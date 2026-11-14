# Local demonstration

## Phase 2 investigation

1. Start Ollama using `scripts/start-ollama.ps1`, then run `docker compose up --build --wait --wait-timeout 180`. See [Phase 2 setup](phase-2.md) for the installed model and host requirements.
2. Open `http://localhost:8080`, select **AI Investigation Center**, and wait for **Model ready**. This checks the actual model installation and tool capability.
3. Enter a question about the allowlisted demo container and select **Start investigation**. Observe persisted tool choices, actual observations, and model/tool budgets as the run progresses.
4. Read the validated report, follow its evidence references, and expand **Collected evidence**. Compare the model's claims with the actual tool data; a healthy snapshot does not prove future reliability.
5. Use **Export JSON** to download the sanitized record. Select a saved investigation to inspect its report and execution trail again.
6. To demonstrate cancellation, start another investigation and select **Cancel investigation** while it is running. Cancellation preserves partial evidence and does not modify the container.

For repeatable command-line verification, run `scripts/verify_agent.py` with the workspace Python interpreter. Its saved artifact records actual execution; scripted test transports do not count as a real AI demonstration. See the [verification report](phase-2-report.md) for executed results and limits. Multi-agent coordination, simulated failures, and recovery execution remain future phases.

## Foundation health monitoring

1. Start the local stack with the README commands after reviewing the build/test report. Open the dashboard.
2. Observe the connected backend, SQLite database, and actual Flask application result. Read the last-check timestamp.
3. Click **Run health check** twice. Inspect the measured SQLite latency trend; switch the chart to Flask HTTP latency.
4. Open **Infrastructure** and inspect evidence for each service. No CPU/RAM or AI statistics should appear.
5. Open **Health-check history**, expand a record, filter records, and download the real JSON observations.
6. Open **Configuration**. Verify the local target, bounded timeout, and local AI provider configuration. Check actual provider availability in the Investigation Center. Secrets must not appear.
7. For a disconnection demonstration without containers, stop the Flask development terminal, run another check, and observe the unavailable demo with no invented latency. Restart Flask and check again. This is a manually controlled diagnostic demonstration, not an AI failure simulation.
8. Stop the backend and refresh the dashboard. It must show disconnected state or clearly identify saved observations. Restart and use **Retry connection**.

Health monitoring establishes the foundation. Demonstrate the separately verified Phase 2 model/tool workflow to show Agentic AI functionality.

Future evidence to prepare after the appropriate phase passes: approved repository commits, architecture diagram, actual agent tool traces, evaluation rubric/results, screenshots, a working incident/simulation/recovery recording, and presentation. Do not fill these artifacts with illustrative model decisions presented as actual execution.
