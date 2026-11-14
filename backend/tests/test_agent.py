import asyncio
import json

import pytest

from app.agents.investigation import InvestigationAgent, InvestigationFailure, ReportGroundingError, validate_quantities
from app.agents.schemas import InvestigationReport
from app.services.ollama import ProviderError
from app.tools.diagnostics import PolicyDenied
from tests.agent_fixtures import ScriptedProvider, TestDiagnostics, report, plan, tool


def invoke(provider=None, diagnostics=None):
    events = []
    agent = InvestigationAgent(provider or ScriptedProvider(), diagnostics or TestDiagnostics(), events.append)
    result = asyncio.run(agent.run("Investigate this test container"))
    return agent, result, events


def test_real_langgraph_loop_uses_model_selected_tools_and_validates_report():
    diagnostics = TestDiagnostics()
    agent, result, events = invoke(diagnostics=diagnostics)
    assert diagnostics.calls == ["inspect_container", "container_logs"]
    assert agent.budget.model_calls == 3 and agent.budget.tool_calls == 2
    observations = [e["evidence"] for e in events if e["kind"] == "observation"]
    assert result["observations"][0]["evidence_ids"] == [observations[0]["id"]]
    assert len({item["id"] for item in observations}) == 3
    assert result["grounding_version"] == "2.1" and result["summary_evidence_ids"]


def test_six_tool_call_ceiling_is_enforced():
    first = {"tool_calls": [tool("inspect_container")["tool_calls"][0]] * 3}
    second = {"tool_calls": [tool("container_logs")["tool_calls"][0]] * 3}
    provider = ScriptedProvider([first, second, {"content": json.dumps(plan())}])
    agent, _, _ = invoke(provider)
    assert agent.budget.tool_calls == 6 and agent.budget.model_calls == 3


def test_unknown_evidence_ids_are_rejected_within_four_model_calls():
    two = {"tool_calls": [tool("inspect_container")["tool_calls"][0], tool("container_logs")["tool_calls"][0]]}
    provider = ScriptedProvider([two, {"content": json.dumps(plan(["F999"]))}, {"content": json.dumps(plan(["F999"]))}])
    _, result, _ = invoke(provider)
    assert result["outcome"] == "insufficient_evidence" and not result["model_selection_accepted"]
    assert len(provider.calls) == 3


def test_model_cannot_execute_mutation_tool():
    diagnostics = TestDiagnostics()
    with pytest.raises(PolicyDenied): invoke(ScriptedProvider([tool("restart_container")]), diagnostics)
    assert diagnostics.calls == []


def test_tool_arguments_cannot_smuggle_commands():
    bad = tool("container_logs", {"command": "anything"})
    provider = ScriptedProvider([bad, bad, bad])
    diagnostics = TestDiagnostics()
    _, result, _ = invoke(provider, diagnostics)
    assert result["outcome"] == "insufficient_evidence"
    assert diagnostics.calls == []


def test_invalid_arguments_explain_empty_schema_and_allow_model_to_correct():
    two = {"tool_calls": [tool("inspect_container")["tool_calls"][0], tool("container_logs")["tool_calls"][0]]}
    class CorrectingProvider(ScriptedProvider):
        async def chat(self, messages, **kwargs):
            if len(self.calls) == 1:
                feedback = json.loads(next(message["content"] for message in reversed(messages) if message["role"] == "tool"))
                assert "empty JSON object {}" in feedback["error"]
            return await super().chat(messages, **kwargs)
    provider = CorrectingProvider([tool("container_logs", {"target": "demo"}), two, {"content": json.dumps(plan())}])
    diagnostics = TestDiagnostics()
    agent, _, events = invoke(provider, diagnostics)
    assert diagnostics.calls == ["inspect_container", "container_logs"]
    assert agent.budget.tool_calls == 3
    assert any("invalid diagnostic arguments" in event["title"] for event in events)


def test_two_model_selected_tools_proceed_directly_to_structured_reporting():
    two = {"tool_calls": [tool("inspect_container")["tool_calls"][0], tool("container_logs")["tool_calls"][0]]}
    provider = ScriptedProvider([two, {"content": json.dumps(plan())}])
    agent, result, _ = invoke(provider)
    assert agent.budget.model_calls == 2 and result["observations"]
    assert "tools" in provider.calls[0] and "schema" in provider.calls[1]


def test_provider_failures_have_only_one_retry():
    provider = ScriptedProvider([ProviderError("offline"), ProviderError("offline")])
    with pytest.raises(ProviderError): invoke(provider)
    assert len(provider.calls) == 2


def test_deadline_cancels_inference(monkeypatch):
    class Slow(ScriptedProvider):
        async def chat(self, *args, **kwargs): await asyncio.sleep(5)
    monkeypatch.setattr("app.agents.investigation.DEADLINE_SECONDS", 0.02)
    with pytest.raises(TimeoutError): invoke(Slow())


def test_no_tools_does_not_produce_fake_report():
    _, result, _ = invoke(ScriptedProvider([{"content": "I assume healthy"}]*3))
    assert result["outcome"] == "insufficient_evidence"
    assert result["observations"] == [] and result["recommended_actions"] == []


@pytest.mark.parametrize("claim", ["CPU usage 100%", "Memory usage is high (611MB)"])
def test_real_run_unsupported_quantities_are_rejected(claim):
    data = report()
    data["summary"] = claim
    evidence = [{"tool": "container_stats", "data": {"memory_usage_bytes": 61136896, "memory_limit_bytes": 134217728, "cpu_percent": None}}]
    with pytest.raises(ReportGroundingError):
        validate_quantities(InvestigationReport.model_validate(data), evidence)


def test_actual_memory_quantities_accept_consistent_units_and_rounding():
    data = report()
    data["summary"] = "Memory usage is 58.3 MiB (61.14 MB) under the 128 MiB limit. CPU utilization is unavailable."
    evidence = [{"tool": "container_stats", "data": {"memory_usage_bytes": 61136896, "memory_limit_bytes": 134217728, "cpu_percent": None}}]
    validate_quantities(InvestigationReport.model_validate(data), evidence)


@pytest.mark.parametrize("calls", [[{"function": "bad"}], ["bad"], "bad"])
def test_malformed_native_tool_selections_fail_with_a_clear_error(calls):
    with pytest.raises(InvestigationFailure, match="native tool calls"):
        invoke(ScriptedProvider([{"tool_calls": calls}]))


def test_malformed_diagnostic_evidence_does_not_produce_observations():
    class BrokenDiagnostics(TestDiagnostics):
        async def execute(self, *args, **kwargs):
            return {"measurement": "actual", "observed_at": "not-a-timestamp", "data": {}}
    provider = ScriptedProvider([tool("container_logs")]*3)
    _, result, events = invoke(provider, BrokenDiagnostics())
    assert result["outcome"] == "insufficient_evidence" and result["observations"] == []
    assert all(event["evidence"]["tool"] == "investigation_scope" for event in events if event["kind"] == "observation")


def test_health_question_requires_inspection_and_service_probes_within_existing_budget():
    provider = ScriptedProvider([tool("inspect_container"), tool("container_logs"), tool("container_logs")])
    agent = InvestigationAgent(provider, TestDiagnostics(), lambda _: None)
    result = asyncio.run(agent.run("Investigate current demo container health"))
    assert result["outcome"] == "insufficient_evidence" and agent.budget.model_calls == 3
    assert "service_health" in result["validation_notes"][0]


def test_unmeasured_disk_question_returns_insufficient_evidence_without_disk_numbers():
    two = {"tool_calls": [tool("inspect_container")["tool_calls"][0], tool("container_logs")["tool_calls"][0]]}
    agent = InvestigationAgent(ScriptedProvider([two]), TestDiagnostics(), lambda _: None)
    result = asyncio.run(agent.run("What is the disk utilization?"))
    assert result["outcome"] == "insufficient_evidence"
    assert all("disk" not in item["statement"].lower() for item in result["observations"])
