"""Verify actual deployed Phase 3 monitoring or Ollama-to-Docker coordination."""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from smoke import fetch_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.agents.coordination_catalog import validate_checkpoint
from app.agents.coordination_schemas import WorkflowResponse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend', default='http://127.0.0.1:8080')
    parser.add_argument('--investigate-healthy', action='store_true', help='Explicitly exercise all stages against healthy actual resources')
    parser.add_argument('--run-id', type=UUID, help='Revalidate an existing terminal workflow without creating work')
    parser.add_argument('--output', default='artifacts/phase3/real-workflow.json')
    args = parser.parse_args()
    target = urlsplit(args.frontend)
    if target.scheme != 'http' or target.hostname not in {'localhost', '127.0.0.1', '::1'} or target.username or target.password:
        raise SystemExit('The live verifier accepts only loopback HTTP origins.')
    if args.run_id:
        run_id = str(args.run_id)
    else:
        _, created = fetch_json(args.frontend, '/api/workflows', {
            'target': 'demo', 'question': 'Investigate current demo container health.', 'investigate_healthy': args.investigate_healthy,
        })
        run_id = created['id']
    started = time.monotonic()
    while True:
        _, raw = fetch_json(args.frontend, f'/api/workflows/{run_id}')
        if args.run_id or raw['status'] not in {'queued', 'running'} or time.monotonic()-started >= 315:
            break
        time.sleep(1)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw['verification_elapsed_seconds'] = round(time.monotonic()-started, 2)
    payload = json.dumps(raw, indent=2)
    output.write_text(payload, encoding='utf-8')
    output.with_name(f'workflow-{run_id}.json').write_text(payload, encoding='utf-8')
    parsed = {key: value for key, value in raw.items() if key != 'verification_elapsed_seconds'}
    run = WorkflowResponse.model_validate(parsed)
    validate_checkpoint(run.checkpoint)
    assert run.status in {'observed_healthy', 'awaiting_review'}, {'status': run.status, 'error': run.error, 'artifact': str(output)}
    assert run.checkpoint.outcome == run.status and run.execution_enabled is False
    assert run.checkpoint.evidence and all(item.measurement == 'actual' for item in run.checkpoint.evidence)
    if args.investigate_healthy:
        assert run.status == 'awaiting_review'
    if run.status == 'awaiting_review':
        assert run.checkpoint.investigation.model_selection_accepted
        assert run.checkpoint.role_models.get('simulation', 0) >= 1 and run.checkpoint.role_models.get('recovery', 0) >= 1
        assert run.checkpoint.role_models.get('risk', 0) == 0
        assert set(run.checkpoint.specialists) == {'simulation', 'risk', 'recovery'}
    duration = (run.finished_at-run.created_at).total_seconds()
    print(json.dumps({'result': 'PASS', 'run_id': run.id, 'status': run.status,
        'model_calls': run.checkpoint.model_calls, 'tool_calls': run.checkpoint.tool_calls,
        'observations': len(run.checkpoint.evidence), 'duration_seconds': round(duration, 2),
        'execution_enabled': run.execution_enabled, 'artifact': str(output)}, indent=2))


if __name__ == '__main__':
    main()
