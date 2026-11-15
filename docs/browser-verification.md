# Browser verification checklist

Status on 14 November 2026: **not executed in a real browser**. The computer-use inventory returned no browser and these errors: `Computer Use native pipe is unavailable` and `The browser access host is unavailable`. HTTP smoke checks and jsdom tests passed separately; neither establishes browser layout or console correctness.

Use `http://localhost:8080` with the local Compose stack and Ollama running. Record browser/version, date, viewport, result and any screenshot path for each row. Do not put secrets or raw private logs in screenshots.

| Check | Manual steps and expected result | Result |
| --- | --- | --- |
| Navigation | Open Overview, Infrastructure, Health-check history, AI Investigation Center and Configuration. Each page should load its intended content without blank screens. | Pending |
| Creation | Wait for Model ready, enter a question about current demo health and start. A new saved run should appear; repeat submissions must be disabled while active. | Pending |
| Live progress | Observe counters and stage text while the run executes. Tool choices and observations should appear as persisted events. | Pending |
| Execution timeline | Compare selected tools, call counts, timestamps and observations with the exported JSON. The timeline must not claim recovery was executed. | Pending |
| Final report | Check source-validated observations, unconfirmed hypotheses and unexecuted recommendations. Summary and finding citations must scroll to the matching evidence; expand it and compare source fields and quantities. | Pending |
| Insufficient evidence | Ask for disk utilization, which is not measured. The result must state insufficient evidence and must not invent a disk percentage. | Pending |
| Historical report | Select an old Phase 2 report. It must show the warning that source-field validation did not apply to that output. | Pending |
| Cancellation | Start another run and cancel it. The terminal state must be visible, partial evidence preserved and the start control enabled after active status refresh. | Pending |
| Provider failure | Stop only the local Ollama helper, refresh provider status and confirm creation becomes unavailable with an explicit error. Restart using the setup guide. | Pending |
| Backend/network error | With browser developer tools, temporarily use offline mode and refresh. Confirm the error is visible and no report or measurement is invented; restore networking and retry. | Pending |
| Export | Export a completed and an insufficient-evidence run. Check downloaded JSON IDs, sources, provenance, limits, report outcome and validation notes against the screen. | Pending |
| Desktop | At 1440×900, check all controls, report columns, long source fields and expanded evidence for clipping or overlap. | Pending |
| Tablet | At 1024×768, check history/detail stacking and page navigation. | Pending |
| Mobile | At 390×844 and 360×800, open/close the menu, navigate, start/cancel, expand evidence, and check horizontal overflow and readable citation labels. | Pending |
| Keyboard | Tab through navigation, form, run controls, citations and details; confirm visible focus and that Enter/Space activate controls. | Pending |
| Console/network | Open developer tools before navigation. Check all flows above for uncaught JavaScript errors, React warnings, failed asset loads and unexpected API failures. Record actual messages, not a presumed pass. | Pending |

The component suites cover rendering, API-error display, cancellation, citations, insufficient-evidence messaging and historical warnings with isolated fixtures. Physical responsiveness, actual downloads, console output and browser interaction still require this checklist or working browser automation.
