from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_MODEL_CALLS = 4
MAX_TOOL_CALLS = 6
DEADLINE_SECONDS = 180
TOOLS = ("inspect_container", "container_logs", "container_stats")


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


class InvestigationReport(StrictModel):
    summary: str = Field(min_length=1, max_length=1000)
    observations: list[Finding] = Field(min_length=1, max_length=6)
    suspected_root_causes: list[Finding] = Field(max_length=4)
    uncertainties: list[str] = Field(min_length=1, max_length=6)
    recommended_actions: list[Finding] = Field(min_length=1, max_length=4)


class Evidence(StrictModel):
    id: str
    tool: str
    observed_at: str
    measurement: Literal["actual"] = "actual"
    data: dict


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
