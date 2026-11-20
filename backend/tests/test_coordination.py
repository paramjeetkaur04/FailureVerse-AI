import asyncio
import copy

import pytest
from pydantic import ValidationError

from app.agents.coordination import CoordinationAgent
from app.agents.coordination_catalog import catalog, monitor, select, validate_checkpoint
from app.agents.coordination_schemas import Selection, WorkflowCheckpoint
from app.agents.grounding import GroundingError, build_catalog
from app.agents.investigation import InvestigationFailure
from app.agents.metrics import at_memory_review_threshold
from app.agents.schemas import Evidence
from tests.workflow_fixtures import WorkflowDiagnostics, WorkflowProvider


def exercise(scenario='healthy', force=False, provider=None, checkpoint=None):
    provider, diagnostics, events = provider or WorkflowProvider(), WorkflowDiagnostics(scenario), []
    agent = CoordinationAgent(provider, diagnostics, lambda cp, event: events.append((copy.deepcopy(cp), event)),
        'Investigate current demo container health.', force)
    result = asyncio.run(agent.run(checkpoint or WorkflowCheckpoint()))
    return result, events, provider, diagnostics


def test_healthy_monitoring_stops_without_model_calls_or_inventing_incident():
    result, events, provider, diagnostics = exercise()
    assert result.outcome == 'observed_healthy' and result.monitoring.signals == []
    assert result.model_calls == 0 and result.tool_calls == 3
    assert provider.calls == [] and provider.status_calls == 0
    assert diagnostics.calls == ['inspect_container', 'service_health', 'container_stats']
    assert {event['role'] for _, event in events} == {'monitoring'}
    validate_checkpoint(result)


@pytest.mark.parametrize('scenario,expected', [
    ('stopped', 'stopped'), ('unhealthy', 'health_failure'),
    ('high_memory', 'memory_pressure'), ('database_failure', 'database_failure'),
])
def test_controlled_incident_routes_through_all_roles_with_source_bound_proposals(scenario, expected):
    result, events, provider, _ = exercise(scenario)
    assert result.outcome == 'awaiting_review'
    assert expected in {signal.kind for signal in result.monitoring.signals}
    assert {event['role'] for _, event in events} == {'monitoring', 'investigation', 'simulation', 'risk', 'recovery'}
    assert result.model_calls <= 7 and result.tool_calls <= 9
    assert result.role_models.get('risk', 0) == 0
    assert result.specialists['risk'].method == 'deterministic_policy'
    assert result.specialists['recovery'].plan_hash
    assert all(item.measurement == 'simulated' for item in result.evidence)
    assert all(not item.execution_enabled for output in result.specialists.values() for item in output.items)
    validate_checkpoint(result)


def test_forced_healthy_workflow_uses_native_investigation_and_two_planning_model_calls():
    result, _, provider, _ = exercise(force=True)
    assert result.outcome == 'awaiting_review' and not result.monitoring.signals
    assert result.model_calls == 4 and result.tool_calls == 5
    assert len(provider.calls) == 4 and sum('tools' in call for call in provider.calls) == 1
    assert all(output.execution_enabled is False for output in result.specialists.values())
    validate_checkpoint(result)


def test_catalog_rejects_invented_duplicate_and_omitted_signal_ids():
    result, _, _, _ = exercise('unhealthy')
    entries, groups = catalog('recovery', result)
    assert len(groups) == 2 and len(entries) == 4
    for ids in [['invented'], [next(iter(groups[0]))]*2, [next(iter(groups[0]))]]:
        with pytest.raises(GroundingError):
            select('recovery', Selection(ids=ids), result)


def test_checkpoint_cannot_rewrite_sources_or_enable_execution():
    result, _, _, _ = exercise(force=True)
    changed = result.model_copy(deep=True)
    changed.specialists['recovery'].items[0].statement = 'Confirmed leak and recovery executed.'
    with pytest.raises(GroundingError):
        validate_checkpoint(changed)
    changed = result.model_dump()
    changed['specialists']['recovery']['execution_enabled'] = True
    with pytest.raises(ValidationError):
        WorkflowCheckpoint.model_validate(changed)


def test_checkpoint_rejects_counter_reset_and_skipped_stages():
    result, _, _, _ = exercise(force=True)
    changed = result.model_dump()
    changed['model_calls'] = 0
    with pytest.raises(ValidationError):
        WorkflowCheckpoint.model_validate(changed)
    with pytest.raises(GroundingError):
        validate_checkpoint(WorkflowCheckpoint(next_stage='recovery'))


@pytest.mark.parametrize('usage,limit,pressure', [(899950, 1000000, False), (900000, 1000000, True), (101, 100, False), (True, 100, False)])
def test_policy_uses_exact_counters_instead_of_rounded_display(usage, limit, pressure):
    data = {'memory_usage_bytes': usage, 'memory_limit_bytes': limit}
    assert at_memory_review_threshold(data) is pressure
    evidence = Evidence(id='test.stats', tool='container_stats', measurement='simulated', observed_at='2026-11-15T00:00:00Z', data=data)
    assert bool(build_catalog([evidence.model_dump()]).sections['hypotheses']) is pressure


def test_missing_or_inconsistent_monitoring_does_not_claim_healthy():
    result = monitor([])
    assert result.state == 'insufficient_evidence' and result.missing
    cp, _, _, _ = exercise()
    stats = next(item for item in cp.evidence if item.tool == 'container_stats')
    stats.data['memory_usage_bytes'] = stats.data['memory_limit_bytes']+1
    assert monitor(cp.evidence).state == 'insufficient_evidence'


def test_many_requested_tools_cannot_exceed_aggregate_nine_attempt_budget():
    class Repeating(WorkflowProvider):
        async def chat(self, messages, **kwargs):
            if 'tools' in kwargs:
                return {'tool_calls': [{'function': {'name': 'inspect_container', 'arguments': {}}}]*20}
            return await super().chat(messages, **kwargs)
    result, _, _, diagnostics = exercise(force=True, provider=Repeating())
    assert result.tool_calls == 9 and len(diagnostics.calls) == 9
    assert result.outcome == 'insufficient_evidence' and not result.specialists


def test_resume_cannot_gain_fresh_aggregate_inference_budget():
    cp, _, _, _ = exercise(force=True)
    cp.next_stage, cp.outcome = 'recovery', None
    cp.specialists.pop('recovery')
    cp.role_models = {'investigation': 4, 'simulation': 2, 'recovery': 1}
    cp.model_calls = 7
    provider = WorkflowProvider()
    with pytest.raises(InvestigationFailure, match='aggregate'):
        exercise(force=True, provider=provider, checkpoint=cp)
    assert provider.calls == []


def test_planning_includes_failures_discovered_after_healthy_initial_monitoring():
    class Changing(WorkflowDiagnostics):
        async def execute(self, name, *args, **kwargs):
            result = await super().execute(name, *args, **kwargs)
            if self.calls.count(name) > 1:
                if name == 'inspect_container':
                    result['data']['health_status'] = 'unhealthy'
                if name == 'service_health':
                    next(item for item in result['data']['services'] if item['service'] == 'demo')['status'] = 'degraded'
            return result
    agent = CoordinationAgent(WorkflowProvider(), Changing(), lambda cp, event: None, 'Investigate current demo container health.', True)
    result = asyncio.run(agent.run(WorkflowCheckpoint()))
    assert result.monitoring.state == 'healthy' and not result.monitoring.signals
    assert result.outcome == 'awaiting_review'
    risk = ' '.join(item.statement for item in result.specialists['risk'].items)
    assert 'unhealthy' in risk and 'degraded' in risk
    _, required = catalog('recovery', result)
    assert len(required) == 2


@pytest.mark.parametrize('invalid', [True, '1', 1.0, -1])
def test_checkpoint_budget_counters_require_nonnegative_integer_values(invalid):
    with pytest.raises(ValidationError):
        WorkflowCheckpoint.model_validate({'model_calls': invalid, 'role_models': {'investigation': invalid}})


def test_all_monitoring_failures_return_explicit_missing_evidence_without_model_calls():
    from app.tools.diagnostics import DiagnosticError
    class Offline(WorkflowDiagnostics):
        async def execute(self, *args, **kwargs):
            raise DiagnosticError('Simulated diagnostic timeout; no observation collected.')
    provider, events = WorkflowProvider(), []
    agent = CoordinationAgent(provider, Offline(), lambda cp, event: events.append(event), 'Investigate demo health.', False)
    result = asyncio.run(agent.run(WorkflowCheckpoint()))
    assert result.outcome == 'insufficient_evidence'
    assert result.monitoring.missing and not result.evidence
    assert result.model_calls == 0 and result.tool_calls == 3
    assert len([event for event in events if event['kind'] == 'error']) == 3
    assert not provider.calls


def test_plan_fingerprint_binds_the_complete_sanitized_resource_snapshot():
    result, _, _, _ = exercise(force=True)
    changed = result.model_copy(deep=True)
    item = next(item for item in changed.evidence if item.tool == 'inspect_container')
    item.data['id_prefix'] = 'changed-resource'
    with pytest.raises(GroundingError):
        validate_checkpoint(changed)
