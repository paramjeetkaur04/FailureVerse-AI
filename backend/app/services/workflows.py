"""Durable application checkpoints and bounded lifecycle for coordinated agents."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agents.coordination import CoordinationAgent
from app.agents.coordination_catalog import validate_checkpoint
from app.agents.coordination_schemas import WORKFLOW_SECONDS, WorkflowCheckpoint, WorkflowRequest, WorkflowResponse
from app.agents.grounding import GroundingError
from app.agents.investigation import InvestigationFailure
from app.core.execution import ExecutionBusy
from app.core.redaction import redact
from app.models.workflow import WorkflowRecord
from app.services.investigations import utc
from app.services.ollama import ProviderError
from app.tools.diagnostics import PolicyDenied

logger = logging.getLogger(__name__)


class ResumeDenied(Exception):
    pass


class WorkflowService:
    def __init__(self, engine, settings, provider, diagnostics, execution_slot):
        self.engine, self.settings, self.provider = engine, settings, provider
        self.diagnostics, self.execution_slot = diagnostics, execution_slot
        self.active_id = None
        self.task = None
        self.closing = False

    def recover_interrupted(self):
        with Session(self.engine) as session, session.begin():
            session.execute(update(WorkflowRecord).where(WorkflowRecord.status.in_(['queued', 'running'])).values(
                status='interrupted', finished_at=datetime.now(timezone.utc),
                error='Backend restarted. Review the saved checkpoint; explicit resume retains the original deadline and budgets.'))

    def get(self, run_id):
        with Session(self.engine) as session:
            row = session.get(WorkflowRecord, run_id)
            if row is None:
                return None
            checkpoint = WorkflowCheckpoint.model_validate(row.checkpoint)
            validate_checkpoint(checkpoint)
            return WorkflowResponse(id=row.id, target=row.target, question=row.question,
                investigate_healthy=row.investigate_healthy, model=row.model, status=row.status,
                created_at=utc(row.created_at), expires_at=utc(row.expires_at), finished_at=utc(row.finished_at),
                checkpoint=checkpoint, events=row.events, error=row.error,
                resumable=row.status == 'interrupted' and checkpoint.next_stage != 'done'
                    and utc(row.expires_at) > datetime.now(timezone.utc))

    def list(self, limit=20):
        with Session(self.engine) as session:
            rows = session.scalars(select(WorkflowRecord).order_by(WorkflowRecord.created_at.desc()).limit(limit)).all()
            for row in rows:
                validate_checkpoint(WorkflowCheckpoint.model_validate(row.checkpoint))
            return [{'id': row.id, 'question': row.question, 'status': row.status,
                'created_at': utc(row.created_at).isoformat(), 'next_stage': row.checkpoint.get('next_stage'),
                'model_calls': row.checkpoint.get('model_calls', 0), 'tool_calls': row.checkpoint.get('tool_calls', 0)} for row in rows]

    def save(self, run_id, checkpoint, event):
        with Session(self.engine) as session, session.begin():
            row = session.get(WorkflowRecord, run_id)
            if row is None:
                raise InvestigationFailure('Workflow storage is unavailable.')
            if len(row.events) >= 200:
                raise InvestigationFailure('The bounded workflow event limit was reached.')
            row.checkpoint = checkpoint
            row.events = [*row.events, {'sequence': len(row.events)+1,
                'at': datetime.now(timezone.utc).isoformat(), **event}]

    def finish(self, run_id, status, error=None):
        with Session(self.engine) as session, session.begin():
            row = session.get(WorkflowRecord, run_id)
            row.status, row.error = status, error
            row.finished_at = datetime.now(timezone.utc)

    async def start(self, request: WorkflowRequest):
        run_id = str(uuid4())
        self.execution_slot.claim(f'workflow:{run_id}')
        try:
            with Session(self.engine) as session, session.begin():
                session.add(WorkflowRecord(id=run_id, target=request.target,
                    question=redact(request.question, 400), investigate_healthy=request.investigate_healthy,
                    model=self.settings.ollama_model, checkpoint=WorkflowCheckpoint().model_dump(),
                    expires_at=datetime.now(timezone.utc)+timedelta(seconds=WORKFLOW_SECONDS)))
            self.active_id = run_id
            self.task = asyncio.create_task(self._run(run_id))
            return self.get(run_id)
        except Exception:
            self.execution_slot.release(f'workflow:{run_id}')
            raise

    async def resume(self, run_id):
        # Validate durable state before taking the shared slot or starting any network call.
        try:
            with Session(self.engine) as session:
                row = session.get(WorkflowRecord, run_id)
                if row is None or row.status != 'interrupted' or utc(row.expires_at) <= datetime.now(timezone.utc):
                    raise ResumeDenied('Only an interrupted workflow within its original deadline can resume.')
                checkpoint = WorkflowCheckpoint.model_validate(row.checkpoint)
                validate_checkpoint(checkpoint)
                if checkpoint.next_stage == 'done':
                    raise ResumeDenied('This checkpoint is already terminal.')
        except (ValidationError, GroundingError, ValueError, KeyError) as exc:
            raise ResumeDenied('Saved checkpoint validation failed; no work was resumed.') from exc
        self.execution_slot.claim(f'workflow:{run_id}')
        try:
            with Session(self.engine) as session, session.begin():
                row = session.get(WorkflowRecord, run_id)
                if len(row.events) >= 200:
                    raise ResumeDenied('The workflow event budget is exhausted.')
                row.status, row.error, row.finished_at = 'queued', None, None
                row.events = [*row.events, {'sequence': len(row.events)+1, 'at': datetime.now(timezone.utc).isoformat(),
                    'role': checkpoint.next_stage, 'kind': 'resume',
                    'title': 'Explicit resume from validated checkpoint; original deadline and budgets retained',
                    'model_calls': checkpoint.model_calls, 'tool_calls': checkpoint.tool_calls}]
            self.active_id = run_id
            self.task = asyncio.create_task(self._run(run_id))
            return self.get(run_id)
        except Exception:
            self.execution_slot.release(f'workflow:{run_id}')
            raise

    async def _run(self, run_id):
        try:
            run = self.get(run_id)
            with Session(self.engine) as session, session.begin():
                session.get(WorkflowRecord, run_id).status = 'running'
            remaining = (run.expires_at-datetime.now(timezone.utc)).total_seconds()
            async with asyncio.timeout(max(0, remaining)):
                agent = CoordinationAgent(self.provider, self.diagnostics,
                    lambda checkpoint, event: self.save(run_id, checkpoint, event), run.question, run.investigate_healthy)
                result = await agent.run(run.checkpoint)
                validate_checkpoint(result)
            self.finish(run_id, result.outcome)
        except asyncio.CancelledError:
            self.finish(run_id, 'interrupted' if self.closing else 'cancelled',
                'Workflow interrupted; review its checkpoint before explicit resume.' if self.closing
                else 'Workflow cancelled. Evidence retained; no experiment or recovery action was executed.')
        except TimeoutError:
            self.finish(run_id, 'timed_out', 'The original workflow or investigator deadline expired. Partial evidence is retained.')
        except GroundingError as exc:
            self.finish(run_id, 'insufficient_evidence', redact(str(exc), 600))
        except ValidationError:
            self.finish(run_id, 'insufficient_evidence', 'Agent output or checkpoint failed schema validation. Unsupported output was withheld.')
        except (ProviderError, InvestigationFailure, PolicyDenied) as exc:
            self.finish(run_id, 'failed', redact(str(exc), 600))
        except Exception as exc:
            logger.error('Coordinated workflow failed: %s', type(exc).__name__)
            self.finish(run_id, 'failed', 'Workflow failed safely. Review its events and local service availability.')
        finally:
            self.active_id = None
            self.execution_slot.release(f'workflow:{run_id}')

    async def cancel(self, run_id):
        if self.active_id != run_id or self.task is None or self.task.done():
            return False
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            self.finish(run_id, 'interrupted' if self.closing else 'cancelled', 'Workflow stopped before its first stage. No infrastructure was modified.')
            self.active_id = None
            self.execution_slot.release(f'workflow:{run_id}')
        return True

    async def close(self):
        self.closing = True
        if self.active_id:
            await self.cancel(self.active_id)
