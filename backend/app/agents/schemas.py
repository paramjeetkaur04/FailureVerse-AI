from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MODEL_CALLS = 4
MAX_TOOL_CALLS = 6
DEADLINE_SECONDS = 180
TOOLS = ("inspect_container", "container_logs", "container_stats", "service_health")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvestigationRequest(StrictModel):
    target: Literal["demo"] = "demo"
    question: str = Field(default="Investigate the demo application's current health and possible reliability issues.", min_length=5, max_length=400)


class NoArguments(StrictModel):
    pass


class Finding(StrictModel):
    statement: str = Field(min_length=1, max_length=600)
    evidence_ids: list[str] = Field(min_length=1, max_length=6)
    claim_id: str | None = None
    source_fields: list[str] = Field(default_factory=list)


class InvestigationReport(StrictModel):
    summary: str = Field(min_length=1, max_length=1000)
    observations: list[Finding] = Field(max_length=6)
    suspected_root_causes: list[Finding] = Field(max_length=4)
    uncertainties: list[str] = Field(min_length=1, max_length=6)
    recommended_actions: list[Finding] = Field(max_length=4)
    grounding_version: Literal["legacy", "2.1"] = "legacy"
    outcome: Literal["conclusions", "insufficient_evidence"] = "conclusions"
    summary_evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[Finding] = Field(default_factory=list)
    model_selection_accepted: bool | None = None
    validation_notes: list[str] = Field(default_factory=list)


class ReportSelection(StrictModel):
    """Only references are model-generated; arbitrary factual text/numbers are prohibited."""
    observations: list[str] = Field(min_length=1, max_length=4)
    hypotheses: list[str] = Field(max_length=2)
    recommendations: list[str] = Field(min_length=1, max_length=2)


class Evidence(StrictModel):
    id: str
    tool: str
    observed_at: str
    measurement: Literal["actual", "simulated"] = "actual"
    data: dict

    @field_validator("observed_at")
    @classmethod
    def timestamp_has_timezone(cls, value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError("Evidence timestamps require a timezone.")
        return value


class RunResponse(BaseModel):
    id: str
    target: str
    question: str
    model: str
    status: str
    created_at: datetime
    finished_at: datetime | None
    model_calls: int
    tool_calls: int
    report: InvestigationReport | None
    evidence: list[Evidence]
    error: str | None
    events: list[dict]
    limits: dict[str, int] = {"model_calls": MAX_MODEL_CALLS, "tool_calls": MAX_TOOL_CALLS, "deadline_seconds": DEADLINE_SECONDS}
