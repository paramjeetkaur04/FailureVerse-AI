# Testing and evaluation

Run commands from the project root unless a working directory is shown. The workspace Python is `.venv/Scripts/python.exe` on Windows; use `.venv/bin/python` on Linux/macOS.

## Automated suites

```powershell
# backend/
& ../.venv/Scripts/python.exe -m pytest -q
# demo-app/
& ../.venv/Scripts/python.exe -m pytest -q
# frontend/
npm.cmd test
npm.cmd run build
# root
& ./.venv/Scripts/python.exe -m ruff check --select E9,F63,F7,F82 backend demo-app scripts
& ./.venv/Scripts/python.exe scripts/check_secrets.py --history --self-test
```

Ruff checks syntax and selected correctness errors; this is basic lint, not a full style audit. The secret check rejects common credential patterns and excluded paths without printing matched values. It is not a comprehensive dependency-vulnerability or security audit. Before each commit also run the secret check with `--staged` and inspect the actual staged diff. `.env`, local tools/models, virtual environments, caches, databases, logs, build output and generated evaluation artifacts must remain ignored.

The grounding tests reproduce the original invented CPU percentage, invented CPU milliseconds/stability, memory conversion error, unsupported absence claims, disk invention, wrong-but-existing citations and incorrect source fields. They also cover invalid/unknown units, negative/non-finite/boolean quantities, impossible normalized percentages, contradictory memory counters, duplicate IDs, malformed responses, missing diagnostic coverage, cancellation, persistence, provider failures and execution budgets.

Required source observations and observed failure signals are mandatory in a completed report. Regression coverage verifies that selecting another true but benign fact cannot hide the main observation. The model still selects IDs; missing required selections fail validation and use only the existing bounded repair attempt.

## Five controlled scenarios

These scenarios inject explicitly **simulated observations**, not Docker mutations. No container is stopped and no database or health endpoint is broken by the evaluation suite. The database-failure fixture represents a failed fixed query probe; an actual outage of the platform's persistent SQLite storage can also prevent durable investigation records and must remain an explicit API/storage failure.

| Scenario | Expected observable evidence | Acceptable conclusion | Expected tools |
| --- | --- | --- | --- |
| Healthy container | Running state, Docker health `healthy`, healthy fixed HTTP/query probes | Report the observed health status; do not infer uptime, absence of attacks or future reliability | Inspection, service health |
| Stopped application | `running=false`, state `exited`, bounded exit log | Container was not running at inspection; stopping reason remains unverified | Inspection, logs |
| Failed health check | Docker health `unhealthy`, degraded HTTP probe | The observed health test failed; no invented application cause | Inspection, service health |
| High memory | 95 MiB used of a 100 MiB limit | 95.00% memory usage; memory pressure may matter, but a leak is unproven | Statistics, inspection |
| Database failure | Fixed database query probe unavailable, failure log, independent demo probe healthy | The connection/query probe failed; do not infer a specific server failure or fabricate a connection error | Service health, logs |

Source fixtures, questions and expected conclusions are versioned in `backend/evaluation/scenarios.py`.

```powershell
# Deterministic regression mode: simulated tools AND a scripted model
& ./.venv/Scripts/python.exe scripts/evaluate_agent.py

# Actual local Ollama inference with the SAME simulated tool observations
& ./.venv/Scripts/python.exe scripts/evaluate_agent.py --ollama --output artifacts/phase21/evaluation-ollama.json
```

The default mode validates orchestration and deterministic report mechanics. Its perfect scores are **not** evidence of Ollama accuracy. `--ollama` measures the real local model's selection under the supplied tool/schema constraints. Neither mode is a live Docker fault test. The application has no production scenario/mock switch; these fixtures exist only in the separate evaluation runner.

## Metric definitions

- **Evidence citation validity:** existing referenced evidence IDs divided by all referenced IDs in the summary and report sections. This checks identity; exact finding/source-field comparisons check support separately.
- **Unsupported returned claim rate:** section claims that differ from their source-supported catalog entry divided by all returned section claims. The host constrains this vocabulary; zero does not establish unrestricted natural-language reasoning accuracy. Raw invalid selections are counted separately as `selection_rejections`.
- **Diagnostic tool selection accuracy:** Jaccard overlap of unique attempted tool names and expected scenario tools. Precision and recall are also recorded. Tool availability is constrained by deterministic question-coverage rules; this is not an unconstrained planning benchmark.
- **Completion rate:** runs with an accepted model selection and a `conclusions` outcome divided by all scenarios. Insufficient evidence, timeouts and provider failures do not count as completed conclusions.
- **Acceptable conclusion rate:** runs whose selected observations include the scenario's expected observable conclusion. A report can be factually supported but omit the most relevant observation, so this is separate from completion.
- **Average duration:** measured wall-clock duration of all attempted scenario runs. Report the mode: scripted timings do not measure LLM or live Docker performance. Summary ratios are macro averages across scenarios with defined denominators; empty claim/reference sets remain unavailable rather than fabricated zeros.

Results include per-scenario denominators, selected/expected tools, simulated provenance, model/tool budgets, validation rejection counts, reports, evidence and failures. One run per scenario is a small demonstration, not a statistical accuracy study. Temperature is zero, but inference and runtime timing are not promised to be bit-for-bit reproducible.

## Actual local Docker verification

```powershell
& ./.venv/Scripts/python.exe scripts/smoke.py
& ./.venv/Scripts/python.exe scripts/verify_agent.py

# Focused actual counter/quantity verification
& ./.venv/Scripts/python.exe scripts/verify_agent.py --question 'Measure current demo container memory usage and utilization against its limit. Inspect container state and use actual counter evidence. Do not infer trends or causes.' --output artifacts/phase21/real-memory-investigation.json
```

The smoke test verifies served HTML/assets, API proxying, real Flask HTTP health, readiness and SQLite persistence. The agent verifier starts a genuine investigation via the deployed API, requires two distinct successful diagnostics, checks execution budgets and actual provenance, and reconstructs the source-field catalog to revalidate the persisted report. It saves the latest and run-specific JSON under ignored `artifacts/phase21/`.

Failed and insufficient-evidence attempts are preserved as well. Do not call an execution-only check a semantic pass for historical Phase 2 free-form reports; the Phase 2.1 verifier additionally requires `grounding_version=2.1` and an accepted model selection.

Real-browser navigation, progress, rendering, errors, responsiveness and console checks are separate. See [browser-verification.md](browser-verification.md); unavailability of browser automation is not a pass.
