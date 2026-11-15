"""Run an actual Ollama/LangGraph/Docker investigation through the deployed local API."""

import argparse
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

from smoke import fetch_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.agents.grounding import build_catalog, validate_report
from app.agents.schemas import InvestigationReport


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", default="http://127.0.0.1:8080")
    parser.add_argument("--output", default="artifacts/phase21/real-investigation.json")
    parser.add_argument("--question", default="Investigate the demo container's actual health. Choose relevant tools, compare their observations, and report suspected issues or the limitations of a healthy snapshot.")
    parser.add_argument("--run-id", type=UUID, help="Revalidate an existing completed investigation without starting another model run")
    args = parser.parse_args()
    if args.run_id:
        created = {"id": str(args.run_id)}
    else:
        _, status = fetch_json(args.frontend, "/api/ai/status")
        assert status["ready"], status
        _, created = fetch_json(args.frontend, "/api/investigations", {
            "target": "demo", "question": args.question,
        })
    started = time.monotonic()
    while time.monotonic()-started < 195:
        _, run = fetch_json(args.frontend, f'/api/investigations/{created["id"]}')
        if args.run_id:
            break
        if run["status"] not in {"queued", "running"}:
            break
        time.sleep(1)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run["verification_elapsed_seconds"] = round(time.monotonic()-started, 2)
    run["verification_mode"] = "revalidate_existing" if args.run_id else "create_live_investigation"
    record = json.dumps(run, indent=2)
    destination.write_text(record, encoding="utf-8")
    destination.with_name(f'investigation-{run["id"]}.json').write_text(record, encoding="utf-8")
    assert run["status"] == "completed", {"status": run["status"], "error": run["error"], "artifact": str(destination)}
    assert 2 <= run["model_calls"] <= 4 and 2 <= run["tool_calls"] <= 6
    assert len({e["tool"] for e in run["evidence"] if e["tool"] != "investigation_scope"}) >= 2
    assert all(e["measurement"] == "actual" for e in run["evidence"])
    assert run["report"] and any(event["kind"] == "decision" for event in run["events"])
    assert run["report"]["grounding_version"] == "2.1" and run["report"]["model_selection_accepted"]
    validate_report(InvestigationReport.model_validate(run["report"]), build_catalog(run["evidence"]))
    duration = (datetime.fromisoformat(run["finished_at"]) - datetime.fromisoformat(run["created_at"])).total_seconds()
    print(json.dumps({"result": "PASS", "verification_mode": run["verification_mode"], "run_id": run["id"], "model": run["model"], "model_calls": run["model_calls"], "tool_calls": run["tool_calls"], "tools": [event["tool"] for event in run["events"] if event["kind"] == "tool_call"], "observations": len([item for item in run["evidence"] if item["tool"] != "investigation_scope"]), "investigation_duration_seconds": round(duration, 2), "elapsed_seconds": run["verification_elapsed_seconds"], "artifact": str(destination)}, indent=2))


if __name__ == "__main__":
    main()
