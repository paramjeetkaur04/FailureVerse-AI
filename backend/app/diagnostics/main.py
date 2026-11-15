"""Internal diagnostic broker. This process alone receives the Docker socket."""

import asyncio
import os
from typing import Literal

from docker.errors import DockerException
from fastapi import FastAPI, HTTPException

from app.diagnostics.gateway import Denied, DockerGateway
from app.diagnostics.limits import BROKER_REQUEST_SECONDS


def create_broker(gateway=None) -> FastAPI:
    broker = FastAPI(title="FailureVerse restricted diagnostics", docs_url=None, redoc_url=None, openapi_url=None)
    gateway = gateway or DockerGateway(os.environ.get("FV_DEMO_CONTAINER_NAME", "failureverse-ai-demo-app-1"))
    gate = asyncio.Lock()

    @broker.get("/health")
    async def health():
        # Container liveness must not consume the single diagnostic slot.
        return {"status": "ok", "docker": "not_checked"}

    @broker.get("/diagnostics/{target}/{tool}")
    async def diagnostic(target: Literal["demo"], tool: Literal["inspect_container", "container_logs", "container_stats"]):
        if gate.locked():
            raise HTTPException(429, "Another bounded diagnostic is running.")
        async with gate:
            try:
                async with asyncio.timeout(BROKER_REQUEST_SECONDS):
                    return await asyncio.to_thread(gateway.execute, tool)
            except Denied as exc:
                raise HTTPException(403, "Test-container allowlist validation failed.") from exc
            except (DockerException, OSError, TimeoutError) as exc:
                raise HTTPException(503, "Docker diagnostics are unavailable or timed out.") from exc

    return broker


app = create_broker()
