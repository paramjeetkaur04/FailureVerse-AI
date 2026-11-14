import asyncio

import pytest

from evaluation.runner import evaluate_all, evaluate_scenario
from evaluation.scenarios import SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
def test_controlled_scenarios_have_cited_acceptable_conclusions(scenario):
    result = asyncio.run(evaluate_scenario(scenario))
    assert result["diagnostic_provenance"] == "simulated" and result["error"] is None
    assert all(item["measurement"] == "simulated" for item in result["evidence"])
    assert result["metrics"]["evidence_citation_validity"] == 1
    assert result["metrics"]["unsupported_claim_rate"] == 0
    assert result["metrics"]["tool_selection_accuracy"] == 1
    assert result["metrics"]["completion"] and result["metrics"]["acceptable_conclusion"]


def test_evaluation_summary_preserves_mode_and_denominators():
    result = asyncio.run(evaluate_all())
    assert result["scenario_count"] == 5 and result["live_docker_tests"] is False
    assert result["mode"] == "simulated_tools_scripted_model"
    assert result["summary"]["investigation_completion_rate"] == 1
