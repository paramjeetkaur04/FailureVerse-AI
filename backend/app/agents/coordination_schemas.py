"""Strict shared state for the Phase 3 planning-only workflow."""
from datetime import datetime
from typing import Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from app.agents.schemas import Evidence, Finding, InvestigationReport, StrictModel

WORKFLOW_MODELS = 7
WORKFLOW_TOOLS = 9
WORKFLOW_SECONDS = 300
ROLES = ('monitoring', 'investigation', 'simulation', 'risk', 'recovery')
Stage = Literal['monitoring', 'investigation', 'simulation', 'risk', 'recovery', 'done']


class WorkflowRequest(StrictModel):
    target: Literal['demo'] = 'demo'
    question: str = Field(default='Investigate current demo container health.', min_length=5, max_length=400)
    investigate_healthy: bool = False


class Signal(Finding):
    kind: Literal['stopped', 'health_failure', 'memory_pressure', 'database_failure', 'service_failure']
    severity: Literal['warning', 'high']


class MonitoringResult(StrictModel):
    state: Literal['healthy', 'incident', 'insufficient_evidence']
    signals: list[Signal] = Field(default_factory=list, max_length=6)
    missing: list[str] = Field(default_factory=list, max_length=6)
    evidence_ids: list[str] = Field(max_length=40)
    policy: Literal['snapshot-v1-memory-90-percent'] = 'snapshot-v1-memory-90-percent'


class Proposal(Finding):
    action: str
    execution_enabled: Literal[False] = False


class Selection(StrictModel):
    ids: list[str] = Field(min_length=1, max_length=4)


class SpecialistResult(StrictModel):
    role: Literal['simulation', 'risk', 'recovery']
    method: Literal['ollama_catalog_selection', 'deterministic_policy'] = 'ollama_catalog_selection'
    items: list[Proposal] = Field(min_length=1, max_length=4)
    execution_enabled: Literal[False] = False
    plan_hash: str | None = None


class WorkflowCheckpoint(StrictModel):
    version: Literal[1] = 1
    next_stage: Stage = 'monitoring'
    evidence: list[Evidence] = Field(default_factory=list, max_length=40)
    investigation_evidence: list[Evidence] = Field(default_factory=list, max_length=30)
    monitoring: MonitoringResult | None = None
    investigation: InvestigationReport | None = None
    specialists: dict[str, SpecialistResult] = Field(default_factory=dict)
    model_calls: int = Field(default=0, ge=0, le=WORKFLOW_MODELS, strict=True)
    tool_calls: int = Field(default=0, ge=0, le=WORKFLOW_TOOLS, strict=True)
    role_models: dict[str, StrictInt] = Field(default_factory=dict)
    role_tools: dict[str, StrictInt] = Field(default_factory=dict)
    attempted_tools: list[str] = Field(default_factory=list, max_length=6)
    monitoring_attempted: list[Literal['inspect_container', 'container_stats', 'service_health']] = Field(default_factory=list, max_length=3)
    investigation_expires_at: str | None = None
    outcome: Literal['observed_healthy', 'awaiting_review', 'insufficient_evidence'] | None = None

    @field_validator('investigation_expires_at')
    @classmethod
    def aware_investigator_expiry(cls, value):
        if value is not None and datetime.fromisoformat(value).utcoffset() is None:
            raise ValueError('Investigator expiry must include a timezone.')
        return value

    @model_validator(mode='after')
    def validate_identity_and_budgets(self):
        ids = [item.id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate workflow evidence IDs.')
        for counts in (self.role_models, self.role_tools):
            if any(key not in ROLES or type(value) is not int or value < 0 for key, value in counts.items()):
                raise ValueError('Invalid role budget counters.')
        if sum(self.role_models.values()) != self.model_calls or sum(self.role_tools.values()) != self.tool_calls:
            raise ValueError('Role counters do not match aggregate counters.')
        if self.role_models.get('investigation', 0) > 4 or self.role_tools.get('investigation', 0) > 6:
            raise ValueError('Investigator budget exceeded.')
        if self.role_models.get('monitoring', 0) or self.role_tools.get('monitoring', 0) > 3:
            raise ValueError('Monitoring budget exceeded.')
        if self.role_models.get('risk', 0) or len(set(self.monitoring_attempted)) != len(self.monitoring_attempted):
            raise ValueError('Invalid deterministic stage counters.')
        if self.role_tools.get('monitoring', 0) != len(self.monitoring_attempted):
            raise ValueError('Monitoring attempts do not match consumed budget.')
        if any(self.role_models.get(role, 0) > 2 or self.role_tools.get(role, 0) for role in ('simulation', 'risk', 'recovery')):
            raise ValueError('Specialist budget exceeded.')
        investigation_ids = [item.id for item in self.investigation_evidence]
        if len(investigation_ids) != len(set(investigation_ids)) or not set(investigation_ids).issubset(ids):
            raise ValueError('Investigation evidence is absent from shared state.')
        return self


class WorkflowResponse(StrictModel):
    id: str
    target: Literal['demo']
    question: str
    investigate_healthy: bool
    model: str
    status: str
    created_at: datetime
    expires_at: datetime
    finished_at: datetime | None
    checkpoint: WorkflowCheckpoint
    events: list[dict]
    error: str | None
    resumable: bool
    execution_enabled: Literal[False] = False
    limits: dict[str, int] = {'model_calls': WORKFLOW_MODELS, 'tool_calls': WORKFLOW_TOOLS, 'deadline_seconds': WORKFLOW_SECONDS}
