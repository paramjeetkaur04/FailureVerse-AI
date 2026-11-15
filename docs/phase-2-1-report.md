# Phase 2.1 reliability verification

Date: **14 November 2026**. Phase 3 has not started. The existing FastAPI/SQLite, LangGraph, Ollama, restricted broker and React architecture is retained.

**Technical result:** source-grounded reporting, required observations and bounded failure handling pass the local checks, two real Ollama-to-Docker investigations, and all five controlled scenarios with real Ollama inference. **Final milestone approval remains conditional on real-browser review and remote GitHub CI/publication, which are not verified.**

## What changed

The model still issues native diagnostic calls and selects findings. Its report response is now a Pydantic `ReportSelection` of eligible fact, hypothesis and recommendation IDs, rather than arbitrary factual sentences or quantities. Python creates those eligible findings from exact collected source fields, derives memory units/percentages with deterministic calculations, binds citations and renders the report. Unknown, duplicate, wrong-category or unsupported selections are rejected. Summary and uncertainty checks apply as well as individual findings.

Every observation has a UUID-based evidence namespace. Each HTTP/query probe receives a distinct ID. A separate coverage record cites unmeasured fields and missing tools. Required observations and observed failures must appear in a completed conclusion; another true but irrelevant fact cannot replace them. Question-coverage rules constrain which relevant missing tools are offered, but the model must still make the native call. No hidden scripted diagnostic fallback is used.

Hypotheses are explicitly tentative and eligible only when their supporting failure condition is observed. Recommendations are never executed. Missing/inconsistent quantities, unsupported disk/CPU-utilization requests, incomplete coverage and invalid report selections produce explicit uncertainty or `insufficient_evidence`; retained verifier facts are not presented as an accepted model conclusion. Historical free-form reports remain preserved and visibly unverified.

## Tests and checks

| Check | Final executed result |
| --- | --- |
| Backend Pytest | **128 passed**, one dependency deprecation warning |
| Flask demo Pytest | **3 passed** |
| Frontend Vitest | **19 passed** |
| Total automated tests | **150 passed; zero currently failing** |
| TypeScript/Vite production build | Passed natively and in the final Docker build |
| Basic Ruff checks | Passed: `E9,F63,F7,F82` |
| Source/index/history secret checks | Passed; no matching secrets or excluded runtime paths |
| Compose configuration and all four images | Passed |
| Final Compose readiness | Backend, frontend, broker and demo healthy |
| Live HTTP smoke check | Passed: real assets, reverse proxy, readiness, Flask HTTP and SQLite persistence |
| Real browser | **Not executed**: browser/native automation hosts unavailable |
| Remote CI | **Not executed**: GitHub authentication/publication pending |

The initial eight old-contract regression failures were corrected while preserving budget, policy and no-fabrication coverage. A disk-scope test found an unnecessary resource-tool requirement; it was fixed. The final build also caught a Node/DOM timer overload mismatch in the new progress test; the test now uses Vitest's fake clock and the full frontend suite/build passed again. No failing final check is being counted as a pass.

Tests cover invalid/unknown units, negative/non-finite/boolean quantities, impossible normalized percentages, inconsistent byte counters, invented CPU milliseconds/percentages/stability, unsupported absence claims, disk invention, wrong-but-existing citations, incorrect source fields, unknown/duplicate IDs, omitted required observations, malformed model/evidence payloads, provider failure, cancellation, persistence and deadline/budget enforcement. The broker's Docker restrictions remain unchanged.

## Actual live Docker investigations

The runtime was workspace-local Ollama **0.40.16**, installed **qwen3:0.6b**, CPU inference with two threads and a 2048-token context. These runs used actual deployed API/SQLite/Docker services, not evaluation transports.

| Property | Final health investigation | Focused actual memory investigation |
| --- | --- | --- |
| Run ID | `974d0db1-01e6-44d1-99c7-99428b44cfef` | `2026eaf9-c22a-4375-aeb4-c723c7c9418c` |
| Status | `completed` | `completed` |
| Model calls | 3 | 2 |
| Diagnostic attempts | 3 | 2 |
| Tool sequence | `service_health`, `service_health`, `inspect_container` | `container_stats`, `inspect_container` |
| Actual diagnostic observations | 7, plus one coverage record | 2, plus one coverage record |
| Verification duration | **89.30 seconds** | **35.31 seconds** |
| Accepted model selection | Yes | Yes |
| Source-field and citation validation | Passed | Passed |

The final health summary reported only the observed Docker configured-health status and the successful demo HTTP probe. Fresh database query observations were also cited in the findings. No confirmed root cause or guarantee of future health was introduced. The completed record and matching report were re-fetched from persistent API storage.

The actual memory observation recorded **61,304,832 bytes = 58.46 MiB**, against **134,217,728 bytes = 128.00 MiB**, yielding **45.68%** usage. These values were calculated by Python from the same raw counters cited in the report. The CPU counter was reported exactly as **1,859,175,614,000 nanoseconds**, explicitly distinguished from CPU utilization. CPU utilization, stability, memory trends and disk usage remained unmeasured; no leak or absence-of-suspicious-activity claim was invented. Hypotheses were empty and the recommendation requested interval samples before calculating utilization/trends.

Generated records are local-only and ignored by Git: `artifacts/phase21/real-investigation.json`, `real-memory-investigation.json`, and their `investigation-<run-id>.json` archives. They are not public repository links. Reproduce using the commands in [testing.md](testing.md).

An earlier candidate run (`4ae63115-3706-41ab-bdac-011f6e038b50`) correctly returned insufficient evidence after the model omitted inspection. Coverage-based tool availability then enabled a successful intermediate run (`a596a7e4-bbf9-4c04-8e7d-0dd3699de605`, 40.81 seconds). That intermediate run predates the final required-observation validation; the table above describes the final code's live checks. Failed and intermediate records were preserved.

## Controlled evaluation with actual Ollama

The five controlled cases use **simulated observations**, with no Docker fault injection. A separate scripted-model run verifies deterministic regression mechanics. The following numbers instead use real Ollama inference against those same fixed tool observations. The case definitions and acceptable-conclusion criteria were not changed between the before/after evaluations.

The first real-model evaluation returned supported facts and completed every run, but included the case's key observation only **60%** of the time. Required source-observation validation fixed that omission path. The original result remains in `artifacts/phase21/evaluation-ollama.json`; the final result is `evaluation-ollama-required.json`.

| Controlled case | Duration (seconds) | Model/tool calls | Expected conclusion present | Citation validity | Unsupported returned claim rate |
| --- | ---: | --- | --- | ---: | ---: |
| Healthy container | 24.078 | 3 / 2 | Yes | 100% | 0% |
| Stopped application | 13.406 | 2 / 2 | Yes | 100% | 0% |
| Failed health check | 14.438 | 2 / 2 | Yes | 100% | 0% |
| High memory utilization | 16.640 | 2 / 2 | Yes | 100% | 0% |
| Database connection/query failure | 15.031 | 2 / 2 | Yes | 100% | 0% |

Aggregate final results: **57/57 cited references valid**, **0/47 unsupported returned section claims**, **100% tool-selection accuracy**, **100% completion**, **100% acceptable-conclusion inclusion**, and **16.72 seconds average duration**. Tool precision and recall were also 100%. The scripted-model regression mode separately passed all five cases; its timings and perfect scores are not counted as real-model performance.

These are five narrow cases with one attempt per case, constrained tool availability and a bounded finding vocabulary. The zero unsupported-returned-claim rate describes enforced source binding, not unrestricted natural-language reasoning or general root-cause accuracy. Metrics, denominators, expected observables and mode distinctions are defined in [testing.md](testing.md). None of the controlled stopped/unhealthy/high-memory/database-failure cases is presented as a live Docker fault test.

## Browser and GitHub status

Browser inventory returned no app/browser and reported `Computer Use native pipe is unavailable` and `The browser access host is unavailable`. Navigation, physical responsiveness, actual export/download behavior, keyboard interaction and console errors have therefore **not** passed a browser check. The complete [manual checklist](browser-verification.md) covers every requested flow. Component and HTTP tests are recorded separately.

Phase 1 commit `94dd605` and all history were preserved. The original branch was renamed from `master` to `main`. Verified Phase 2 work was split into backend, dashboard and documentation commits; Phase 2.1 work uses a feature branch and logical Conventional Commits. Staged reviews, relevant checks and secret scans precede commits. No credentials, local models, virtual environments, caches, generated builds, databases, logs or evaluation JSON were staged.

The requested public target is `https://github.com/PARAMCLOUD1/FailureVerse-AI`. The last GitHub CLI checks reported no authenticated account; unauthenticated repository checks returned 404. Creation, public accessibility, pushes and remote CI are **not confirmed**. See [version-control.md](version-control.md) for the login handoff and authorized workflow. No production deployment was configured or performed.

## Files changed for Phase 2.1

- Grounding and numeric contracts: `backend/app/agents/grounding.py`, `metrics.py`, `schemas.py`, `investigation.py`.
- Fixed probes and bounded execution: `backend/app/services/health.py`, `investigations.py`, `ollama.py`, `backend/app/tools/diagnostics.py`, `backend/app/diagnostics/gateway.py`, `backend/app/main.py`.
- Evaluation: `backend/evaluation/__init__.py`, `scenarios.py`, `runner.py`, `scripts/evaluate_agent.py`, `scripts/verify_agent.py`.
- Backend regressions: `backend/tests/agent_fixtures.py`, `test_agent.py`, `test_grounding.py`, `test_evaluation.py`, `test_investigations.py`, `test_ollama.py`.
- Dashboard and tests: `frontend/src/api.ts`, `components/InvestigationCenter.tsx`, `styles.css`, `test/InvestigationCenter.test.tsx`.
- CI/tooling: `.github/workflows/ci.yml`, `backend/requirements-dev.txt`; GitHub preparation also added `scripts/check_secrets.py` in its own commit.
- Documentation: `README.md`, `docs/phase-2.md`, `phase-2-report.md`, this report, `testing.md`, `browser-verification.md`, and `version-control.md`.

## Recommendation and remaining limits

**Ready for technical review of the bounded Phase 2.1 investigation milestone; hold final Phase 2 milestone approval until manual browser review and authenticated GitHub/CI verification finish. Do not begin Phase 3.**

The finding vocabulary and keyword-based coverage policy are deliberately limited. They do not establish arbitrary log interpretation, novel causal diagnosis, prediction accuracy, recovery effectiveness or instrumentation correctness. The local model can repeat diagnostics and choose redundant findings, but attempts remain bounded. Missing CPU interval/disk data stay unavailable. A full outage of the persistent SQLite store can prevent durable investigations and must remain an explicit storage/API error. The application remains an unauthenticated local test environment; only the designated, labeled Docker resource is readable through the broker.
