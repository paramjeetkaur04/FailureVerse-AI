"""Phase 3 controlled scenarios: tools are always SIMULATED in this evaluator."""
import asyncio
import json
from datetime import datetime, timezone
from time import perf_counter

from app.agents.coordination import CoordinationAgent
from app.agents.coordination_catalog import validate_checkpoint
from app.agents.coordination_schemas import WORKFLOW_SECONDS, WorkflowCheckpoint
from app.agents.schemas import NoArguments, TOOLS
from app.tools.diagnostics import PolicyDenied
from evaluation.scenarios import SCENARIOS, observations


class ScriptedWorkflowProvider:
    """Regression selector, not a measurement of LLM accuracy."""
    def __init__(self):
        self.calls, self.status_calls = [], 0

    async def status(self):
        self.status_calls += 1
        return {'ready': True, 'state': 'ready', 'detail': 'Scripted evaluation selector', 'model': 'scripted-selector'}

    async def chat(self, messages, **kwargs):
        self.calls.append(kwargs)
        if 'tools' in kwargs:
            return {'content': '', 'tool_calls': [{'function': {'name': item['function']['name'], 'arguments': {}}} for item in kwargs['tools']]}
        body = json.loads(messages[-1]['content'])
        if 'ids' in kwargs['schema']['properties']:
            selection = {'ids': [group[0] for group in body['required_groups']]}
        else:
            catalog = body['catalog']
            selection = {'observations': catalog['required_observations'] or [catalog['observations'][0]['id']],
                'hypotheses': [], 'recommendations': [catalog['recommendations'][0]['id']]}
        return {'content': json.dumps(selection)}


class SimulatedWorkflowDiagnostics:
    def __init__(self, scenario):
        self.data, self.calls = observations(scenario), []

    async def execute(self, name, arguments, target='demo'):
        if name not in TOOLS or target != 'demo':
            raise PolicyDenied('Evaluation denies unregistered operations.')
        NoArguments.model_validate(arguments)
        self.calls.append(name)
        return {'measurement': 'simulated', 'observed_at': datetime.now(timezone.utc).isoformat(), 'data': self.data[name]}


async def evaluate_workflows(real_provider=None):
    cases = []
    signals = {'stopped': 'stopped', 'failed_health': 'health_failure', 'high_memory': 'memory_pressure', 'database_failure': 'database_failure'}
    for scenario in SCENARIOS:
        provider = real_provider or ScriptedWorkflowProvider()
        diagnostics, events, saved = SimulatedWorkflowDiagnostics(scenario.id), [], []
        def persist(checkpoint, event):
            saved[:] = [checkpoint]
            events.append(event)
        agent = CoordinationAgent(provider, diagnostics, persist, scenario.question, False)
        started = perf_counter()
        failure, validated = None, False
        try:
            async with asyncio.timeout(WORKFLOW_SECONDS):
                result = await agent.run(WorkflowCheckpoint())
            validate_checkpoint(result)
            validated = True
        except Exception as exc:
            failure = type(exc).__name__
            result = WorkflowCheckpoint.model_validate(saved[0]) if saved else WorkflowCheckpoint()
        expected = 'observed_healthy' if scenario.id == 'healthy' else 'awaiting_review'
        completed = [event['role'] for event in events if event['kind'] == 'checkpoint']
        expected_stages = ['monitoring'] if scenario.id == 'healthy' else ['monitoring', 'investigation', 'simulation', 'risk', 'recovery']
        findings = list(result.monitoring.signals) if result.monitoring else []
        references = list(result.monitoring.evidence_ids) if result.monitoring else []
        if result.investigation:
            report = result.investigation
            findings += report.observations + report.suspected_root_causes + report.recommended_actions + report.limitations
            references += report.summary_evidence_ids
        findings += [item for output in result.specialists.values() for item in output.items]
        references += [ref for item in findings for ref in item.evidence_ids]
        ids = {item.id for item in result.evidence}
        signal_present = scenario.id == 'healthy' or signals[scenario.id] in {item.kind for item in result.monitoring.signals}
        cases.append({'scenario': scenario.id, 'measurement': 'simulated', 'expected_outcome': expected,
            'outcome': result.outcome, 'accepted': validated and result.outcome == expected and signal_present,
            'stage_path_valid': completed == expected_stages, 'stages': completed, 'failure': failure,
            'valid_references': sum(ref in ids for ref in references), 'references': len(references),
            'source_validation': validated, 'returned_section_claims': len(findings),
            'model_calls': result.model_calls, 'tool_calls': result.tool_calls,
            'duration_seconds': round(perf_counter()-started, 3), 'checkpoint': result.model_dump(), 'events': events})
    references = sum(case['references'] for case in cases)
    return {'mode': 'simulated_tools_real_ollama' if real_provider else 'simulated_tools_scripted_model',
        'summary': {'completion_rate': sum(case['accepted'] for case in cases)/len(cases),
            'stage_path_accuracy': sum(case['stage_path_valid'] for case in cases)/len(cases),
            'evidence_citation_validity': sum(case['valid_references'] for case in cases)/references if references else None,
            'source_validated_runs': sum(case['source_validation'] for case in cases),
            'average_duration_seconds': sum(case['duration_seconds'] for case in cases)/len(cases)}, 'cases': cases}
