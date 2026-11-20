"""Bounded five-stage LangGraph orchestration; all proposed actions remain inert."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from pydantic import ValidationError

from app.agents.coordination_catalog import catalog, monitor, select, validate_checkpoint
from app.agents.coordination_schemas import WORKFLOW_MODELS, WORKFLOW_TOOLS, Selection, WorkflowCheckpoint
from app.agents.investigation import Budget, InvestigationAgent, InvestigationFailure
from app.agents.schemas import Evidence, InvestigationReport
from app.core.redaction import redact
from app.services.ollama import ProviderError
from app.tools.diagnostics import DiagnosticError, PolicyDenied


class GraphState(TypedDict):
    checkpoint: dict


class CoordinationAgent:
    def __init__(self, provider, diagnostics, persist, question, investigate_healthy):
        self.provider, self.diagnostics, self.persist = provider, diagnostics, persist
        self.question, self.investigate_healthy = question, investigate_healthy
        self.cp = WorkflowCheckpoint()
        self.namespace = uuid4().hex

    def event(self, role, kind, title, **details):
        # Validate the entire shared state before persisting a budget, evidence or transition.
        self.cp = WorkflowCheckpoint.model_validate(self.cp.model_dump())
        self.persist(self.cp.model_dump(), {'role': role, 'kind': kind, 'title': redact(title, 600),
            'model_calls': self.cp.model_calls, 'tool_calls': self.cp.tool_calls, **details})

    def charge(self, role, kind):
        total, per_role, limit = ('model_calls', 'role_models', WORKFLOW_MODELS) if kind == 'model' else ('tool_calls', 'role_tools', WORKFLOW_TOOLS)
        if getattr(self.cp, total) >= limit:
            raise InvestigationFailure(f'The aggregate workflow {kind} budget is exhausted.')
        counts = getattr(self.cp, per_role)
        role_limit = (4 if role == 'investigation' else 2) if kind == 'model' else (3 if role == 'monitoring' else 6)
        if counts.get(role, 0) >= role_limit:
            raise InvestigationFailure(f'The {role} {kind} budget is exhausted.')
        setattr(self.cp, total, getattr(self.cp, total)+1)
        counts[role] = counts.get(role, 0)+1

    async def run(self, checkpoint: WorkflowCheckpoint):
        validate_checkpoint(checkpoint)
        graph = StateGraph(GraphState)
        handlers = {'monitoring': self.monitoring, 'investigation': self.investigation,
            'simulation': lambda: self.specialist('simulation'), 'risk': self.risk,
            'recovery': lambda: self.specialist('recovery')}

        def node(role, handler):
            async def step(state):
                self.cp = WorkflowCheckpoint.model_validate(state['checkpoint'])
                self.event(role, 'stage_started', f'{role.capitalize()} stage started')
                await handler()
                self.event(role, 'checkpoint', f'{role.capitalize()} stage completed; checkpoint saved', next_stage=self.cp.next_stage)
                return {'checkpoint': self.cp.model_dump()}
            return step

        def route(state):
            return END if state['checkpoint']['next_stage'] == 'done' else state['checkpoint']['next_stage']
        for role, handler in handlers.items():
            graph.add_node(role, node(role, handler))
            graph.add_conditional_edges(role, route)
        graph.add_conditional_edges(START, route)
        with tracing_context(enabled=False):
            result = await graph.compile().ainvoke({'checkpoint': checkpoint.model_dump()}, config={'recursion_limit': 12})
        return WorkflowCheckpoint.model_validate(result['checkpoint'])

    async def monitoring(self):
        for name in ('inspect_container', 'service_health', 'container_stats'):
            if name in self.cp.monitoring_attempted:
                continue
            self.charge('monitoring', 'tool')
            self.cp.monitoring_attempted.append(name)
            self.event('monitoring', 'tool_call', 'Collecting a fixed read-only monitoring snapshot', tool=name)
            try:
                result = await self.diagnostics.execute(name, {})
                if not isinstance(result, dict) or not isinstance(result.get('data'), dict):
                    raise DiagnosticError('Invalid monitoring observation envelope.')
                data = result['data'].get('services') if name == 'service_health' else [result['data']]
                if not isinstance(data, list) or not 1 <= len(data) <= 3:
                    raise DiagnosticError('Invalid monitoring observation envelope.')
                pending = [Evidence(id=f'{self.namespace}.M{len(self.cp.evidence)+index+1}', tool=name,
                    measurement=result['measurement'], observed_at=result['observed_at'], data=item) for index, item in enumerate(data)]
                self.cp.evidence.extend(pending)
                self.event('monitoring', 'observation', 'Monitoring evidence collected', evidence_ids=[item.id for item in pending])
            except PolicyDenied:
                raise
            except DiagnosticError as exc:
                self.event('monitoring', 'error', f'Monitoring diagnostic failed: {redact(str(exc), 200)}', tool=name)
            except (ValidationError, KeyError, TypeError):
                self.event('monitoring', 'error', 'Monitoring diagnostic returned an invalid observation envelope.', tool=name)
        self.cp.monitoring = monitor(self.cp.evidence)
        if self.cp.monitoring.state == 'healthy' and not self.investigate_healthy:
            self.cp.next_stage, self.cp.outcome = 'done', 'observed_healthy'
        elif self.cp.monitoring.state == 'insufficient_evidence':
            self.cp.next_stage, self.cp.outcome = 'done', 'insufficient_evidence'
        else:
            self.cp.next_stage = 'investigation'

    async def investigation(self):
        if self.cp.investigation_expires_at is None:
            self.cp.investigation_expires_at = (datetime.now(timezone.utc)+timedelta(seconds=180)).isoformat()
            self.event('investigation', 'deadline', 'Original 180-second investigator deadline recorded')
        remaining = (datetime.fromisoformat(self.cp.investigation_expires_at)-datetime.now(timezone.utc)).total_seconds()
        async with asyncio.timeout(max(0, remaining)):
            await self.investigate()

    async def investigate(self):
        availability = await self.provider.status()
        if not availability['ready'] and availability.get('state') == 'unavailable':
            self.event('investigation', 'error', 'Local provider unavailable; retrying preflight once within the original workflow deadline')
            availability = await self.provider.status()
        if not availability['ready']:
            raise ProviderError(availability['detail'])
        self.cp.investigation_evidence = [item for item in self.cp.investigation_evidence if item.tool != 'investigation_scope']

        def receive(event):
            details = {key: value for key, value in event.items() if key not in {'kind', 'title', 'model_calls', 'tool_calls', 'evidence'}}
            if event['kind'] == 'model_call':
                self.charge('investigation', 'model')
            elif event['kind'] == 'tool_call':
                self.charge('investigation', 'tool')
                self.cp.attempted_tools.append(event['tool'])
            elif event['kind'] == 'observation':
                item = Evidence.model_validate(event['evidence'])
                self.cp.investigation_evidence.append(item)
                self.cp.evidence.append(item)
                details['evidence_ids'] = [item.id]
            self.event('investigation', event['kind'], event['title'], **details)

        agent = InvestigationAgent(self.provider, self.diagnostics, receive)
        agent.budget = Budget(self.cp.role_models.get('investigation', 0), self.cp.role_tools.get('investigation', 0))
        agent.attempted_tools = list(self.cp.attempted_tools)
        subjects = {'stopped': 'stopped container state and logs', 'health_failure': 'container health',
            'memory_pressure': 'memory counters', 'database_failure': 'database probe and logs', 'service_failure': 'HTTP service health'}
        topics = sorted({subjects[item.kind] for item in self.cp.monitoring.signals})
        question = self.question[:280] + (' Monitoring signals require coverage of: ' + ', '.join(topics) if topics else '')
        report = await agent.run(question, seed_evidence=[item.model_dump() for item in self.cp.investigation_evidence])
        self.cp.investigation = InvestigationReport.model_validate(report)
        if self.cp.investigation.outcome != 'conclusions':
            self.cp.next_stage, self.cp.outcome = 'done', 'insufficient_evidence'
        else:
            self.cp.next_stage = 'simulation'

    async def specialist(self, role):
        entries, groups = catalog(role, self.cp)
        self.charge(role, 'model')
        self.event(role, 'model_call', 'Selecting evidence-bound planning proposals through local Ollama')
        schema = Selection.model_json_schema()
        schema['properties']['ids']['items'] = {'type': 'string', 'enum': list(entries)}
        result = await self.provider.chat([
            {'role': 'system', 'content': 'Select proposal IDs only. Include at least one ID from EVERY required group. Choose the most useful supported proposal or alternatives, up to four IDs. Proposals are NOT executed. No new text, numbers, facts, causes or actions. Return only the JSON schema. /no_think'},
            {'role': 'user', 'content': json.dumps({'role': role, 'required_groups': [sorted(group) for group in groups],
                'catalog': [{'id': key, 'proposal': item.statement} for key, item in entries.items()]})},
        ], schema=schema)
        selection = Selection.model_validate_json(result.get('content', ''))
        self.cp.specialists[role] = select(role, selection, self.cp)
        self.cp.next_stage = 'risk' if role == 'simulation' else 'done'
        if role == 'recovery':
            self.cp.outcome = 'awaiting_review'

    async def risk(self):
        entries, _ = catalog('risk', self.cp)
        self.cp.specialists['risk'] = select('risk', Selection(ids=list(entries)), self.cp)
        self.event('risk', 'policy', 'Python policy classified observed signals and retained uncertainty; no model supplied severity or probabilities')
        self.cp.next_stage = 'recovery'
