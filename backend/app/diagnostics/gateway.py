"""Privileged boundary: only fixed GET routes and explicitly labeled test resources."""

import re
import struct
from datetime import datetime, timezone
from urllib.parse import urlsplit

import docker

from app.core.redaction import redact


class Denied(Exception):
    pass


class ReadOnlyDockerAPI(docker.APIClient):
    """Deny mutation and unrelated reads at the HTTP transport, not just tool routing."""

    def __init__(self, container_name: str, **kwargs):
        self.allowed_refs = {container_name}
        super().__init__(base_url="unix:///var/run/docker.sock", timeout=4, **kwargs)

    def request(self, method, url, **kwargs):
        path = re.sub(r"^/v\d+\.\d+", "", urlsplit(url).path)
        match = re.fullmatch(r"/containers/([A-Za-z0-9_-]+)/(json|logs|stats)", path)
        if method.upper() != "GET" or not (path == "/version" or (match and match[1] in self.allowed_refs)):
            raise Denied("Docker transport permits only designated read-only diagnostic routes.")
        return super().request(method, url, **kwargs)

    def logs(self, container, **_kwargs):
        """Read bounded Docker frames without the SDK's timeout-disabling log helper."""
        response = self._get(
            self._url("/containers/{0}/logs", container),
            params={"stdout": 1, "stderr": 1, "follow": 0, "tail": 40, "timestamps": 1},
            stream=True, timeout=(2, 3),
        )
        self._raise_for_status(response)

        def chunks():
            remaining = 4097  # One extra byte establishes that the displayed evidence was truncated.
            try:
                while remaining > 0:
                    if getattr(self, "log_tty", False):
                        data = response.raw.read(min(1024, remaining))
                    else:
                        header = response.raw.read(8)
                        if not header:
                            break
                        if len(header) != 8 or header[0] not in (0, 1, 2):
                            raise DockerLogError("Invalid Docker log frame.")
                        length = struct.unpack(">I", header[4:])[0]
                        if length == 0:
                            continue
                        data = response.raw.read(min(length, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
            finally:
                response.close()
        return chunks()


class DockerLogError(docker.errors.DockerException):
    pass


class DockerGateway:
    def __init__(self, container_name: str = "failureverse-ai-demo-app-1", factory=ReadOnlyDockerAPI):
        if not re.fullmatch(r"failureverse-[A-Za-z0-9_-]{1,100}", container_name):
            raise ValueError("The allowlist must name a FailureVerse test resource.")
        self.container_name = container_name
        self.factory = factory

    def execute(self, tool: str) -> dict:
        if tool not in {"inspect_container", "container_logs", "container_stats"}:
            raise Denied("Unregistered diagnostic operation.")
        client = self.factory(self.container_name)
        try:
            inspected = client.inspect_container(self.container_name)
            labels = inspected.get("Config", {}).get("Labels") or {}
            expected = {"io.failureverse.project": "failureverse-ai", "io.failureverse.environment": "test", "io.failureverse.role": "demo"}
            container_id = inspected.get("Id", "")
            if (any(labels.get(key) != value for key, value in expected.items())
                or inspected.get("Name", "").lstrip("/") != self.container_name
                or not re.fullmatch(r"[a-f0-9]{64}", container_id)):
                raise Denied("The target does not match all required test-resource labels and identity.")
            client.allowed_refs.add(container_id)
            client.log_tty = bool(inspected.get("Config", {}).get("Tty", False))
            if tool == "inspect_container":
                state = inspected.get("State", {})
                data = {
                    "container": "demo", "id_prefix": container_id[:12],
                    "status": state.get("Status"), "running": state.get("Running"),
                    "exit_code": state.get("ExitCode"), "oom_killed": state.get("OOMKilled"),
                    "restart_count": inspected.get("RestartCount"),
                    "health_status": state.get("Health", {}).get("Status", "not_configured"),
                }
            elif tool == "container_logs":
                chunks = client.logs(container_id, stdout=True, stderr=True, stream=True, follow=False, tail=40, timestamps=True)
                raw = bytearray()
                truncated = False
                try:
                    for chunk in chunks:
                        if len(raw) + len(chunk) > 4096:
                            raw.extend(chunk[:4096-len(raw)])
                            truncated = True
                            break
                        raw.extend(chunk)
                finally:
                    if hasattr(chunks, "close"):
                        chunks.close()
                data = {"container": "demo", "logs": redact(raw.decode("utf-8", errors="replace"), 4096), "truncated": truncated, "tail_limit": 40}
            else:
                stats = client.stats(container_id, stream=False, one_shot=True)
                memory = stats.get("memory_stats", {})
                cpu = stats.get("cpu_stats", {})
                usage, limit = memory.get("usage"), memory.get("limit")
                valid_usage = isinstance(usage, int) and usage >= 0
                valid_limit = isinstance(limit, int) and limit > 0
                data = {
                    "container": "demo", "memory_usage_bytes": usage,
                    "memory_limit_bytes": limit,
                    "memory_usage_mib": round(usage / 1048576, 2) if valid_usage else None,
                    "memory_limit_mib": round(limit / 1048576, 2) if valid_limit else None,
                    "memory_usage_percent": round(100 * usage / limit, 2) if valid_usage and valid_limit else None,
                    "memory_note": "Actual counter snapshot; one sample cannot establish a memory leak or trend.",
                    "cpu_total_usage_ns": cpu.get("cpu_usage", {}).get("total_usage"),
                    "online_cpus": cpu.get("online_cpus"),
                    "cpu_percent": None, "cpu_note": "Single actual counter sample; utilization percentage requires a time interval.",
                }
            return {"measurement": "actual", "observed_at": datetime.now(timezone.utc).isoformat(), "data": data}
        finally:
            client.close()
