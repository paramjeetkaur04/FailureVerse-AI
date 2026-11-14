"""Read-only diagnostic service with fixed targets and bounded network work."""

import asyncio
import json
from datetime import datetime, timezone
from time import perf_counter

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas import CheckResponse, ServiceObservation
from app.core.config import Settings
from app.models.check import CheckRecord


class CheckBusyError(Exception):
    """A bounded check is already running."""


class HealthService:
    def __init__(self, engine: Engine, settings: Settings, transport=None) -> None:
        self.engine = engine
        self.settings = settings
        self.transport = transport
        self._lock = asyncio.Lock()

    async def investigation_snapshot(self) -> dict:
        """Fresh fixed probes without depending on a history-write transaction."""
        def database_probe():
            started = perf_counter()
            try:
                with self.engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                return {"service": "database", "status": "healthy", "latency_ms": round((perf_counter()-started)*1000, 2)}
            except SQLAlchemyError:
                return {"service": "database", "status": "unavailable", "latency_ms": None}
        try:
            async with asyncio.timeout(self.settings.check_timeout_seconds):
                database = await asyncio.to_thread(database_probe)
        except TimeoutError:
            database = {"service": "database", "status": "unavailable", "latency_ms": None}
        demo = await self._demo_observation()
        return {"measurement": "actual", "observed_at": datetime.now(timezone.utc).isoformat(), "data": {"services": [
            {"service": "backend", "status": "healthy", "latency_ms": None}, database,
            {"service": "demo", "status": demo.status, "latency_ms": demo.latency_ms},
        ]}}

    async def collect(self, source: str) -> CheckResponse:
        if self._lock.locked():
            raise CheckBusyError("A service check is already running. Try again shortly.")
        async with self._lock:
            start = perf_counter()
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            db_latency = round((perf_counter() - start) * 1000, 2)
            services = [
                ServiceObservation(
                    id="backend", name="FailureVerse API", kind="api", status="healthy",
                    detail="This backend is responding. Container metrics are not collected in Phase 1.",
                ),
                ServiceObservation(
                    id="database", name="SQLite database", kind="database", status="healthy",
                    latency_ms=db_latency, detail="Measured SELECT 1 query; local persistent storage.",
                ),
                await self._demo_observation(),
            ]
            with Session(self.engine) as session, session.begin():
                record = CheckRecord(source=source, services=[s.model_dump() for s in services])
                session.add(record)
                session.flush()
                result = self.serialize(record)
                # Retention applies to observations; permanent agent audit logs are a future feature.
                retained = select(CheckRecord.id).order_by(
                    CheckRecord.checked_at.desc(), CheckRecord.id.desc()
                ).limit(self.settings.history_limit)
                session.execute(delete(CheckRecord).where(CheckRecord.id.not_in(retained)))
            return result

    async def _demo_observation(self) -> ServiceObservation:
        start = perf_counter()
        try:
            async with asyncio.timeout(self.settings.check_timeout_seconds), httpx.AsyncClient(
                timeout=self.settings.check_timeout_seconds,
                follow_redirects=False, trust_env=False, transport=self.transport,
            ) as client:
                async with client.stream("GET", str(self.settings.demo_health_url)) as response:
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 8192:
                            raise ValueError("Oversized demo health response")
                    latency = round((perf_counter() - start) * 1000, 2)
                    if response.status_code != 200:
                        return ServiceObservation(
                            id="demo", name="Flask demo application", kind="application",
                            status="degraded", latency_ms=latency,
                            detail=f"Demo health endpoint returned HTTP {response.status_code}.",
                        )
                    payload = json.loads(raw)
                    if not isinstance(payload, dict) or payload.get("status") != "healthy" or payload.get("service") != "failureverse-demo":
                        raise ValueError("Unexpected demo health response")
            return ServiceObservation(
                id="demo", name="Flask demo application", kind="application", status="healthy",
                latency_ms=latency, detail="Measured HTTP /health response from the designated demo app.",
            )
        except (httpx.HTTPError, ValueError, TimeoutError):
            return ServiceObservation(
                id="demo", name="Flask demo application", kind="application", status="unavailable",
                detail="Demo health check failed or returned an invalid response. Start the demo app and check again.",
            )

    @staticmethod
    def serialize(record: CheckRecord) -> CheckResponse:
        checked_at = record.checked_at
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        return CheckResponse(
            id=record.id, checked_at=checked_at, source=record.source, services=record.services
        )

    def history(self, limit: int = 30) -> list[CheckResponse]:
        with Session(self.engine) as session:
            rows = session.scalars(select(CheckRecord).order_by(
                CheckRecord.checked_at.desc(), CheckRecord.id.desc()
            ).limit(limit)).all()
            return [self.serialize(row) for row in rows]

    def count(self) -> int:
        with Session(self.engine) as session:
            return session.scalar(select(func.count()).select_from(CheckRecord)) or 0
