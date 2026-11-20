import asyncio

from evaluation.workflows import evaluate_workflows


def test_five_controlled_workflows_use_simulated_evidence_and_validate_stage_paths():
    report = asyncio.run(evaluate_workflows())
    assert report['mode'] == 'simulated_tools_scripted_model'
    assert len(report['cases']) == 5
    assert report['summary']['completion_rate'] == 1
    assert report['summary']['stage_path_accuracy'] == 1
    assert report['summary']['evidence_citation_validity'] == 1
    for case in report['cases']:
        assert case['source_validation'] and case['measurement'] == 'simulated'
        assert all(item['measurement'] == 'simulated' for item in case['checkpoint']['evidence'])
