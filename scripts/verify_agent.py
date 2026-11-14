"""Run an actual Ollama/LangGraph/Docker investigation through the deployed local API."""

import argparse
import json
import time
from pathlib import Path

from smoke import fetch_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", default="http://127.0.0.1:8080")
    parser.add_argument("--output", default="artifacts/phase2/real-investigation.json")
    args = parser.parse_args()
    _, status = fetch_json(args.frontend, "/api/ai/status")
    assert status["ready"], status
    _, created = fetch_json(args.frontend, "/api/investigations", {
        "target": "demo", "question": "Investigate the demo container's actual health. Choose relevant tools, compare their observations, and report suspected issues or the limitations of a healthy snapshot.",
    })
    started = time.monotonic()
    while time.monotonic()-started < 195:
        _, run = fetch_json(args.frontend, f'/api/investigations/{created["id"]}')
        if run["status"] not in {"queued", "running"}:
            break
        time.sleep(1)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run["verification_elapsed_seconds"] = round(time.monotonic()-started, 2)
    record = json.dumps(run, indent=2)
    destination.write_text(record, encoding="utf-8")
    destination.with_name(f'investigation-{run["id"]}.json').write_text(record, encoding="utf-8")
    assert run["status"] == "completed", {"status": run["status"], "error": run["error"], "artifact": str(destination)}
    assert 1 <= run["model_calls"] <= 4 and 2 <= run["tool_calls"] <= 6
    assert len({e["tool"] for e in run["evidence"]}) >= 2
    assert all(e["measurement"] == "actual" for e in run["evidence"])
    assert run["report"] and any(event["kind"] == "decision" for event in run["events"])
    print(json.dumps({"result": "PASS", "run_id": run["id"], "model": run["model"], "model_calls": run["model_calls"], "tool_calls": run["tool_calls"], "tools": [e["tool"] for e in run["evidence"]], "elapsed_seconds": run["verification_elapsed_seconds"], "artifact": str(destination)}, indent=2))


if __name__ == "__main__":
    main()
