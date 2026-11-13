import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("url", [
    "http://production.example/health", "http://localhost/execute", "http://user:pass@localhost/health",
    "http://localhost/health?command=restart", "http://localhost/health#fragment",
])
def test_target_is_fixed_to_local_demo_health(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, demo_health_url=url)


@pytest.mark.parametrize("kwargs", [
    {"check_timeout_seconds": 0}, {"check_timeout_seconds": 11},
    {"history_limit": 1}, {"history_limit": 1001}, {"database_url": "postgresql://localhost/prod"},
])
def test_invalid_configuration_fails_at_startup(kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)
