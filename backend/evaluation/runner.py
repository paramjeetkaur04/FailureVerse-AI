"""Reproducible model/tool evaluation with explicit provenance and denominators."""

import json
from statistics import mean
from time import monotonic

from app.agents.grounding import build_catalog
from app.agents.investigation import InvestigationAgent
from app.tools.diagnostics import PolicyDenied
from evaluation.scenarios import SCENARIOS, observations


class SimulatedDiagnostics:
    def __init__(self, scenario):
        self.data = observations(scenario.id)

    async def execute(self, name, arguments, target="demo"):
        if target != "demo" or name not in self.data or arguments:
            raise PolicyDenied("Evaluation operation was outside its controlled tool set.")
        return {"measurement": "simulated", "observed_at": "2026-11-14T00:00:00Z", "data": self.data[name]}


class ScriptedScenarioProvider:
    """An explicit oracle fixture for regression checks, never a live-model score."""
    def __init__(self, scenario):
        self.scenario = scenario

    async def chat(self, messages, **kwargs):
        if "tools" in kwargs:
            return {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": name, "arguments": {}}} for name in self.scenario.expected_tools]}
        catalog = json.loads(messages[1]["content"])["catalog"]
        chosen = [row["id"] for row in catalog["observations"] if self.scenario.expected_conclusion in row["statement"].lower()]
        if not chosen:
            raise AssertionError("Controlled scenario lacks its expected supported observation.")
        return {"role": "assistant", "content": json.dumps({"observations": chosen[:2],
            "hypotheses": [row["id"] for row in catalog["hypotheses"]][:1],
            "recommendations": [row["id"] for row in catalog["recommendations"]][:1]})}


def score(report, evidence, selected_tools, expected_tools, expected_conclusion):
    catalog = build_catalog(evidence)
    mapping = {"observations": "observations", "suspected_root_causes": "hypotheses",
               "recommended_actions": "recommendations", "limitations": "limitations"}
    existing = {item["id"] for item in evidence}
    references = list(report.get("summary_evidence_ids", []))
    claims = supported = 0
    for field, section in mapping.items():
        for finding in report.get(field, []):
            claims += 1
            references.extend(finding["evidence_ids"])
            expected = catalog.sections[section].get(finding.get("claim_id"))
            supported += int(expected is not None and expected.model_dump() == finding)
    actual, expected = set(selected_tools), set(expected_tools)
    intersection, union = actual & expected, actual | expected
    return {
        "evidence_references": len(references), "valid_evidence_references": sum(ref in existing for ref in references),
        "evidence_citation_validity": sum(ref in existing for ref in references)/len(references) if references else None,
        "reported_claims": claims, "unsupported_claims": claims-supported,
        "unsupported_claim_rate": (claims-supported)/claims if claims else None,
        "tool_selection_accuracy": len(intersection)/len(union) if union else None,
        "tool_precision": len(intersection)/len(actual) if actual else 0,
        "tool_recall": len(intersection)/len(expected) if expected else 0,
        "completion": int(report.get("outcome") == "conclusions" and report.get("model_selection_accepted") is True),
        "acceptable_conclusion": expected_conclusion in " ".join(f["statement"] for f in report.get("observations", [])).lower(),
    }


async def evaluate_scenario(scenario, provider=None):
    events = []
    agent = InvestigationAgent(provider or ScriptedScenarioProvider(scenario), SimulatedDiagnostics(scenario), events.append)
    started = monotonic()
    error, report = None, None
    try:
        report = await agent.run(scenario.question)
    except Exception as exc:
        error = type(exc).__name__
    duration = monotonic()-started
    evidence = [event["evidence"] for event in events if event["kind"] == "observation"]
    selected = [event["tool"] for event in events if event["kind"] == "tool_call"]
    metrics = score(report or {}, evidence, selected, scenario.expected_tools, scenario.expected_conclusion)
    return {"scenario": scenario.id, "question": scenario.question, "expected_observable_evidence_and_conclusions": scenario.description,
            "expected_tools": list(scenario.expected_tools), "selected_tools": selected,
            "diagnostic_provenance": "simulated", "duration_seconds": round(duration, 4),
            "model_calls": agent.budget.model_calls, "tool_calls": agent.budget.tool_calls,
            "selection_rejections": sum("Report validation failed" in event["title"] for event in events),
            "error": error, "metrics": metrics, "report": report, "evidence": evidence}


async def evaluate_all(provider_factory=None):
    rows = []
    for scenario in SCENARIOS:
        rows.append(await evaluate_scenario(scenario, provider_factory(scenario) if provider_factory else None))
    def average(field):
        values = [row["metrics"][field] for row in rows if row["metrics"][field] is not None]
        return mean(values) if values else None
    return {"mode": "simulated_tools_real_ollama" if provider_factory else "simulated_tools_scripted_model",
            "live_docker_tests": False, "scenario_count": len(rows), "summary": {
                "evidence_citation_validity": average("evidence_citation_validity"),
                "unsupported_claim_rate": average("unsupported_claim_rate"),
                "diagnostic_tool_selection_accuracy": average("tool_selection_accuracy"),
                "investigation_completion_rate": average("completion"),
                "acceptable_conclusion_rate": average("acceptable_conclusion"),
                "average_investigation_duration_seconds": mean(row["duration_seconds"] for row in rows),
            }, "scenarios": rows,
            "interpretation": "Scripted-model scores validate deterministic regression behavior, not Ollama accuracy. Unsupported claim rate describes returned source-validated claims; rejected selections are recorded separately. Simulated durations are not live Docker performance."}
