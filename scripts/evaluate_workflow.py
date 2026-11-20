"""Controlled Phase 3 evaluation; simulated diagnostics never touch Docker."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.core.config import Settings
from app.services.ollama import OllamaProvider
from evaluation.workflows import evaluate_workflows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ollama', action='store_true', help='Actual Ollama inference with simulated diagnostics')
    parser.add_argument('--output', default='artifacts/phase3/evaluation-scripted.json')
    args = parser.parse_args()
    provider = OllamaProvider(Settings()) if args.ollama else None
    result = asyncio.run(evaluate_workflows(provider))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'mode': result['mode'], 'summary': result['summary'], 'artifact': str(output)}, indent=2))
    if not all(case['accepted'] and case['stage_path_valid'] for case in result['cases']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
