# Phase 3: bounded agent coordination

Implementation authorized after Phase 2.1 approval on 15 November 2026. Work is on `feat/phase-3-coordination` until verified. This document describes the implementation contract; executed results will be recorded separately.

## Scope

A LangGraph workflow coordinates monitoring, the existing investigation agent, simulation planning, risk analysis, and recovery planning. Monitoring and risk analysis apply explicit Python rules to actual approved diagnostics. The investigator retains its native Ollama tool calls, source-bound reports and four-model/six-tool/180-second limits. Simulation and recovery planners select supported catalog IDs through structured local model calls. Python owns the factual statements, policy severity, citations and proposed steps. Deterministic stages are labeled as such; they do not pretend to perform LLM inference.

The workflow has aggregate ceilings of seven inference calls, nine attempted diagnostics and 300 seconds. Budgets include failed attempts and are persisted before requests. Healthy monitoring may finish without inference; an explicit manual investigation mode exercises the full sequence without pretending an incident occurred. Missing evidence and malformed/unavailable inference remain visible terminal outcomes.

Simulation and recovery outputs are proposals. There are no fault-injection, shell, container mutation, approval-token or execution endpoints in Phase 3. Plans explicitly state that execution is disabled. Docker target/method/path/label restrictions are retained.

## Persistence and recovery contract

An additive, versioned SQLite migration adds workflow records without altering or deleting existing health/investigation data. Strict JSON domain checkpoints persist shared evidence, completed stages, role counters, pending work and an absolute expiry. These are application checkpoints around LangGraph nodes, not a claim of native LangGraph arbitrary-state persistence.

Restarted runs become interrupted. Explicit resume must revalidate checkpoint fields and cited evidence, retain already consumed aggregate and investigator budgets, and honor the original absolute expiry. Cancelled/completed/expired runs do not resume. Completed stages are reused; incomplete work can consume only the remaining budget. One shared process execution slot prevents concurrent legacy investigations and coordinated workflows in the supported single-worker API.

## Verification gate

- Controlled healthy, stopped, unhealthy, high-memory and unavailable-database observations; simulated inputs clearly labeled.
- Required observations, valid citations, source-bound specialist selections, prohibited actions, malformed model output and missing data.
- Aggregate/role budgets, cancellation, deadline expiry, interrupted checkpoints, resume without reset, invalid checkpoints and cross-workflow exclusion.
- Additive migration idempotence and preservation of prior records.
- Existing suites, frontend production build, lint, secret/dependency checks and CI.
- Real local monitoring and an explicitly forced full Ollama-to-Docker workflow; browser navigation, progress, stage outputs, evidence, errors and viewport checks.

Do not describe planned checks as passes. Phase 4 execution and production deployment remain outside this authorization.
