"""Source-field catalog and validation, independent of any model's interpretation.

The model selects supported findings. Python renders measured facts with exact source
references; free-form generated claims, numbers and confirmed causes are not accepted.
"""

from dataclasses import dataclass, field

from app.agents.metrics import memory_values
from app.agents.schemas import Finding, InvestigationReport, ReportSelection


class GroundingError(ValueError):
    pass


@dataclass
class Catalog:
    evidence: list[dict]
    required_observations: list[str] = field(default_factory=list)
    sections: dict[str, dict[str, Finding]] = field(default_factory=lambda: {
        "observations": {}, "hypotheses": {}, "recommendations": {}, "limitations": {},
    })

    def add(self, section, statement, item, fields):
        prefix = {"observations": "F", "hypotheses": "H", "recommendations": "R", "limitations": "L"}[section]
        key = f"{prefix}{len(self.sections[section])+1}"
        self.sections[section][key] = Finding(statement=statement, evidence_ids=[item["id"]],
            claim_id=key, source_fields=list(dict.fromkeys(f"data.{name}" if name in item["data"] else "data" for name in fields)))

    def prompt(self):
        return {"required_observations": self.required_observations,
                **{section: [{"id": key, "statement": value.statement} for key, value in entries.items()]
                   for section, entries in self.sections.items() if section != "limitations"}}

    def schema(self):
        schema = ReportSelection.model_json_schema()
        for section in ("observations", "hypotheses", "recommendations"):
            options = list(self.sections[section])
            schema["properties"][section]["items"]["enum"] = options or ["UNAVAILABLE"]
            schema["properties"][section]["maxItems"] = min(schema["properties"][section]["maxItems"], len(options))
            if not options:
                schema["properties"][section]["maxItems"] = 0
        schema["properties"]["observations"]["minItems"] = max(1, len(self.required_observations))
        return schema


def build_catalog(evidence: list[dict]) -> Catalog:
    ids = [item["id"] for item in evidence]
    if len(set(ids)) != len(ids):
        raise GroundingError("Duplicate evidence IDs are not allowed.")
    catalog = Catalog(evidence)
    for item in evidence:
        data, tool = item["data"], item["tool"]
        if tool == "inspect_container":
            running, status, health = data.get("running"), data.get("status"), data.get("health_status")
            if type(running) is bool and status in {"running", "exited", "created", "paused", "restarting", "dead", "removing"}:
                catalog.add("observations", f"The demo container was {'running' if running else 'not running'} when inspected (state: {status}).", item, ["running", "status"])
                if not running:
                    catalog.add("hypotheses", "A non-running application container may affect availability; its state reason is unverified.", item, ["running", "status"])
                    catalog.add("recommendations", "Review the recorded container state and authorized application logs before planning any restart.", item, ["running", "status"])
            if health in {"healthy", "unhealthy", "starting", "not_configured"}:
                catalog.add("observations", f"Docker reported the configured container health status as {health}.", item, ["health_status"])
                if health == "unhealthy":
                    catalog.add("hypotheses", "The configured health test may be failing; the underlying application cause is unverified.", item, ["health_status"])
                    catalog.add("recommendations", "Compare the configured health test with a fresh authorized HTTP probe and application logs.", item, ["health_status"])
            catalog.add("limitations", "Container inspection is one snapshot and does not establish future availability or a root cause.", item, ["status"])
        elif tool == "container_stats":
            memory = memory_values(data)
            usage, limit, percent = (memory[key] for key in ("memory_usage_mib", "memory_limit_mib", "memory_usage_percent"))
            if usage is not None:
                catalog.add("observations", f"Recorded memory usage was {usage:.2f} MiB.", item, ["memory_usage_bytes"])
            if percent is not None:
                catalog.add("observations", f"Memory usage was {percent:.2f}% of the {limit:.2f} MiB recorded limit.", item, ["memory_usage_bytes", "memory_limit_bytes"])
                if percent >= 90:
                    catalog.add("hypotheses", "Memory pressure may be relevant at this snapshot; a memory leak has not been established.", item, ["memory_usage_bytes", "memory_limit_bytes"])
                    catalog.add("recommendations", "Collect another bounded memory sample and review workload before attributing the high utilization to a leak.", item, ["memory_usage_bytes", "memory_limit_bytes"])
            else:
                catalog.add("limitations", "A consistent positive memory limit and usage pair was unavailable; memory percentage is withheld.", item, ["memory_usage_bytes", "memory_limit_bytes"])
            cpu = data.get("cpu_total_usage_ns")
            if type(cpu) is int and cpu >= 0:
                catalog.add("observations", f"The cumulative CPU counter was {cpu} nanoseconds; this is not a utilization percentage.", item, ["cpu_total_usage_ns"])
            catalog.add("limitations", "These observations do not establish CPU utilization, CPU stability or memory trends.", item, ["cpu_total_usage_ns", "memory_usage_bytes"])
            catalog.add("recommendations", "Collect timestamped counter samples over an interval before calculating CPU utilization or resource trends.", item, ["cpu_total_usage_ns", "memory_usage_bytes"])
        elif tool == "container_logs":
            logs = data.get("logs")
            if isinstance(logs, str):
                catalog.add("observations", f"The bounded log observation contained {len(logs.splitlines())} returned lines; truncation was {'recorded' if data.get('truncated') is True else 'not reported'}.", item, ["logs", "truncated"])
                catalog.add("limitations", "A bounded log excerpt cannot establish absence of errors, attacks, leaks or suspicious activity.", item, ["logs", "truncated"])
                catalog.add("recommendations", "Review additional authorized logs if the current bounded window does not answer the investigation question.", item, ["logs", "truncated"])
        elif tool == "service_health":
            service, status = data.get("service"), data.get("status")
            if service in {"backend", "database", "demo"} and status in {"healthy", "degraded", "unavailable"}:
                label = {"backend": "Backend investigation process", "database": "Database SELECT 1 probe", "demo": "Demo HTTP health probe"}[service]
                catalog.add("observations", f"{label} reported {status} at collection time.", item, ["service", "status"])
                if status != "healthy":
                    description = "A database connection or query problem" if service == "database" else "An application or connectivity problem"
                    catalog.add("hypotheses", f"{description} may explain the failed probe; the precise cause is unverified.", item, ["service", "status"])
                    catalog.add("recommendations", "Verify the fixed probe target and local service configuration before proposing recovery.", item, ["service", "status"])
                else:
                    catalog.add("recommendations", "Repeat the authorized health probe before making a reliability or recovery decision.", item, ["service", "status"])
        elif tool == "investigation_scope":
            collected = set(data.get("collected_tools", []))
            if "inspect_container" not in collected:
                catalog.add("limitations", "Container running state and Docker health were not inspected in this investigation.", item, ["collected_tools"])
            if "service_health" not in collected:
                catalog.add("limitations", "Fresh HTTP and database health probes were not collected in this investigation.", item, ["collected_tools"])
            catalog.add("limitations", "Disk usage was not measured; no disk utilization conclusion is supported.", item, ["unmeasured_fields"])
    # Required source observations and failure signals must not disappear just
    # because the small model selects the first few benign rows it sees.
    by_id = {item["id"]: item for item in evidence}
    facts = list(catalog.sections["observations"].values())
    scopes = [item["data"] for item in evidence if item["tool"] == "investigation_scope"]
    scope = scopes[-1] if scopes else {}
    required_tools = scope.get("required_tools", [])
    subjects = scope.get("question_subjects", [])
    critical = []
    seen_signals = set()
    for fact in facts:
        item = by_id[fact.evidence_ids[0]]
        data, tool = item["data"], item["tool"]
        fields = fact.source_fields
        signal = None
        if tool == "inspect_container" and data.get("running") is False and "data.running" in fields:
            signal = "not_running"
        elif tool == "inspect_container" and data.get("health_status") == "unhealthy" and "data.health_status" in fields:
            signal = "failed_container_health"
        elif tool == "service_health" and data.get("status") in {"unavailable", "degraded"}:
            signal = f"failed_probe_{data.get('service')}"
        elif tool == "container_stats" and "data.memory_limit_bytes" in fields:
            percent = memory_values(data)["memory_usage_percent"]
            if percent is not None and percent >= 90:
                signal = "high_memory"
        if signal and signal not in seen_signals:
            seen_signals.add(signal)
            critical.append(fact.claim_id)
    required = list(critical)
    for tool in sorted(required_tools):
        candidates = [fact for fact in facts if by_id[fact.evidence_ids[0]]["tool"] == tool]
        if tool == "inspect_container":
            preferred = [fact for fact in candidates if "data.health_status" in fact.source_fields] or candidates
        elif tool == "container_stats":
            preferred = [fact for fact in candidates if "data.memory_limit_bytes" in fact.source_fields] or candidates
        elif tool == "service_health":
            service = "database" if "database" in subjects else "demo"
            preferred = [fact for fact in candidates if by_id[fact.evidence_ids[0]]["data"].get("service") == service] or candidates
        else:
            preferred = candidates
        if preferred and preferred[0].claim_id not in required:
            required.append(preferred[0].claim_id)
    order = required + [fact.claim_id for fact in facts if fact.claim_id not in required]
    renumbered = {}
    mapping = {}
    for index, old_id in enumerate(order, 1):
        key = f"F{index}"
        mapping[old_id] = key
        renumbered[key] = catalog.sections["observations"][old_id].model_copy(update={"claim_id": key})
    catalog.sections["observations"] = renumbered
    catalog.required_observations = [mapping[key] for key in required]
    return catalog


def render_report(selection: ReportSelection | None, catalog: Catalog, *, errors: list[str] | None = None) -> dict:
    notes = errors or []
    chosen = {}
    if selection is not None:
        for section in ("observations", "hypotheses", "recommendations"):
            values = getattr(selection, section)
            if len(set(values)) != len(values):
                raise GroundingError("Duplicate finding selections are not allowed.")
            if any(key not in catalog.sections[section] for key in values):
                raise GroundingError("A selected finding does not exist in its supported evidence category.")
            chosen[section] = [catalog.sections[section][key] for key in values]
        if not set(catalog.required_observations).issubset(selection.observations):
            raise GroundingError("The selection omitted required source observations: " + ", ".join(catalog.required_observations))
    else:
        chosen = {"observations": list(catalog.sections["observations"].values())[:4], "hypotheses": [],
                  "recommendations": list(catalog.sections["recommendations"].values())[:1]}
    sufficient = selection is not None and bool(chosen["observations"])
    facts = chosen["observations"]
    summary = " ".join(f.statement for f in facts[:2]) if sufficient else "Insufficient evidence for a validated model-selected conclusion; unvalidated claims were withheld."
    limitations = list(catalog.sections["limitations"].values())
    report = InvestigationReport(summary=summary, observations=facts,
        suspected_root_causes=chosen["hypotheses"], recommended_actions=chosen["recommendations"],
        uncertainties=[f"{item.statement} [{', '.join(item.evidence_ids)}]" for item in limitations][:6] or ["Only the collected snapshot is supported."],
        grounding_version="2.1", outcome="conclusions" if sufficient else "insufficient_evidence",
        summary_evidence_ids=list(dict.fromkeys(eid for fact in facts[:2] for eid in fact.evidence_ids)) if sufficient else [],
        limitations=limitations, model_selection_accepted=sufficient, validation_notes=notes)
    validate_report(report, catalog)
    return report.model_dump()


def validate_report(report: InvestigationReport, catalog: Catalog) -> None:
    if report.grounding_version != "2.1":
        raise GroundingError("Legacy reports do not have source-field validation.")
    if report.model_selection_accepted != (report.outcome == "conclusions"):
        raise GroundingError("Report outcome and model-selection status disagree.")
    if report.limitations != list(catalog.sections["limitations"].values()):
        raise GroundingError("Required evidence limitations cannot be omitted or changed.")
    evidence_ids = {item["id"] for item in catalog.evidence}
    sections = {"observations": report.observations, "hypotheses": report.suspected_root_causes,
                "recommendations": report.recommended_actions, "limitations": report.limitations}
    for section, findings in sections.items():
        if len({finding.claim_id for finding in findings}) != len(findings):
            raise GroundingError("Duplicate report claims are not allowed.")
        for finding in findings:
            expected = catalog.sections[section].get(finding.claim_id)
            if expected is None or finding != expected or not set(finding.evidence_ids).issubset(evidence_ids):
                raise GroundingError("A claim, quantity, source field or evidence citation differs from its supported observation.")
    if report.outcome == "conclusions":
        if not set(catalog.required_observations).issubset(item.claim_id for item in report.observations):
            raise GroundingError("A required observation or observed failure was omitted.")
        if not report.observations or not report.recommended_actions:
            raise GroundingError("A validated conclusion requires supported observations and a recommendation.")
        expected_summary = " ".join(item.statement for item in report.observations[:2])
        expected_ids = list(dict.fromkeys(eid for item in report.observations[:2] for eid in item.evidence_ids))
        if report.summary != expected_summary or report.summary_evidence_ids != expected_ids:
            raise GroundingError("Summary claims must match the cited selected observations.")
    elif report.summary != "Insufficient evidence for a validated model-selected conclusion; unvalidated claims were withheld." or report.summary_evidence_ids:
        raise GroundingError("An insufficient-evidence result cannot introduce a factual conclusion.")
    expected_uncertainties = [f"{item.statement} [{', '.join(item.evidence_ids)}]" for item in report.limitations][:6] or ["Only the collected snapshot is supported."]
    if report.uncertainties != expected_uncertainties:
        raise GroundingError("Uncertainty statements must match their cited limitations.")
