# Browser verification checklist

Status on **15 November 2026: 15 real-browser checks passed**, with no final failures, skips, retries or unexpected console warnings/errors. Playwright used installed Microsoft Edge **157.0.4341.46**, headless in an isolated profile, against the actual dashboard. The earlier native/browser connector errors remain true, but standalone Playwright provided working browser automation. HTTP smoke and jsdom results are still reported separately.

Use `http://localhost:8080` with Compose and Ollama running. Commands, modes and CI skips are in [testing.md](testing.md); run IDs, durations, source-validation results and initial failures are in the [browser follow-up report](phase-2-1-browser-report.md). Final JSON, screenshots and traces are under ignored `artifacts/browser/`. The selected documentation screenshot contains only generic local service observations.

| Check | Executed check and expected behavior | Result |
| --- | --- | --- |
| Navigation | All five implemented pages load at four viewport sizes; overview waits for the lazy chart or its empty state. | Passed |
| Creation | Actual browser POST returns 202, progress appears, duplicate submission is disabled. | Passed with real Ollama/Docker |
| Live progress | Running state, stage and persisted diagnostic events are rendered. | Passed |
| Execution timeline | Actual tool names render; downloaded events, call counts and limits match the persisted API record. | Passed |
| Final report | Grounded observations, tentative hypotheses, recommendations and citations render; links reach expandable matching evidence. | Passed on desktop/mobile |
| Insufficient evidence | Actual disk question returns insufficient evidence and no invented disk percentage. | Passed with real Ollama/Docker |
| Historical report | Actual stored legacy report shows the unverified-output warning. | Passed |
| Cancellation | Cancel after actual service observations; terminal state, retained evidence and released start control verified. | Passed with real Ollama/Docker |
| Provider failure | Browser routes deliberately simulate unavailable-model status and HTTP 503; start disables and explicit retry recovers. Ollama was not intentionally stopped. | Passed, simulated error inputs |
| Backend/network error | Browser context goes offline, shows the failure and saved-data notice, then recovers through retry after networking is restored. | Passed |
| Export | Real completed and insufficient-evidence JSON downloads match API report, evidence, events, status, counters and limits. | Passed |
| Desktop | 1440x900 navigation/screenshots, document-width check, report links and export. | Passed |
| Tablet | 1024x768 navigation/screenshots and document-width check. | Passed |
| Mobile | 390x844 and 360x800 menu/navigation/screenshots and document-width checks; 360px saved-report citations, expansion and download. Live creation/cancellation used desktop. | Passed for the stated viewport flows |
| Keyboard | Tab to skip link, Enter to main, Tab to health-check control. | Passed for these keys; full audit pending |
| Console/network | Browser listeners collect uncaught exceptions, warnings and errors across all flows. Only deliberately induced network/resource errors are narrowly allowed. | No unexpected messages |

The component suites additionally cover recovery of the actual active ID after a lost start response and operation errors persisting across polling. These deterministic component inputs are distinct from live browser investigations.

Remaining manual coverage: full keyboard/screen-reader audit, physical touch devices, Firefox/Safari and subjective visual review on other displays. These were not executed or counted as passes. Headless viewport checks do not establish physical-device compatibility. If repeating manually, record browser/version, date, viewport, result and screenshot location; keep secrets and private logs out of screenshots.
