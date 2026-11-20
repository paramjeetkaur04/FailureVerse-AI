import asyncio
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import create_app
from app.models.workflow import WorkflowRecord
from tests.workflow_fixtures import WorkflowDiagnostics, WorkflowProvider


def finished(client, run_id):
    for _ in range(200):
        response = client.get(f'/api/workflows/{run_id}')
        assert response.status_code == 200, response.text
        result = response.json()
        if result['status'] not in {'queued', 'running'}:
            return result
        time.sleep(0.01)
    raise AssertionError('Controlled workflow did not finish')


def test_workflow_api_persists_planning_and_preserves_legacy_health_data(settings, transport):
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=WorkflowProvider(), diagnostic_client=WorkflowDiagnostics())) as client:
        old_check = client.get('/api/checks').json()[0]['id']
        response = client.post('/api/workflows', json={'investigate_healthy': True})
        assert response.status_code == 202
        run = finished(client, response.json()['id'])
        assert run['status'] == 'awaiting_review', run
        assert run['execution_enabled'] is False
        assert client.get('/api/workflows').json()[0]['id'] == run['id']
    with TestClient(create_app(settings, demo_transport=transport)) as restarted:
        saved = restarted.get(f'/api/workflows/{run["id"]}').json()
        assert saved['checkpoint'] == run['checkpoint']
        assert old_check in {item['id'] for item in restarted.get('/api/checks').json()}
        with restarted.app.state.engine.connect() as connection:
            assert connection.execute(text('SELECT COUNT(*) FROM schema_versions WHERE version=1')).scalar() == 1


def test_workflow_api_rejects_unknown_targets_actions_and_untrusted_origins(client):
    assert client.post('/api/workflows', json={}).status_code == 503
    assert client.post('/api/workflows', json={'target': 'production'}).status_code == 422
    assert client.post('/api/workflows', json={'command': 'anything'}).status_code == 422
    assert client.post('/api/workflows', json={}, headers={'Origin': 'https://untrusted.example'}).status_code == 403
    assert client.post('/api/workflows/00000000-0000-0000-0000-000000000000/execute').status_code == 404
    assert client.get('/api/workflows?limit=51').status_code == 422


def test_shared_execution_slot_excludes_legacy_and_coordinated_work(settings, transport):
    class Slow(WorkflowDiagnostics):
        async def execute(self, *args, **kwargs):
            await asyncio.sleep(5)
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=WorkflowProvider(), diagnostic_client=Slow())) as client:
        created = client.post('/api/workflows', json={}).json()
        assert client.post('/api/investigations', json={}).status_code == 409
        assert client.post('/api/workflows', json={}).status_code == 409
        assert client.get('/api/ai/status').json()['active_workflow_id'] == created['id']
        assert client.post(f'/api/workflows/{created["id"]}/cancel').json()['status'] == 'cancelled'
        assert client.post(f'/api/workflows/{created["id"]}/resume').status_code == 409
        legacy = client.post('/api/investigations', json={})
        assert legacy.status_code == 202
        assert client.post('/api/workflows', json={}).status_code == 409
        assert client.post(f'/api/investigations/{legacy.json()["id"]}/cancel').status_code == 200
        assert client.post('/api/workflows', json={}).status_code == 202


def test_restart_resume_reuses_completed_stages_and_consumed_budgets(settings, transport):
    class InterruptedPlanner(WorkflowProvider):
        async def chat(self, messages, **kwargs):
            if 'ids' in kwargs.get('schema', {}).get('properties', {}):
                await asyncio.sleep(5)
            return await super().chat(messages, **kwargs)
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=InterruptedPlanner(), diagnostic_client=WorkflowDiagnostics())) as client:
        created = client.post('/api/workflows', json={'investigate_healthy': True}).json()
        for _ in range(200):
            saved = client.get(f'/api/workflows/{created["id"]}').json()
            if saved['checkpoint']['role_models'].get('simulation') == 1:
                break
            time.sleep(0.01)
        assert saved['checkpoint']['next_stage'] == 'simulation'
    provider, diagnostics = WorkflowProvider(), WorkflowDiagnostics()
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=provider, diagnostic_client=diagnostics)) as client:
        interrupted = client.get(f'/api/workflows/{created["id"]}').json()
        assert interrupted['status'] == 'interrupted' and interrupted['resumable']
        assert client.post(f'/api/workflows/{created["id"]}/resume').status_code == 202
        result = finished(client, created['id'])
        assert result['status'] == 'awaiting_review', result
        assert result['expires_at'] == created['expires_at']
        assert result['checkpoint']['model_calls'] == saved['checkpoint']['model_calls']+2
        assert result['checkpoint']['tool_calls'] == saved['checkpoint']['tool_calls']
        assert result['checkpoint']['role_models']['simulation'] == 2
        assert diagnostics.calls == [] and all('tools' not in call for call in provider.calls)


def test_expired_and_corrupt_checkpoints_cannot_resume(settings, transport):
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=WorkflowProvider(), diagnostic_client=WorkflowDiagnostics())) as client:
        created = client.post('/api/workflows', json={}).json()
        finished(client, created['id'])
        with Session(client.app.state.engine) as session, session.begin():
            row = session.get(WorkflowRecord, created['id'])
            row.status = 'interrupted'
            row.expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
        assert client.post(f'/api/workflows/{created["id"]}/resume').status_code == 409
        with Session(client.app.state.engine) as session, session.begin():
            row = session.get(WorkflowRecord, created['id'])
            row.expires_at = datetime.now(timezone.utc)+timedelta(seconds=100)
            cp = dict(row.checkpoint)
            cp['model_calls'] = 99
            row.checkpoint = cp
        assert client.post(f'/api/workflows/{created["id"]}/resume').status_code == 409
        assert client.get(f'/api/workflows/{created["id"]}').status_code == 503


def test_workflow_deadline_includes_monitoring(settings, transport, monkeypatch):
    class Slow(WorkflowDiagnostics):
        async def execute(self, *args, **kwargs):
            await asyncio.sleep(5)
    monkeypatch.setattr('app.services.workflows.WORKFLOW_SECONDS', 0.03)
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=WorkflowProvider(), diagnostic_client=Slow())) as client:
        created = client.post('/api/workflows', json={}).json()
        assert finished(client, created['id'])['status'] == 'timed_out'


def test_resume_investigator_reuses_evidence_and_original_stage_deadline(settings, transport):
    class InterruptedReport(WorkflowProvider):
        async def chat(self, messages, **kwargs):
            if 'observations' in kwargs.get('schema', {}).get('properties', {}):
                await asyncio.sleep(5)
            return await super().chat(messages, **kwargs)
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=InterruptedReport(), diagnostic_client=WorkflowDiagnostics())) as client:
        created = client.post('/api/workflows', json={'investigate_healthy': True}).json()
        for _ in range(200):
            saved = client.get(f'/api/workflows/{created["id"]}').json()
            if saved['checkpoint']['role_models'].get('investigation') == 2:
                break
            time.sleep(0.01)
        assert saved['checkpoint']['investigation_evidence']
    provider, diagnostics = WorkflowProvider(), WorkflowDiagnostics()
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=provider, diagnostic_client=diagnostics)) as client:
        assert client.post(f'/api/workflows/{created["id"]}/resume').status_code == 202
        result = finished(client, created['id'])
        assert result['status'] == 'awaiting_review', result
        assert result['checkpoint']['investigation_expires_at'] == saved['checkpoint']['investigation_expires_at']
        assert result['checkpoint']['role_models']['investigation'] == 3
        assert diagnostics.calls == [] and all('tools' not in call for call in provider.calls)


def test_malformed_specialist_output_withholds_plan_without_echoing_output(settings, transport):
    class InvalidPlanner(WorkflowProvider):
        async def chat(self, messages, **kwargs):
            if 'ids' in kwargs.get('schema', {}).get('properties', {}):
                return {'content': '{"ids":["invented"],"private":"private-model-material"}'}
            return await super().chat(messages, **kwargs)
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=InvalidPlanner(), diagnostic_client=WorkflowDiagnostics())) as client:
        created = client.post('/api/workflows', json={'investigate_healthy': True}).json()
        result = finished(client, created['id'])
        assert result['status'] == 'insufficient_evidence' and result['checkpoint']['specialists'] == {}
        assert 'private-model-material' not in result['error']


def test_unavailable_provider_after_monitoring_fails_visibly_with_no_model_calls(settings, transport):
    class Offline(WorkflowProvider):
        async def status(self):
            self.status_calls += 1
            return {'ready': False, 'state': 'unavailable', 'detail': 'Simulated local provider unavailable'}
    settings.ai_enabled = True
    provider = Offline()
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=provider, diagnostic_client=WorkflowDiagnostics())) as client:
        created = client.post('/api/workflows', json={'investigate_healthy': True}).json()
        result = finished(client, created['id'])
        assert result['status'] == 'failed' and 'unavailable' in result['error']
        assert result['checkpoint']['model_calls'] == 0 and result['checkpoint']['tool_calls'] == 3
        assert provider.status_calls == 2
