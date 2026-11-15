# Phase 2.1 browser and transport reliability follow-up

Verified on **15 November 2026** against the local Compose stack at `http://localhost:8080`. This continues Phase 2.1; Phase 3 and production deployment have not started. The initial [14 November report](phase-2-1-report.md) and original failed investigations remain preserved.

## Result

**176 automated tests passed, with zero final failures:** 137 backend, 3 Flask demo, 21 frontend component/API tests, and 15 real-browser checks. The final browser run had no skips, retries or unexpected console warnings/errors. It took 277.97 seconds including navigation, screenshots, actual AI investigations and downloads; this is not an average inference duration.

Playwright 1.65.1 used the installed **Microsoft Edge 157.0.4341.46**, headless with an isolated profile. The native/browser connectors remained unavailable; the standalone browser-test runner supplied actual browser rendering and JavaScript execution. jsdom and HTTP checks remain separately identified.

| Verification | Executed result |
| --- | --- |
| Navigation | Five implemented pages at 1440x900, 1024x768, 390x844 and 360x800; no document horizontal overflow |
| Health checks/history | Real POST, three actual service observations, persisted check visible and expandable |
| Keyboard | Skip link, main-content focus and next health-check control passed; full accessibility audit remains outside this check |
| Provider errors | Explicitly simulated unavailable model and HTTP 503; creation disabled and retry recovery verified |
| Network error | Actual browser offline mode, visible error, saved data retained, restored-network retry passed |
| Saved reports | Real stored Phase 2.1 reports on desktop and mobile, citation targets/expansion and actual JSON downloads compared with the API |
| Historical output | Actual saved legacy report retains its unverified-output warning |
| Live investigation | Real browser submission through FastAPI, Ollama, restricted Docker broker and SQLite; progress, execution trail and grounded report passed |
| Cancellation | Real run cancelled after service evidence; observations preserved and creation enabled again |
| Missing measurement | Actual disk question returned insufficient evidence without inventing disk utilization |
| Console | No uncaught exceptions, unexpected warnings or unexpected errors in all 15 cases; intentional network failures narrowly excluded |
| Production build/containers | Final Docker frontend TypeScript/Vite build and all four images passed; all four services healthy |
| Other checks | Smoke, basic Ruff, controlled scripted evaluation and staged/source secret checks passed |
| Dependency audit | Vitest updated to 5.1.0; final npm audit reported zero known vulnerabilities |

Screenshot capture also waits for the lazy latency chart or its legitimate empty state. The four layout cases were rerun with that additional assertion before the documentation screenshot was selected.

## Actual live results

Durations below are computed from each persisted run's creation and finish timestamps. Browser test duration additionally includes page setup, readiness checks, polling, assertions and exports.

| Case | Run ID | Outcome | Model/tool calls | Actual diagnostic observations | Duration |
| --- | --- | --- | --- | ---: | ---: |
| Browser health | `77ce8e7e-777f-445f-9af1-38dacfb29f35` | Completed, accepted grounded selection | 3 / 3 | 4, plus coverage | 80.86 s |
| Browser cancellation | `7e7eff48-6c01-48d8-9981-9288358d4f1a` | Cancelled; partial evidence retained | 2 / 1 | 3 | 17.65 s |
| Browser disk question | `f6c778aa-c1f3-4336-bb0f-f51154dbbf61` | Insufficient evidence; model conclusion withheld | 3 / 2 | 4, plus coverage | 43.94 s |
| Focused CLI memory check | `5632301e-adf7-4dc8-8779-a48466136b1e` | Completed, accepted grounded selection | 2 / 2 | 2, plus coverage | 33.53 s |

The health summary states only that Docker reported healthy configured health and that the fixed demo HTTP health probe returned healthy. It does not establish a root cause, future uptime or absence of incidents. Its model selected `service_health`, `inspect_container`, then repeated inspection; the redundant attempt remained within the existing budget.

The focused memory investigation successfully used `container_stats` and inspection after the transport adjustment. Its raw counters were **61,022,208 bytes = 58.20 MiB**, with a **134,217,728-byte = 128.00 MiB** limit and **45.47%** usage. Python derived these values from the same cited counters. The cumulative CPU counter was **3,957,046,261,000 nanoseconds**; CPU utilization remained unavailable. One snapshot establishes neither a memory leak nor a trend.

The health, insufficient-evidence and memory reports were independently reconstructed against their source catalogs in Python: **31/31 references existed and 27/27 returned section claims matched their supported source entries**. The insufficient-evidence report's retained verifier observations are not an accepted model conclusion. These checks cover observations, recommendations, hypotheses, limitations, summary rules and quantities; they do not establish unrestricted causal reasoning accuracy.

The original five-case real-model controlled evaluation remains documented in the initial report and used simulated tools. This follow-up reran the scripted five-case regression separately; those scores are not presented as new live fault-injection results. No container/database fault was deliberately injected.

## Fixes found through browser execution

The initial live browser attempt passed its 12 dashboard cases but failed the positive health and cancellation cases; the disk case did not run before the browser suite's 12-minute deadline. The saved health attempt `821b0cc7-03fe-465e-bdaf-d7dd748ca15c` failed Ollama preflight before any inference or diagnostic calls. Attempt `9b5ede11-17ed-491c-b786-afc18fda70f4` recorded two diagnostic gateway timeouts and correctly withheld a memory conclusion. Its POST response was absent from the browser trace even though the backend had created the run. These are actual failures, not successes.

Changes made without replacing the architecture:

- **Aligned diagnostic deadlines:** the old HTTP client read limit was 6 seconds while the broker could legitimately run for 7 seconds. Shared limits preserve the 7-second broker deadline and allow an 8-second read within a 9-second client ceiling. A real loopback HTTP test with a simulated delayed broker reproduces a valid result arriving after 6 seconds. Docker method/path/identity/label restrictions are unchanged.
- **One bounded preflight retry:** only `unavailable` status is retried once, visibly, inside the original 180-second run deadline. Missing/unsupported models fail immediately. Tests verify recovery, persistent failure, missing/unsupported models and deadline expiry; the retry performs no inference and does not increase the four-model/six-tool limits.
- **Visible transport errors:** gateway timeouts, connection failures and invalid JSON have distinct sanitized messages. Raw exception details are not echoed.
- **Lost-response recovery:** after a failed creation response, the dashboard checks the actual active run ID and follows that run instead of submitting duplicate work. Start/cancel errors remain visible across periodic polling until explicit retry or another action. Two component regressions cover this behavior.
- **Bounded browser tests:** a terminal backend failure is reported promptly, POST-response waits have a deadline, and cancellation waits for a real diagnostic observation while the run is still active. No automatic test retry or fake replacement report is used.

One new unit fixture initially requested health while offering only inspection/log tools, correctly producing insufficient evidence; its preflight test question was corrected to the intended generic observation scope. An early saved-report browser check also counted history rows before loading completed; it now waits for the actual UI. Final counts exclude these earlier failures/skips.

Initial browser results and traces are retained under ignored `artifacts/browser/initial-live-results.json` and `initial-live-test-results/`. Final results are `live-results.json`; per-run JSON, screenshots and revalidation outputs are local-only under `artifacts/browser/`. They are not public download links.

## Reproduction, CI and files

Run commands are in [testing.md](testing.md). `scripts/verify_agent.py --run-id <completed-run-uuid>` independently revalidates an existing report without starting another model run. Its verification duration is reported separately from the original investigation duration.

CI now installs Chromium, checks the real Compose dashboard, retains browser artifacts for seven days, runs frontend dependency audit and checks browser-test TypeScript. Fresh CI has no Ollama or saved investigation records, so the three live-AI and three saved-report cases explicitly skip there. CI must not be described as reproducing all 15 local browser cases. Check [Actions for the reviewed SHA](https://github.com/PARAMCLOUD1/FailureVerse-AI/actions/workflows/ci.yml); local success alone is not remote CI success.

Changed files in this follow-up:

- Reliability: `backend/app/diagnostics/limits.py`, `main.py`, `backend/app/tools/diagnostics.py`, `backend/app/services/investigations.py`, `frontend/src/components/InvestigationCenter.tsx`.
- Regressions: `backend/tests/test_diagnostic_client.py`, `test_investigations.py`, `frontend/src/test/InvestigationCenter.test.tsx`.
- Browser tooling: `frontend/e2e/dashboard.spec.ts`, `helpers.ts`, `investigation.spec.ts`, `playwright.config.ts`, `tsconfig.e2e.json`, `vite.config.ts`, `package.json`, `package-lock.json`, `.gitignore`.
- Independent verifier and CI: `scripts/verify_agent.py`, `.github/workflows/ci.yml`.
- Documentation: README, phase guides/reports, testing and browser checklist, plus the selected real dashboard screenshot.

## Milestone recommendation and limits

**Ready for Phase 2 milestone review with these local checks complete and a passing CI run required for the reviewed commit. Phase 3 remains unstarted until separately authorized.**

This verifies one headless Chromium-based desktop browser at several viewport sizes, not Firefox/Safari, physical touch devices or a full keyboard/accessibility audit. Provider-unavailability browser cases deliberately simulate status/errors; Ollama was not intentionally stopped. The five controlled fault scenarios remain simulated observations, not live failure injection. The finding vocabulary, CPU/disk measurement gaps, SQLite-outage behavior and unauthenticated local-only boundary described in the initial report still apply. Short retries improve resilience but cannot guarantee completion on an overloaded or unavailable host.
