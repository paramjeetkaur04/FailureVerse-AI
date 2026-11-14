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
        self.replies = list(replies if replies is not None else [tool("inspect_container"), tool("container_logs"), {"content": json.dumps(report())}])
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
        if name not in {"inspect_container", "container_logs", "container_stats"} or target != "demo":
            raise PolicyDenied("Unapproved operation")
        self.calls.append(name)
        return {"measurement": "actual", "observed_at": datetime.now(timezone.utc).isoformat(), "data": {"running": True, "logs": "test observation"}}
