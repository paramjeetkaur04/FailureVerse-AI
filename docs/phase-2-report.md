# Phase 2 verification report

## Phase 2.1 addendum

The original Phase 2 findings below are preserved as historical evidence. Phase 2.1 replaces free-form factual generation with model-selected finding IDs and deterministic source-field rendering, adds fixed service probes and explicit insufficient-evidence results, and validates required observations so a report cannot omit the main finding. See [phase-2-1-report.md](phase-2-1-report.md) for the final tests, live run, real-model controlled evaluation, browser limitation and milestone recommendation. Original inaccurate reports were not edited or retroactively marked accurate. Phase 3 has not started.

## Original Phase 2 verification

Verification date: **14 November 2026**. Scope: one genuine local Ollama investigation agent using LangGraph, restricted Docker diagnostics, durable SQLite records, and the React Investigation Center. Multi-agent coordination, fault injection, recovery execution, and deployment remain outside this phase.

**Status: the real model/tool integration is verified; factual report quality and browser review remain open. Do not treat this as an accuracy sign-off or advance to Phase 3 yet.**

## Automated checks

| Check | Executed result |
| --- | --- |
| Backend: `../.venv/Scripts/python.exe -m pytest -q` | **85 passed** |
| Flask demo: `../.venv/Scripts/python.exe -m pytest -q` | **3 passed** |
| Frontend: `npm.cmd test` | **16 passed** |
| TypeScript and Vite production build | Passed inside the frontend Docker build |
| `docker compose config --quiet` | Passed |
| All four Compose image builds | Passed; backend and broker rebuilt again after agent fixes |
| `docker compose up --no-build --wait --wait-timeout 180` | All four services healthy |
| `scripts/smoke.py` against `http://127.0.0.1:8080` | Passed after the final backend rebuild |
| `git diff --check` | Passed |

The suites contain **104 tests** in total. The complete backend suite passed after the final quantity-validation changes. The backend emits one dependency deprecation warning concerning Starlette's AnyIO `BlockingPortal` alias; it does not fail the tests. Frontend tests required execution outside the filesystem sandbox because Vite's configuration loader could not traverse a parent directory there.

The live smoke check fetched executable frontend JavaScript and CSS, exercised the API reverse proxy, verified readiness, made an actual Flask HTTP health request, persisted a check in SQLite, retrieved it through the overview, and checked the public configuration. This is separate from the scripted provider transports used by unit tests.

Covered failure and policy cases include missing or unsupported models, unavailable providers, malformed and oversized responses, invalid tool arguments, forbidden tool names, unknown evidence references, diagnostic and inference budgets, overall deadline cancellation, disabled AI, untrusted browser origins, single-flight execution, cancellation, and persisted report retrieval. Broker tests verify all three required test labels, deny Docker mutations and unrelated reads, bound/redact logs, and avoid inventing CPU utilization. The broker liveness endpoint does not access Docker or consume its diagnostic slot.

## Actual local-model verification

The final run passed the execution checks against real services:

| Recorded property | Actual result |
| --- | --- |
| Run ID | `04646e06-1107-4c78-8386-0f3242733f04` |
| Status | `completed` |
| Model calls / diagnostic calls | **2 / 2** |
| Model-selected tools | `container_stats`, `container_logs` |
| Verification elapsed time | **119.42 seconds** |
| Recorded timestamps | `2026-11-14T12:26:51.912566Z` to `2026-11-14T12:28:51.641395Z` |
| Enforced budgets | 4 inference calls, 6 attempted tools, 180 seconds |
| Validation completed | JSON schema, collected evidence IDs, known CPU-percentage/memory-conversion checks |
| Durable retrieval | Completed record and matching report re-fetched through the API |

The actual statistics recorded **60,968,960 bytes / 58.14 MiB** of memory, a **128 MiB** limit, and **45.43%** memory usage. CPU utilization remained unavailable; only the actual cumulative CPU counter and CPU count were recorded. Timestamped application logs were collected as a separate bounded observation. The saved record includes model tool selections, actual results, state transitions, counters, final report, and limits. No test provider or scripted Docker transport participates in this command-line demonstration.

Local-only evidence paths: `artifacts/phase2/real-investigation.json` and `artifacts/phase2/investigation-04646e06-1107-4c78-8386-0f3242733f04.json`. These generated records are intentionally ignored by Git and are not public repository links. `scripts/verify_agent.py` preserves subsequent runs separately as well.

**Manual factual review did not pass.** The final report correctly repeated the memory percentage and limit, but still described CPU usage as "stable," introduced an unsupported `8292ms` value, and asserted absence of leaks/suspicious activity. Its actual CPU counter was `829232997000` nanoseconds; a single sample and clipped logs cannot support those conclusions. Some CPU statements cite log evidence, illustrating that a valid evidence ID does not establish semantic relevance. The limited quantity checks reject the reproduced percentage/memory-conversion errors; they do not validate arbitrary units, trends, absence claims, or general natural-language interpretation. The completed state records successful execution and bounded validation, not verified diagnostic truth. Original generated outputs are preserved unchanged.

The test host runs Windows Docker Desktop and workspace-local Ollama **0.40.16**, using the installed **qwen3:0.6b** model on CPU. The application uses two inference threads, a 2048-token context, bounded generation, and an 800-character log excerpt per prompt. Full sanitized log evidence remains bounded to 4096 bytes in the saved record.

The three diagnostic operations were also executed from inside the running backend against the actual broker. Container inspection returned the designated container identity and healthy state; logs returned actual timestamped HTTP health requests with truncation recorded; statistics returned actual memory/CPU counters. Those direct broker checks establish tool connectivity, independently of model-selected execution.

## Corrections found during real execution

The earlier log-stream path used a Docker SDK helper that disabled socket timeouts. The bounded frame reader preserves timeouts, stops at its byte limit, and closes the response. Its regression test verifies Docker stdout/stderr frame decoding, the timeout setting, output bounds, and response cleanup. The real broker subsequently returned log observations successfully.

An earlier real investigation reached the **180-second** deadline after collecting two observations while spending additional inference calls on readiness. Another two-call attempt hit the former **65-second** provider timeout during report generation. These attempts saved partial evidence and explicit failures without generating a substitute report. Ollama logs showed approximately five generated tokens per second on this host.

The graph now requests the structured report directly once two distinct tools have returned observations. It still supports model-selected follow-up tools when evidence is insufficient. Model selection, argument validation, exact target/label restrictions, and evidence-reference validation remain enforced. The per-call timeout defaults to **120 seconds**, while the overall **180-second** deadline still covers provider preflight and all inference/tool work. Four model calls and six attempted diagnostic calls remain hard ceilings.

Invalid arguments and broker errors now produce distinct sanitized feedback. Broker container health probes use process liveness instead of competing with actual investigations for the diagnostic slot.

Manual review of completed run `927919d5-f50b-40c4-9d1d-adff9fd68c8b` caught factual errors despite valid schema and evidence references: the model described `61,136,896` bytes (about 58.3 MiB) as "611MB" and called a single CPU counter "consistent." That run used two model calls and two actual tools and completed in 94.81 seconds, but it does **not** establish accurate interpretation. The record remains preserved as `artifacts/phase2/investigation-927919d5-f50b-40c4-9d1d-adff9fd68c8b.json`.

The broker now supplies memory usage and limit explicitly in MiB and derives a memory percentage from those same recorded counters, leaving unavailable/zero-limit percentages missing. Regression coverage checks the conversion against known byte counters. Reporting guidance asks the model to copy the supplied units and avoid inferring trends, leaks, or absence of suspicious activity from snapshots and clipped logs. These changes reduce ambiguity; they do not provide general semantic validation of free-text model output.

Run `2ac211c1-f68d-489a-81ce-7c127ec33212` completed in 120.66 seconds with two model calls and two actual tools, but manual review still found an invented "100% CPU" claim, citing log evidence even though the stats observation explicitly recorded `cpu_percent: null`. This exposed the limit of prompt guidance alone. Its original record remains preserved. The agent now rejects numeric CPU percentage claims when utilization was not measured and rejects memory quantities in MB/MiB/GB/GiB that do not match recorded usage/limit counters within their stated rounding precision. The permitted report-repair attempt receives the specific validation failure; it remains subject to the same four-call and 180-second budgets. Regression cases reproduce both observed unit/CPU errors and accept correctly rounded units. These checks cover known quantitative failure patterns, not arbitrary natural-language truth or semantic citation relevance.

## Limits and outstanding review

- Browser visual review could not run. Both the Windows native helper pipe and browser access host were unavailable. Desktop/tablet/mobile layout, keyboard navigation, evidence-link behavior, and browser download behavior remain unverified in a real browser; jsdom tests do not establish visual correctness.
- The verified AI route uses the Compose backend. Docker Desktop did not publish the broker's configured host port while it was attached only to an internal network; `localhost:8020` was unavailable. Internal backend-to-broker diagnostics worked. Native backend AI requires a separately reachable broker. The demo container's isolated host port has the same limitation; its backend health check uses the internal service address.
- A healthy broker container establishes process liveness, not Docker availability. Every tool request still checks the exact target identity and labels.
- A schema-valid report with valid evidence IDs can still contain inaccurate interpretations. The small local model is not evidence of diagnostic accuracy, failure prediction, or production reliability. Point-in-time counters cannot establish CPU utilization percentages or future uptime.
- The local application has no authentication or multi-user authorization. Loopback bindings and the designated test environment remain required. No mutation, shell, simulation, or recovery endpoint was added.
- GitHub Actions is configured but has not been executed remotely in this verification. The optional Prometheus profile and Linux-specific socket-group setup were not verified.
- Runtime/model files, `.env`, SQLite data, and investigation artifacts remain ignored by Git. No commit, push, or deployment was performed during this continuation.

## Local review

The local stack is left running for review at `http://localhost:8080`. Open **AI Investigation Center**, inspect a saved run's execution trail and collected evidence, and compare the report with the actual observations. Setup and API contracts are documented in [phase-2.md](phase-2.md); a demonstration sequence is in [demo.md](demo.md).

Phase 3 remains pending. The next work is report-quality evaluation and stronger factual grounding: bind quantitative claims to explicit source fields, test unsupported trend/absence claims, and evaluate whether the local model can meet those requirements within this host's resource and execution limits. Browser layout review also remains outstanding. The current integration is a genuine single-agent demonstration, not a validated diagnostic or recovery system.
