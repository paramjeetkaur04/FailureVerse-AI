import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import create_app
from app.services.health import CheckBusyError


def test_health_contract_and_security_headers(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy", "version": "0.2.0", "database": "connected", "phase": 2,
    }
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_overview_reports_measured_services_and_no_ai_claims(client):
    body = client.get("/api/overview").json()
    assert body["phase"] == 2
    assert body["healthy_services"] == body["total_services"] == 3
    assert body["saved_checks"] == 1
    assert body["latest"]["source"] == "startup"
    assert body["latest"]["checked_at"].endswith("Z")
    for service in body["latest"]["services"]:
        assert service["measurement"] == "actual"
        assert "cpu" not in service and "prediction" not in service
    database = next(s for s in body["latest"]["services"] if s["id"] == "database")
    assert database["latency_ms"] >= 0


def test_manual_check_persists_and_is_returned_in_history(client):
    created = client.post("/api/checks", json={"source": "manual"})
    assert created.status_code == 201
    record = created.json()
    assert record["source"] == "manual"
    assert len(record["services"]) == 3
    history = client.get("/api/checks?limit=1").json()
    assert history[0]["id"] == record["id"]
    assert len(history) == 1
    assert client.get("/api/overview").json()["saved_checks"] == 2


@pytest.mark.parametrize("limit", [0, 121, -1, "invalid"])
def test_history_query_bounds(client, limit):
    assert client.get(f"/api/checks?limit={limit}").status_code == 422


@pytest.mark.parametrize("body", [
    {"source": "autonomous"}, {"target": "production"}, {"command": "rm -rf /"},
])
def test_check_input_does_not_accept_arbitrary_targets_or_commands(client, body):
    assert client.post("/api/checks", json=body).status_code == 422


def test_public_configuration_never_returns_secrets_or_database_url(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert "must-never-be-returned" not in response.text
    assert "api_key" not in response.text
    assert "database_url" not in response.text
    assert response.json()["ai_enabled"] is False
    assert response.json()["docker_control_enabled"] is False


def test_untrusted_origin_cannot_create_check(client):
    response = client.post("/api/checks", json={}, headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403
    assert client.get("/api/overview").json()["saved_checks"] == 1


def test_cors_accepts_only_configured_origin(client):
    allowed = client.options("/api/checks", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
    })
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.options("/api/checks", headers={
        "Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST",
    })
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_busy_check_returns_conflict_without_duplicate_record(client, monkeypatch):
    async def busy(_source):
        raise CheckBusyError("Already running")
    monkeypatch.setattr(client.app.state.health_service, "collect", busy)
    assert client.post("/api/checks", json={}).status_code == 409


def test_database_readiness_failure_is_explicit(client, monkeypatch):
    def unavailable():
        raise SQLAlchemyError("private storage information")
    monkeypatch.setattr(client.app.state.engine, "connect", unavailable)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert "private" not in response.text


def test_database_query_failure_does_not_leak_details(client, monkeypatch):
    def unavailable(*_args):
        raise SQLAlchemyError("secret connection string")
    monkeypatch.setattr(client.app.state.health_service, "history", unavailable)
    response = client.get("/api/overview")
    assert response.status_code == 503
    assert "secret" not in response.text


def test_metrics_and_openapi_are_available(client):
    client.get("/api/health")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert 'failureverse_http_requests_total{method="GET",route="/api/health",status="200"}' in metrics.text
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/health", "/api/overview", "/api/checks", "/api/config", "/api/ai/status", "/api/investigations", "/api/investigations/{run_id}", "/api/investigations/{run_id}/cancel"}
    assert client.get("/docs").status_code == 200
    assert client.get("/does-not-exist").status_code == 404


@pytest.mark.parametrize("mode", ["offline", "timeout", "bad_json", "oversized", "wrong_app", "list", "http_error", "redirect"])
def test_failed_demo_is_never_reported_as_healthy(settings, mode):
    def handle(request):
        if mode == "offline":
            raise httpx.ConnectError("offline", request=request)
        if mode == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if mode == "bad_json":
            return httpx.Response(200, content="not-json")
        if mode == "oversized":
            return httpx.Response(200, content="x" * 9000)
        if mode == "wrong_app":
            return httpx.Response(200, json={"service": "other", "status": "healthy"})
        if mode == "list":
            return httpx.Response(200, json=[])
        if mode == "redirect":
            return httpx.Response(302, headers={"location": "https://production.example/health"})
        return httpx.Response(503, json={"status": "unhealthy"})
    with TestClient(create_app(settings, demo_transport=httpx.MockTransport(handle))) as api:
        result = api.get("/api/overview").json()
        demo = next(s for s in result["latest"]["services"] if s["id"] == "demo")
        assert demo["status"] in {"degraded", "unavailable"}
        assert result["healthy_services"] == 2
        if demo["status"] == "unavailable":
            assert demo["latency_ms"] is None
        assert api.get("/api/health").status_code == 200


def test_history_survives_backend_restart(settings, transport):
    with TestClient(create_app(settings, demo_transport=transport)) as first:
        record_id = first.post("/api/checks", json={}).json()["id"]
    with TestClient(create_app(settings, demo_transport=transport)) as restarted:
        assert record_id in {record["id"] for record in restarted.get("/api/checks").json()}


def test_retention_is_bounded(settings, transport):
    settings.history_limit = 10
    with TestClient(create_app(settings, demo_transport=transport)) as api:
        for _ in range(14):
            assert api.post("/api/checks", json={}).status_code == 201
        assert api.get("/api/overview").json()["saved_checks"] == 10
