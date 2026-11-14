"""Controlled observations, NOT measurements from running Docker resources."""

import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    question: str
    expected_tools: tuple[str, ...]
    expected_conclusion: str
    description: str


SCENARIOS = [
    Scenario("healthy", "Check whether the demo container is running and passing its health checks.",
             ("inspect_container", "service_health"), "health status as healthy", "Running container, Docker health healthy, HTTP and SELECT 1 probes healthy; no future-uptime claim."),
    Scenario("stopped", "Investigate an unreachable application: inspect its container state and recent logs.",
             ("inspect_container", "container_logs"), "not running", "Container running=false and state=exited. Stopping reason remains unknown; no restart is executed."),
    Scenario("failed_health", "Investigate a failing container health check and compare it with a fresh HTTP health probe.",
             ("inspect_container", "service_health"), "health status as unhealthy", "Docker health unhealthy and HTTP probe degraded; no invented root cause."),
    Scenario("high_memory", "Investigate memory utilization using resource statistics and container state. Quantify usage versus its limit.",
             ("container_stats", "inspect_container"), "95.00%", "95 MiB used of 100 MiB limit (95%). Memory pressure is a hypothesis, not a proven leak."),
    Scenario("database_failure", "Investigate a database connection/query probe failure using service health probes and recent logs.",
             ("service_health", "container_logs"), "database select 1 probe reported unavailable", "Database query probe unavailable while demo HTTP remains healthy. The exact failure cause is unverified."),
]


def observations(scenario_id):
    data = {
        "inspect_container": {"status": "running", "running": True, "health_status": "healthy", "restart_count": 0},
        "container_logs": {"logs": "GET /health HTTP/1.1 200\n", "truncated": True},
        "container_stats": {"memory_usage_bytes": 64*1048576, "memory_limit_bytes": 128*1048576,
                            "cpu_total_usage_ns": 829232997000, "online_cpus": 4, "cpu_percent": None},
        "service_health": {"services": [{"service": "backend", "status": "healthy"},
            {"service": "database", "status": "healthy"}, {"service": "demo", "status": "healthy"}]},
    }
    if scenario_id == "stopped":
        data["inspect_container"].update(status="exited", running=False)
        data["container_logs"]["logs"] = "Application process exited. Exit cause not recorded.\n"
        data["service_health"]["services"][2]["status"] = "unavailable"
    elif scenario_id == "failed_health":
        data["inspect_container"]["health_status"] = "unhealthy"
        data["service_health"]["services"][2]["status"] = "degraded"
    elif scenario_id == "high_memory":
        data["container_stats"].update(memory_usage_bytes=95*1048576, memory_limit_bytes=100*1048576)
    elif scenario_id == "database_failure":
        data["service_health"]["services"][1]["status"] = "unavailable"
        data["container_logs"]["logs"] = "Database probe connection/query failed; exact cause unavailable.\n"
    return copy.deepcopy(data)
