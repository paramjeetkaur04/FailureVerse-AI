"""The main API communicates with a restricted broker, never the Docker socket."""

import asyncio
import json

import httpx

from app.agents.schemas import NoArguments, TOOLS
from app.core.config import Settings


class DiagnosticError(Exception):
    pass


class PolicyDenied(DiagnosticError):
    pass


TOOL_SCHEMAS = [{
    "type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
} for name, description in [
    ("inspect_container", "Read actual state, health, restart count and exit information for the designated demo test container. No arguments."),
    ("container_logs", "Read recent bounded, redacted application logs for the designated demo test container. No arguments."),
    ("container_stats", "Read actual memory and CPU counters for the designated demo test container. No arguments."),
    ("service_health", "Run fresh fixed demo HTTP and local database SELECT 1 health probes. No arguments."),
]]


class DiagnosticClient:
    def __init__(self, settings: Settings, transport=None, health_service=None):
        self.settings = settings
        self.transport = transport
        self.health_service = health_service

    async def execute(self, name: str, arguments: dict, target: str = "demo") -> dict:
        if name not in TOOLS or target != "demo":
            raise PolicyDenied("Only registered read-only tools for the demo target are permitted.")
        NoArguments.model_validate(arguments)
        if name == "service_health":
            if self.health_service is None:
                raise DiagnosticError("Fixed service health probes are unavailable in this process.")
            return await self.health_service.investigation_snapshot()
        try:
            async with asyncio.timeout(8), httpx.AsyncClient(
                base_url=str(self.settings.diagnostics_base_url), timeout=6,
                trust_env=False, follow_redirects=False, transport=self.transport,
            ) as client:
                async with client.stream("GET", f"/diagnostics/{target}/{name}") as response:
                    if response.status_code == 403:
                        raise PolicyDenied("The designated container failed allowlist or test-label validation.")
                    if response.status_code != 200:
                        raise DiagnosticError(f"Diagnostic gateway returned HTTP {response.status_code}.")
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 16384:
                            raise DiagnosticError("Diagnostic response exceeded its size limit.")
                    result = json.loads(raw)
                    if not isinstance(result, dict) or result.get("measurement") != "actual" or not isinstance(result.get("data"), dict):
                        raise DiagnosticError("Invalid diagnostic observation.")
                    return result
        except (httpx.HTTPError, TimeoutError, ValueError) as exc:
            raise DiagnosticError("Diagnostic gateway is unavailable or returned an invalid response.") from exc
