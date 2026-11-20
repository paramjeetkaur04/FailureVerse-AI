from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from app.agents.coordination_schemas import WorkflowRequest, WorkflowResponse
from app.agents.grounding import GroundingError
from app.api.investigations import check_origin
from app.core.execution import ExecutionBusy
from app.services.workflows import ResumeDenied

router = APIRouter(prefix='/api/workflows')


@router.get('')
def list_workflows(request: Request, limit: int = Query(20, ge=1, le=50)):
    try:
        return request.app.state.workflows.list(limit)
    except (ValidationError, GroundingError, KeyError) as exc:
        raise HTTPException(503, 'Saved workflow state failed validation and requires storage review.') from exc


@router.post('', status_code=202, response_model=WorkflowResponse)
async def start_workflow(body: WorkflowRequest, request: Request):
    check_origin(request)
    if not request.app.state.settings.ai_enabled:
        raise HTTPException(503, 'Agent workflows are disabled.')
    try:
        return await request.app.state.workflows.start(body)
    except ExecutionBusy as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/{run_id}', response_model=WorkflowResponse)
def get_workflow(run_id: UUID, request: Request):
    try:
        result = request.app.state.workflows.get(str(run_id))
    except (ValidationError, GroundingError, KeyError) as exc:
        raise HTTPException(503, 'Saved workflow state failed validation and requires storage review.') from exc
    if result is None:
        raise HTTPException(404, 'Workflow not found.')
    return result


@router.post('/{run_id}/cancel', response_model=WorkflowResponse)
async def cancel_workflow(run_id: UUID, request: Request):
    check_origin(request)
    if not await request.app.state.workflows.cancel(str(run_id)):
        raise HTTPException(409, 'This workflow is not active.')
    return request.app.state.workflows.get(str(run_id))


@router.post('/{run_id}/resume', status_code=202, response_model=WorkflowResponse)
async def resume_workflow(run_id: UUID, request: Request):
    check_origin(request)
    if not request.app.state.settings.ai_enabled:
        raise HTTPException(503, 'Agent workflows are disabled.')
    try:
        return await request.app.state.workflows.resume(str(run_id))
    except (ExecutionBusy, ResumeDenied) as exc:
        raise HTTPException(409, str(exc)) from exc
