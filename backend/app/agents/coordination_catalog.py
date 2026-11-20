"""Deterministic monitoring policy and source-bound specialist proposal catalogs."""
import hashlib
import json

from app.agents.grounding import GroundingError, build_catalog, validate_report
from app.agents.metrics import at_memory_review_threshold, memory_values
from app.agents.schemas import Evidence, InvestigationReport
from app.agents.coordination_schemas import MonitoringResult, Proposal, Selection, Signal, SpecialistResult, WorkflowCheckpoint


def monitor(evidence: list[Evidence]) -> MonitoringResult:
    signals, missing = [], []
    checks = {item.tool: item for item in evidence if item.tool != 'service_health'}
    services = {item.data.get('service'): item for item in evidence if item.tool == 'service_health'}

    def signal(item, kind, severity, statement, fields):
        signals.append(Signal(kind=kind, severity=severity, statement=statement,
            evidence_ids=[item.id], claim_id=f'M{len(signals)+1}', source_fields=[f'data.{name}' for name in fields]))

    inspection = checks.get('inspect_container')
    if inspection is None or type(inspection.data.get('running')) is not bool:
        missing.append('Valid container running state')
    elif not inspection.data['running']:
        signal(inspection, 'stopped', 'high', 'The designated demo container was not running at inspection.', ['running'])
    elif inspection.data.get('health_status') == 'unhealthy':
        signal(inspection, 'health_failure', 'high', 'Docker reported the configured demo health check as unhealthy.', ['health_status'])
    elif inspection.data.get('health_status') != 'healthy':
        missing.append('Configured Docker health result')
    for service in ('database', 'demo', 'backend'):
        item = services.get(service)
        if item is None or item.data.get('status') not in {'healthy', 'degraded', 'unavailable'}:
            missing.append(f'Valid {service} health probe')
        elif item.data['status'] != 'healthy':
            signal(item, 'database_failure' if service == 'database' else 'service_failure', 'high',
                f'The fixed {service} health probe reported {item.data["status"]}.', ['service', 'status'])
    stats = checks.get('container_stats')
    percent = memory_values(stats.data)['memory_usage_percent'] if stats else None
    if percent is None:
        missing.append('Consistent memory usage and limit counters')
    elif at_memory_review_threshold(stats.data):
        signal(stats, 'memory_pressure', 'warning',
            f'Memory usage was {percent:.2f}% of the recorded limit, meeting the 90% review policy.',
            ['memory_usage_bytes', 'memory_limit_bytes'])
    return MonitoringResult(state='incident' if signals else 'insufficient_evidence' if missing else 'healthy',
        signals=signals, missing=missing, evidence_ids=[item.id for item in evidence])


def catalog(role: str, checkpoint: WorkflowCheckpoint) -> tuple[dict[str, Proposal], list[set[str]]]:
    if checkpoint.monitoring is None:
        raise GroundingError('Monitoring evidence is required before specialist planning.')
    # Preserve earlier observed incidents and include failures discovered by the investigator.
    # Choosing only the initial monitoring snapshot could hide a later failed diagnostic.
    by_id = {item.id: item for item in checkpoint.evidence}
    latest = monitor(checkpoint.evidence)
    observed = {}
    for item in [*checkpoint.monitoring.signals, *latest.signals]:
        service = by_id[item.evidence_ids[0]].data.get('service')
        observed[(item.kind, service)] = item
    monitoring = latest.model_copy(update={'signals': list(observed.values())})
    entries, groups = {}, []

    def add(key, action, statement, ids, fields):
        entries[key] = Proposal(claim_id=key, action=action, statement=statement,
            evidence_ids=ids[:6], source_fields=fields)

    ids = monitoring.evidence_ids
    if not ids:
        raise GroundingError('No collected evidence supports a specialist proposal.')
    if role == 'risk':
        scope = next((item for item in reversed(checkpoint.investigation_evidence) if item.tool == 'investigation_scope'), None)
        add('K1', 'review_snapshot_limits',
            'Policy assessment: these point-in-time observations do not establish future reliability, a causal diagnosis, CPU utilization or disk utilization.',
            [scope.id, ids[0]] if scope else ids[:1], ['data.unmeasured_fields', 'observed_at'] if scope else ['observed_at'])
        groups.append({'K1'})
        for index, signal in enumerate(monitoring.signals, 2):
            add(f'K{index}', 'review_observed_signal',
                f'Policy severity {signal.severity}: {signal.statement} The underlying cause remains unconfirmed.',
                signal.evidence_ids, signal.source_fields)
            groups.append({f'K{index}'})
    else:
        prefix = 'S' if role == 'simulation' else 'P'
        if not monitoring.signals:
            add(f'{prefix}1', 'collect_control_baseline' if role == 'simulation' else 'repeat_read_only_checks',
                'Proposed only: collect another read-only baseline and compare observations before considering a failure experiment or recovery change.',
                ids[:1], ['observed_at'])
            add(f'{prefix}2', 'plan_interval_observation' if role == 'simulation' else 'request_human_review',
                'Proposed only: review the collected snapshot with an engineer and plan interval observations before any infrastructure change.',
                ids[:1], ['observed_at'])
            groups.append({f'{prefix}1', f'{prefix}2'})
        actions = {
            'stopped': ('plan_stopped_container_experiment', 'propose_start_demo', 'Review the observed stopped state and logs before any separately approved start of the designated demo.'),
            'health_failure': ('plan_health_probe_experiment', 'propose_restart_demo', 'Review failed health-check evidence before considering a separately approved demo restart.'),
            'memory_pressure': ('plan_memory_pressure_experiment', 'review_memory_settings', 'Collect interval samples and review the application and configured memory limit; a leak is not established.'),
            'database_failure': ('plan_database_probe_experiment', 'review_database_connectivity', 'Review fixed database-probe failures and configuration before proposing a database recovery action.'),
            'service_failure': ('plan_service_probe_experiment', 'review_service_health', 'Review failed service-probe evidence before proposing a recovery action.'),
        }
        for index, signal in enumerate(monitoring.signals, 1):
            experiment, recovery, description = actions[signal.kind]
            add(f'{prefix}{index}a', experiment if role == 'simulation' else recovery,
                ('Proposed experiment, not performed: design a bounded isolated test of the observed signal. ' if role == 'simulation' else 'Proposed recovery review, not executed: ')
                + description, signal.evidence_ids, signal.source_fields)
            add(f'{prefix}{index}b', 'request_human_review',
                'Proposed only: request human review of this observed signal and collect additional read-only evidence before any experiment or recovery operation.',
                signal.evidence_ids, signal.source_fields)
            groups.append({f'{prefix}{index}a', f'{prefix}{index}b'})
    # A model cannot omit an observed failure or the risk limitations by choosing a benign item.
    if len(groups) > 4:
        raise GroundingError('Too many observed signals for the bounded specialist schema; evidence needs human review.')
    return entries, groups


def select(role: str, selection: Selection, checkpoint: WorkflowCheckpoint) -> SpecialistResult:
    entries, groups = catalog(role, checkpoint)
    chosen = set(selection.ids)
    if len(selection.ids) != len(chosen) or not chosen.issubset(entries) or any(not chosen.intersection(group) for group in groups):
        raise GroundingError('Select at least one supported proposal for each required signal, without duplicate or invented IDs.')
    result = SpecialistResult(role=role, method='deterministic_policy' if role == 'risk' else 'ollama_catalog_selection',
        items=[entries[key] for key in selection.ids])
    if role == 'recovery':
        evidence_digest = hashlib.sha256(json.dumps([item.model_dump() for item in checkpoint.evidence], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        binding = {'target': 'demo', 'evidence_digest': evidence_digest,
            'items': [item.model_dump() for item in result.items], 'execution_enabled': False}
        result.plan_hash = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result


def validate_checkpoint(checkpoint: WorkflowCheckpoint) -> None:
    order = {'monitoring': 0, 'investigation': 1, 'simulation': 2, 'risk': 3, 'recovery': 4, 'done': 5}
    stage = order[checkpoint.next_stage]
    if stage >= 1 and checkpoint.monitoring is None:
        raise GroundingError('A checkpoint cannot skip monitoring.')
    if checkpoint.outcome is not None and checkpoint.next_stage != 'done':
        raise GroundingError('A terminal outcome cannot have a pending stage.')
    if checkpoint.outcome == 'observed_healthy':
        if checkpoint.monitoring.state != 'healthy' or checkpoint.model_calls or checkpoint.investigation or checkpoint.specialists:
            raise GroundingError('Healthy monitoring completion contains inconsistent agent state.')
    elif checkpoint.outcome != 'insufficient_evidence':
        if stage >= 2 and (checkpoint.investigation is None or checkpoint.investigation.outcome != 'conclusions'):
            raise GroundingError('A checkpoint cannot skip a validated investigation.')
        for name, minimum in [('simulation', 3), ('risk', 4), ('recovery', 5)]:
            if stage >= minimum and name not in checkpoint.specialists:
                raise GroundingError('A checkpoint cannot skip a required planning stage.')
        if stage == 5 and checkpoint.outcome != 'awaiting_review':
            raise GroundingError('Completed planning must explicitly await human review.')
    by_id = {item.id: item for item in checkpoint.evidence}
    if checkpoint.monitoring:
        selected = [by_id[key] for key in checkpoint.monitoring.evidence_ids]
        if monitor(selected) != checkpoint.monitoring:
            raise GroundingError('Monitoring checkpoint differs from source evidence.')
    for item in checkpoint.investigation_evidence:
        if by_id.get(item.id) != item:
            raise GroundingError('Investigation evidence differs from shared evidence.')
    if checkpoint.investigation:
        validate_report(InvestigationReport.model_validate(checkpoint.investigation),
            build_catalog([item.model_dump() for item in checkpoint.investigation_evidence]))
    for role, result in checkpoint.specialists.items():
        if role not in {'simulation', 'risk', 'recovery'} or result != select(role, Selection(ids=[item.claim_id for item in result.items]), checkpoint):
            raise GroundingError('Specialist checkpoint differs from its evidence-bound catalog.')
