"""One bounded background investigation at a time, with durable observable progress."""

import asyncio
import logging
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.investigation import InvestigationAgent, InvestigationFailure
from app.agents.schemas import DEADLINE_SECONDS, RunResponse
from app.core.redaction import redact
from app.models.investigation import InvestigationRecord
from app.services.ollama import ProviderError
from app.tools.diagnostics import PolicyDenied

logger = logging.getLogger(__name__)


class InvestigationBusy(Exception):
    pass


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class InvestigationService:
    def __init__(self, engine, settings, provider, diagnostics):
        self.engine, self.settings = engine, settings
        self.provider, self.diagnostics = provider, diagnostics
        self.task: asyncio.Task | None = None
        self.active_id: str | None = None

    def recover_interrupted(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(update(InvestigationRecord).where(InvestigationRecord.active_slot == 1).values(
                status="interrupted", active_slot=None, finished_at=datetime.now(timezone.utc),
                error="Backend restarted before this investigation finished. Start a new investigation.",
            ))

    def get(self, run_id: str) -> RunResponse | None:
        with Session(self.engine) as session:
            row = session.get(InvestigationRecord, run_id)
            if not row:
                return None
            return RunResponse(
                id=row.id, target=row.target, question=row.question, model=row.model,
                status=row.status, created_at=utc(row.created_at), finished_at=utc(row.finished_at),
                model_calls=row.model_calls, tool_calls=row.tool_calls, report=row.report,
                evidence=row.evidence, error=row.error, events=row.events,
            )

    def list(self, limit: int = 20) -> list[dict]:
        with Session(self.engine) as session:
            rows = session.scalars(select(InvestigationRecord).order_by(InvestigationRecord.created_at.desc()).limit(limit)).all()
            return [{"id": row.id, "question": row.question, "status": row.status, "model": row.model,
                     "created_at": utc(row.created_at).isoformat(), "model_calls": row.model_calls, "tool_calls": row.tool_calls}
                    for row in rows]

    def event(self, run_id: str, event: dict) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(InvestigationRecord, run_id)
            if row is None:
                raise InvestigationFailure("Investigation storage was unavailable.")
            payload = {"sequence": len(row.events)+1, "at": datetime.now(timezone.utc).isoformat(), **event}
            row.events = [*row.events, payload]
            row.model_calls = event.get("model_calls", row.model_calls)
            row.tool_calls = event.get("tool_calls", row.tool_calls)
            if event.get("kind") == "observation":
                row.evidence = [*row.evidence, event["evidence"]]

    def finish(self, run_id: str, status: str, *, report=None, error=None) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(InvestigationRecord, run_id)
            row.status, row.report, row.error = status, report, error
            row.active_slot = None
            row.finished_at = datetime.now(timezone.utc)

    async def start(self, target: str, question: str) -> RunResponse:
        if self.task and not self.task.done():
            raise InvestigationBusy("An investigation is already running.")
        run_id = str(uuid4())
        deadline = monotonic()+DEADLINE_SECONDS
        try:
            with Session(self.engine) as session, session.begin():
                session.add(InvestigationRecord(
                    id=run_id, target=target, question=redact(question, 400),
                    model=self.settings.ollama_model, status="queued", active_slot=1,
                ))
        except IntegrityError as exc:
            raise InvestigationBusy("An investigation is already running.") from exc
        self.active_id = run_id
        self.task = asyncio.create_task(self._run(run_id, redact(question, 400), deadline))
        return self.get(run_id)

    async def _run(self, run_id: str, question: str, deadline: float) -> None:
        try:
            with Session(self.engine) as session, session.begin():
                row = session.get(InvestigationRecord, run_id)
                row.status = "running"
            self.event(run_id, {"kind": "state", "title": "Checking actual local Ollama availability"})
            async with asyncio.timeout(max(0, deadline-monotonic())):
                availability = await self.provider.status()
                if not availability["ready"]:
                    raise ProviderError(availability["detail"])
                agent = InvestigationAgent(self.provider, self.diagnostics, lambda event: self.event(run_id, event))
                report = await agent.run(question)
            self.finish(run_id, "completed" if report["outcome"] == "conclusions" else "insufficient_evidence", report=report)
        except asyncio.CancelledError:
            self.finish(run_id, "cancelled", error="Investigation cancelled. No infrastructure was modified.")
        except TimeoutError:
            self.finish(run_id, "timed_out", error="The 180-second investigation deadline was reached. Partial observations are preserved.")
        except (ProviderError, InvestigationFailure, PolicyDenied) as exc:
            self.finish(run_id, "failed", error=redact(str(exc), 600))
        except Exception as exc:
            logger.error("Investigation failed: %s", type(exc).__name__)
            self.finish(run_id, "failed", error="Investigation failed safely. Review the recorded events and local service availability.")
        finally:
            self.active_id = None

    async def cancel(self, run_id: str) -> bool:
        if self.active_id != run_id or not self.task or self.task.done():
            return False
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            self.finish(run_id, "cancelled", error="Investigation cancelled before inference began.")
            self.active_id = None
        return True

    async def close(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                if self.active_id:
                    self.finish(self.active_id, "cancelled", error="Backend stopped before inference began.")
                    self.active_id = None
