import copy
import io
import struct

import pytest
from fastapi.testclient import TestClient

from app.core.redaction import redact
from app.diagnostics.gateway import Denied, DockerGateway, ReadOnlyDockerAPI
from app.diagnostics.main import create_broker


class FakeDocker:
    def __init__(self):
        self.allowed_refs = set()
        self.calls = []
        self.info = {"Id": "a"*64, "Name": "/failureverse-ai-demo-app-1", "State": {"Running": True, "Status": "running", "Health": {"Status": "healthy"}}, "RestartCount": 0,
                     "Config": {"Env": ["PASSWORD=must-not-leak"], "Labels": {"io.failureverse.project": "failureverse-ai", "io.failureverse.environment": "test", "io.failureverse.role": "demo"}}}
    def inspect_container(self, name): self.calls.append("inspect"); return copy.deepcopy(self.info)
    def logs(self, *args, **kwargs): self.calls.append("logs"); return iter([b'password="hidden-value"\n'+b'x'*5000])
    def stats(self, *args, **kwargs): self.calls.append("stats"); return {"memory_stats": {"usage": 123, "limit": 1024}, "cpu_stats": {"cpu_usage": {"total_usage": 456}}}
    def close(self): pass


@pytest.mark.parametrize("key", ["io.failureverse.project", "io.failureverse.environment", "io.failureverse.role"])
def test_all_test_labels_are_required_before_reading_logs(key):
    fake = FakeDocker()
    fake.info["Config"]["Labels"][key] = "production"
    with pytest.raises(Denied): DockerGateway(factory=lambda _: fake).execute("container_logs")
    assert fake.calls == ["inspect"]


def test_inspect_does_not_return_environment_or_host_details():
    result = DockerGateway(factory=lambda _: FakeDocker()).execute("inspect_container")
    assert result["measurement"] == "actual" and result["data"]["running"]
    assert "must-not-leak" not in str(result) and "Config" not in result


def test_logs_are_bounded_and_redacted():
    result = DockerGateway(factory=lambda _: FakeDocker()).execute("container_logs")
    assert result["data"]["truncated"] and len(result["data"]["logs"]) <= 4096
    assert "hidden-value" not in result["data"]["logs"]


def test_stats_do_not_fabricate_cpu_utilization():
    result = DockerGateway(factory=lambda _: FakeDocker()).execute("container_stats")
    assert result["data"]["memory_usage_bytes"] == 123
    assert result["data"]["cpu_percent"] is None


def test_memory_units_are_derived_from_actual_counters_with_zero_limit_unavailable():
    fake = FakeDocker()
    fake.stats = lambda *a, **kw: {"memory_stats": {"usage": 64 * 1048576, "limit": 128 * 1048576}}
    data = DockerGateway(factory=lambda _: fake).execute("container_stats")["data"]
    assert data["memory_usage_mib"] == 64 and data["memory_limit_mib"] == 128
    assert data["memory_usage_percent"] == 50
    fake.stats = lambda *a, **kw: {"memory_stats": {"usage": 64 * 1048576, "limit": 0}}
    data = DockerGateway(factory=lambda _: fake).execute("container_stats")["data"]
    assert data["memory_usage_percent"] is None and data["memory_limit_mib"] is None


@pytest.mark.parametrize("method,path", [("POST", "/containers/demo/stop"), ("DELETE", "/containers/demo"), ("GET", "/containers/other/json"), ("GET", "/containers/demo/archive"), ("GET", "/info")])
def test_docker_transport_denies_unregistered_reads_and_all_mutations(method, path):
    client = ReadOnlyDockerAPI("failureverse-ai-demo-app-1", version="1.45")
    try:
        with pytest.raises(Denied): client.request(method, "http+docker://localhost/v1.45"+path)
    finally: client.close()


def test_broker_has_no_mutation_route_and_rejects_arbitrary_targets():
    with TestClient(create_broker(DockerGateway(factory=lambda _: FakeDocker()))) as client:
        assert client.post("/diagnostics/demo/inspect_container").status_code == 405
        assert client.get("/diagnostics/production/inspect_container").status_code == 422
        assert client.get("/diagnostics/demo/exec").status_code == 422
        assert client.get("/diagnostics/demo/inspect_container").status_code == 200


def test_broker_liveness_does_not_consume_docker_diagnostic_slot():
    class UnavailableDocker:
        def execute(self, tool):
            raise AssertionError("Liveness must not perform a Docker diagnostic")
    with TestClient(create_broker(UnavailableDocker())) as client:
        assert client.get("/health").json() == {"status": "ok", "docker": "not_checked"}


def test_bounded_sdk_log_reader_demultiplexes_and_closes_without_disabling_timeout(monkeypatch):
    client = ReadOnlyDockerAPI("failureverse-ai-demo-app-1", version="1.45")
    class Response:
        status_code = 200
        closed = False
        raw = io.BytesIO(struct.pack(">BxxxI", 1, 3)+b"one"+struct.pack(">BxxxI", 2, 6000)+b"x"*6000)
        def raise_for_status(self): pass
        def close(self): self.closed = True
    response = Response()
    seen = []
    def get(_url, **kwargs): seen.append(kwargs); return response
    monkeypatch.setattr(client, "_get", get)
    try:
        output = b"".join(client.logs("failureverse-ai-demo-app-1"))
        assert output.startswith(b"one") and len(output) == 4097
        assert response.closed and seen[0]["timeout"] == (2, 3)
        assert seen[0]["params"]["follow"] == 0
    finally: client.close()


@pytest.mark.parametrize("value,secret", [('"password": "hunter-two"', 'hunter-two'), ('Authorization: Bearer bearer-secret', 'bearer-secret'), ('postgres://user:dbsecret@localhost/db', 'dbsecret'), ('-----BEGIN PRIVATE KEY-----\nprivate-material', 'private-material')])
def test_redaction_handles_quoted_values_urls_and_incomplete_keys(value, secret):
    assert secret not in redact(value)
