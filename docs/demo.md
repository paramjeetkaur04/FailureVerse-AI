# Phase 1 local demonstration

1. Start the local stack with the README commands after reviewing the build/test report. Open the dashboard.
2. Observe the connected backend, SQLite database, and actual Flask application result. Read the last-check timestamp.
3. Click **Run health check** twice. Inspect the measured SQLite latency trend; switch the chart to Flask HTTP latency.
4. Open **Infrastructure** and inspect evidence for each service. No CPU/RAM or AI statistics should appear.
5. Open **Health-check history**, expand a record, filter records, and download the real JSON observations.
6. Open **Configuration**. Verify the local target, bounded timeout, and explicitly inactive AI provider configuration. Secrets must not appear.
7. For a disconnection demonstration without containers, stop the Flask development terminal, run another check, and observe the unavailable demo with no invented latency. Restart Flask and check again. This is a manually controlled diagnostic demonstration, not an AI failure simulation.
8. Stop the backend and refresh the dashboard. It must show disconnected state or clearly identify saved observations. Restart and use **Retry connection**.

This demo establishes the foundation. It is **not** evidence of Agentic AI functionality. Phase 2 must add and verify the real Ollama/tool workflow before a bootcamp agentic demonstration can be claimed.

Future evidence to prepare after the appropriate phase passes: approved repository commits, architecture diagram, actual agent tool traces, evaluation rubric/results, screenshots, a working incident/simulation/recovery recording, and presentation. Do not fill these artifacts with illustrative model decisions presented as actual execution.
