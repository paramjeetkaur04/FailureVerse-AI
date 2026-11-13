"""Real HTTP to the real Flask WSGI app; API persistence uses a temporary SQLite file."""

import importlib.util
import threading
from pathlib import Path
from wsgiref.simple_server import make_server

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_flask_http_to_fastapi_to_sqlite_round_trip(tmp_path):
    demo_path = Path(__file__).resolve().parents[2] / "demo-app" / "app.py"
    spec = importlib.util.spec_from_file_location("failureverse_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = make_server("127.0.0.1", 0, module.app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings = Settings(
        _env_file=None, environment="test",
        database_url=f"sqlite:///{(tmp_path / 'integration.db').as_posix()}",
        demo_health_url=f"http://127.0.0.1:{server.server_port}/health",
    )
    try:
        with TestClient(create_app(settings)) as client:
            response = client.post("/api/checks", json={})
            assert response.status_code == 201
            demo = next(s for s in response.json()["services"] if s["id"] == "demo")
            assert demo["status"] == "healthy"
            assert demo["latency_ms"] > 0
            assert response.json()["id"] == client.get("/api/checks?limit=1").json()[0]["id"]
            assert client.get("/api/overview").json()["healthy_services"] == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
