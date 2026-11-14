from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas import (
    CheckRequest, CheckResponse, OverviewResponse, PublicConfig, ReadinessResponse,
)
from app.services.health import CheckBusyError

router = APIRouter(prefix="/api")


@router.get("/health", response_model=ReadinessResponse)
def health(request: Request, response: Response) -> ReadinessResponse:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = 503
        return ReadinessResponse(status="unavailable", version="0.2.0", database="unavailable")
    return ReadinessResponse(status="healthy", version="0.2.0", database="connected")


@router.get("/overview", response_model=OverviewResponse)
def overview(request: Request) -> OverviewResponse:
    service = request.app.state.health_service
    history = service.history()
    latest = history[0] if history else None
    return OverviewResponse(
        environment=request.app.state.settings.environment,
        healthy_services=sum(s.status == "healthy" for s in latest.services) if latest else 0,
        total_services=len(latest.services) if latest else 0,
        saved_checks=service.count(), latest=latest, history=history,
    )


@router.get("/checks", response_model=list[CheckResponse])
def checks(request: Request, limit: int = Query(default=30, ge=1, le=120)) -> list[CheckResponse]:
    return request.app.state.health_service.history(limit)


@router.post("/checks", response_model=CheckResponse, status_code=201)
async def run_check(body: CheckRequest, request: Request) -> CheckResponse:
    # Browsers from untrusted origins cannot trigger a persisted check, even with a simple request.
    origin = request.headers.get("origin")
    if origin and origin not in request.app.state.settings.allowed_origins:
        raise HTTPException(status_code=403, detail="Origin is not allowed.")
    try:
        return await request.app.state.health_service.collect(body.source)
    except CheckBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/config", response_model=PublicConfig)
def public_config(request: Request) -> PublicConfig:
    settings = request.app.state.settings
    return PublicConfig(
        environment=settings.environment, demo_health_url=str(settings.demo_health_url),
        check_timeout_seconds=settings.check_timeout_seconds, history_limit=settings.history_limit,
        ollama_model=settings.ollama_model,
        ai_enabled=settings.ai_enabled,
    )
