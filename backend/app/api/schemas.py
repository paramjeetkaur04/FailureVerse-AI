from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.core.version import PHASE


class ServiceObservation(BaseModel):
    id: str
    name: str
    kind: Literal["api", "database", "application"]
    status: Literal["healthy", "unavailable", "degraded"]
    latency_ms: float | None = Field(default=None, ge=0)
    detail: str
    measurement: Literal["actual"] = "actual"


class CheckResponse(BaseModel):
    id: str
    checked_at: datetime
    source: Literal["startup", "manual"]
    services: list[ServiceObservation]


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["manual"] = "manual"


class ReadinessResponse(BaseModel):
    status: Literal["healthy", "unavailable"]
    version: str
    database: Literal["connected", "unavailable"]
    phase: int = PHASE


class OverviewResponse(BaseModel):
    project: str = "FailureVerse AI"
    phase: int = PHASE
    environment: str
    healthy_services: int
    total_services: int
    saved_checks: int
    latest: CheckResponse | None
    history: list[CheckResponse]


class PublicConfig(BaseModel):
    environment: str
    database: str = "SQLite"
    demo_health_url: str
    check_timeout_seconds: float
    history_limit: int
    ai_provider: str = "Ollama"
    ollama_model: str
    ai_enabled: bool = False
    docker_control_enabled: bool = False
    phase: int = PHASE
