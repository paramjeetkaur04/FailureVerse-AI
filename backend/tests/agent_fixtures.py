"""Deterministic test doubles only; production always uses real HTTP services."""
import json
from datetime import datetime, timezone

from app.tools.diagnostics import PolicyDenied


def tool(name, arguments=None):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments or {}}}]}


def report(ids=None):
    refs = ids or ["E1", "E2"]
    return {"summary": "Observed test evidence.", "observations": [{"statement": "The test container is running.", "evidence_ids": refs}],
            "suspected_root_causes": [], "uncertainties": ["A point-in-time snapshot cannot establish future reliability."],
            "recommended_actions": [{"statement": "Continue monitoring.", "evidence_ids": refs}]}


class ScriptedProvider:
    def __init__(self, replies=None):
        self.replies = list(replies if replies is not None else [tool("inspect_container"), tool("container_logs"), {"content": json.dumps(plan())}])
        self.calls = []

    async def status(self):
        return {"ready": True, "state": "ready", "detail": "Test transport", "model": "test-model"}

    async def chat(self, messages, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception): raise reply
        return {"role": "assistant", **reply}


class TestDiagnostics:
    __test__ = False
    def __init__(self): self.calls = []
    async def execute(self, name, arguments, target="demo"):
        if name not in {"inspect_container", "container_logs", "container_stats", "service_health"} or target != "demo":
            raise PolicyDenied("Unapproved operation")
        self.calls.append(name)
        data = {
            "inspect_container": {"running": True, "status": "running", "health_status": "healthy"},
            "container_logs": {"logs": "test observation", "truncated": False},
            "container_stats": {"memory_usage_bytes": 64*1048576, "memory_limit_bytes": 128*1048576, "cpu_total_usage_ns": 123, "cpu_percent": None},
            "service_health": {"services": [{"service": "database", "status": "healthy"}, {"service": "demo", "status": "healthy"}]},
        }[name]
        return {"measurement": "simulated", "observed_at": datetime.now(timezone.utc).isoformat(), "data": data}


def plan(ids=None):
    return {"observations": ids or ["F1"], "hypotheses": [], "recommendations": ["R1"]}
