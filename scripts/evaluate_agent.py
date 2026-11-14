"""Evaluate five controlled scenarios; --ollama uses real inference with simulated tools."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings
from app.services.ollama import OllamaProvider
from evaluation.runner import evaluate_all


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama", action="store_true")
    parser.add_argument("--output", default="artifacts/phase21/evaluation-scripted.json")
    args = parser.parse_args()
    factory = (lambda _: OllamaProvider(Settings())) if args.ollama else None
    result = asyncio.run(evaluate_all(factory))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"mode": result["mode"], "summary": result["summary"], "artifact": str(path)}, indent=2))
    if not args.ollama:
        assert all(row["metrics"]["completion"] and row["metrics"]["acceptable_conclusion"] and not row["metrics"]["unsupported_claims"] for row in result["scenarios"])


if __name__ == "__main__":
    main()
