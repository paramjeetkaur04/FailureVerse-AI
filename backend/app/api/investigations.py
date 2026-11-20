from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.agents.schemas import DEADLINE_SECONDS, MAX_MODEL_CALLS, MAX_TOOL_CALLS, InvestigationRequest, RunResponse
from app.services.investigations import InvestigationBusy

router = APIRouter(prefix="/api")


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in request.app.state.settings.allowed_origins:
        raise HTTPException(403, "Origin is not allowed.")


@router.get("/ai/status")
async def ai_status(request: Request) -> dict:
    settings = request.app.state.settings
    service = request.app.state.investigations
    provider = await service.provider.status() if settings.ai_enabled else {
        "ready": False, "state": "disabled", "detail": "Set FV_AI_ENABLED=true to enable local investigation.", "model": settings.ollama_model,
    }
    return {**provider, "enabled": settings.ai_enabled, "active_run_id": service.active_id,
            "active_workflow_id": request.app.state.workflows.active_id,
            "limits": {"model_calls": MAX_MODEL_CALLS, "tool_calls": MAX_TOOL_CALLS, "deadline_seconds": DEADLINE_SECONDS},
            "targets": [{"id": "demo", "name": "FailureVerse demo test container"}]}


@router.get("/investigations")
def list_investigations(request: Request, limit: int = Query(20, ge=1, le=50)) -> list[dict]:
    return request.app.state.investigations.list(limit)


@router.post("/investigations", response_model=RunResponse, status_code=202)
async def start_investigation(body: InvestigationRequest, request: Request) -> RunResponse:
    check_origin(request)
    if not request.app.state.settings.ai_enabled:
        raise HTTPException(503, "AI investigation is disabled in this environment.")
    try:
        return await request.app.state.investigations.start(body.target, body.question)
    except InvestigationBusy as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/investigations/{run_id}", response_model=RunResponse)
def get_investigation(run_id: UUID, request: Request) -> RunResponse:
    result = request.app.state.investigations.get(str(run_id))
    if not result:
        raise HTTPException(404, "Investigation not found.")
    return result


@router.post("/investigations/{run_id}/cancel", response_model=RunResponse)
async def cancel_investigation(run_id: UUID, request: Request) -> RunResponse:
    check_origin(request)
    service = request.app.state.investigations
    if not service.get(str(run_id)):
        raise HTTPException(404, "Investigation not found.")
    if not await service.cancel(str(run_id)):
        raise HTTPException(409, "This investigation is not active.")
    return service.get(str(run_id))
