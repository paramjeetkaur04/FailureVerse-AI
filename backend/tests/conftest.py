import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None, environment="test",
        ai_enabled=False,
        database_url=f"sqlite:///{(tmp_path / 'checks.db').as_posix()}",
        cloud_api_key="must-never-be-returned",
    )


@pytest.fixture
def transport():
    return httpx.MockTransport(lambda request: httpx.Response(
        200, json={"service": "failureverse-demo", "status": "healthy"}
    ))


@pytest.fixture
def client(settings, transport):
    with TestClient(create_app(settings, demo_transport=transport)) as test_client:
        yield test_client
