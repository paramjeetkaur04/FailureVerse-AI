import asyncio
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from tests.agent_fixtures import ScriptedProvider, TestDiagnostics


def wait_finished(client, run_id):
    for _ in range(100):
        result = client.get(f"/api/investigations/{run_id}").json()
        if result["status"] not in {"queued", "running"}: return result
        time.sleep(0.02)
    raise AssertionError("Test investigation did not finish")


def test_investigation_api_persists_real_graph_events_and_report(settings, transport):
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=ScriptedProvider(), diagnostic_client=TestDiagnostics())) as client:
        status = client.get("/api/ai/status").json()
        assert status["ready"] and status["limits"] == {"model_calls": 4, "tool_calls": 6, "deadline_seconds": 180}
        response = client.post("/api/investigations", json={"target": "demo", "question": "Investigate collected container observations"})
        assert response.status_code == 202
        result = wait_finished(client, response.json()["id"])
        assert result["status"] == "completed", result
        assert result["model_calls"] == 3 and result["tool_calls"] == 2
        assert len(result["evidence"]) == 3 and result["report"]["grounding_version"] == "2.1"
        assert client.get("/api/investigations").json()[0]["id"] == result["id"]
    with TestClient(create_app(settings, demo_transport=transport)) as restarted:
        assert restarted.get(f'/api/investigations/{result["id"]}').json()["report"] == result["report"]


def test_disabled_invalid_or_untrusted_requests_do_not_start_work(client):
    assert client.post("/api/investigations", json={}).status_code == 503
    assert client.post("/api/investigations", json={"target": "production"}).status_code == 422
    assert client.post("/api/investigations", json={"command": "anything"}).status_code == 422
    assert client.post("/api/investigations", json={}, headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.get(f"/api/investigations/{uuid4()}").status_code == 404
    assert client.get("/api/investigations?limit=51").status_code == 422


def test_single_flight_and_cancellation(settings, transport):
    class Slow(ScriptedProvider):
        async def status(self):
            await asyncio.sleep(5)
            return await super().status()
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=Slow(), diagnostic_client=TestDiagnostics())) as client:
        run = client.post("/api/investigations", json={}).json()
        assert client.post("/api/investigations", json={}).status_code == 409
        cancelled = client.post(f'/api/investigations/{run["id"]}/cancel')
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        assert client.post(f'/api/investigations/{run["id"]}/cancel').status_code == 409


def test_service_deadline_includes_provider_preflight(settings, transport, monkeypatch):
    class Slow(ScriptedProvider):
        async def status(self): await asyncio.sleep(5)
    settings.ai_enabled = True
    monkeypatch.setattr("app.services.investigations.DEADLINE_SECONDS", 0.03)
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=Slow(), diagnostic_client=TestDiagnostics())) as client:
        run = client.post("/api/investigations", json={}).json()
        result = wait_finished(client, run["id"])
        assert result["status"] == "timed_out" and result["model_calls"] == 0


def test_unavailable_ollama_does_not_fabricate_a_report(settings, transport):
    class Offline(ScriptedProvider):
        async def status(self): return {"ready": False, "detail": "Local model missing"}
    settings.ai_enabled = True
    with TestClient(create_app(settings, demo_transport=transport, agent_provider=Offline(), diagnostic_client=TestDiagnostics())) as client:
        run = client.post("/api/investigations", json={}).json()
        result = wait_finished(client, run["id"])
        assert result["status"] == "failed" and result["report"] is None
        assert result["evidence"] == [] and result["model_calls"] == 0
