# Phase 1 verification report

## Scope

Foundation only. No AI agent, LangGraph execution, failure injection, Docker mutation gateway, approval flow, or automated recovery is implemented. The user authorized the milestone commit `feat: complete FailureVerse AI Phase 1 foundation` after fresh verification. No GitHub push or public deployment is included; Phase 2 implementation requires separate confirmation.

## Milestone re-verification — 2026-11-13

Before the authorized commit, all available suites were run again: **38 backend tests, 3 Flask tests, and 12 frontend tests passed**. The frontend production build and all three Docker image builds passed. The live Compose smoke test additionally fetched nonempty JavaScript/CSS assets with the correct content types, so a standalone HTML response cannot be mistaken for a working frontend. It verified the same-origin API proxy, actual Flask response, SQLite persistence, and public configuration.

Fresh verification identified and fixed two issues. Recharts compilation during a timed frontend test could exceed its budget on a busy host; the real chart module is now preloaded during test collection. The existing demo container's three-second probe process budget could expire during interpreter startup despite successful HTTP responses. Python probes now skip optional interpreter initialization and allow ten seconds for the entire process; each HTTP request retains a two-second timeout. Application diagnostic request limits are unchanged. These fixes were verified with the frontend suite, rebuilt images, refreshed containers, and the live smoke test.

The three local services were inspected as **healthy with zero consecutive health-check failures**. All run as non-root with read-only roots and the configured CPU/memory limits. The demo network is internal; the backend mounts only its SQLite data volume, with no Docker socket. The local stack was already running at the start of re-verification and remains running for local review; no public deployment was performed.

Git and Docker build exclusions were expanded to private keys, credential directories, local AWS/SSH files, and environment files. All **58 candidate files** were checked for prohibited paths and recognized credential-token/private-key patterns without printing secret values; no findings were detected. **17 exclusion checks passed**, and `.env.example` remains versionable. The final staged content must pass the same audit before the commit is created.

The README was refreshed with Phase 1 features and test counts, setup commands that preserve an existing `.env`, probe behavior, and secret exclusions. Browser visual review remains unverified: the desktop helper's native pipe was unavailable on the fresh attempt. The GitHub workflow and optional Prometheus profile have not been run externally.

## Initial environment

The starting workspace contained no project files or applicable workspace `AGENTS.md`.

| Component | Observed |
| --- | --- |
| OS / shell | Windows 10, PowerShell |
| Python launcher | Present, no installed interpreter found |
| Workspace Python installed for testing | CPython 3.12.13 via uv 0.11.16 |
| Node.js | 26.13.0 |
| npm | 11.20.0 |
| Git | 2.56.0.windows.2 |
| Docker CLI / engine | 29.9.2 / 29.9.2 |
| Docker Compose | 5.6.1 |
| WSL | 3.0.5, kernel 6.18.58.1-1 |
| WSL distributions | Ubuntu (WSL2, stopped); docker-desktop (WSL2, running) |
| Ollama | Not found on PATH; not needed for Phase 1 |

Docker/WSL checks required access outside the workspace sandbox. Python was downloaded into ignored `.tools/python`; dependencies use ignored `.venv`, `.cache`, and `frontend/node_modules`. Git was initialized with no commits.

## Executed verification

| Verification | Result |
| --- | --- |
| Backend: `../.venv/Scripts/python.exe -m pytest -q` from `backend/` | **38 passed**; 1 upstream Starlette/AnyIO deprecation warning |
| Flask: `../.venv/Scripts/python.exe -m pytest -q` from `demo-app/` | **3 passed** |
| Frontend: `npm.cmd test` from `frontend/` | **12 passed** across 2 test files |
| Frontend: `npm.cmd run build` | Passed; Vite 7.3.8 / TypeScript; initial JS 249.59 KB, lazy chart 376.12 KB; no chunk-size warning |
| Final TypeScript check: `node_modules/.bin/tsc.cmd -b` | Passed |
| Compose: `docker compose config --quiet` | Passed |
| Backend and Flask Docker image builds | Passed; verified image users `10001:10001` and `10002:10002` |
| Frontend Docker image build | Passed after source fixes and a transient Docker Hub DNS failure resolved on retry |
| Native local stack HTTP smoke | Passed through Vite port 5173, FastAPI, actual Flask, and SQLite |
| `docker compose up --no-build --wait --wait-timeout 120` | All 3 test services became healthy |
| Docker stack HTTP smoke | Passed through Nginx port 8080, FastAPI, actual Flask, and SQLite |
| Running-container safety inspection | All 3 non-root and read-only, correct CPU/RAM limits; demo network `internal=true` |
| Browser visual review | **Not completed**: browser access host unavailable; native browser approval timed out; fresh attempt found desktop helper native pipe unavailable |
| GitHub Actions execution | **Not run externally**; workflow authored with equivalent test/build/smoke commands |

**53 automated tests passed.** The smoke checks additionally verified frontend HTML, same-origin API routing, live readiness, a real Flask health response, persisted check identity, and public configuration with AI/Docker control disabled. There are no outstanding automated test failures.

Backend tests cover every declared API route, readiness failure, CORS, validation, fixed targets, failed/malformed/redirected/oversized demo responses, secrets exclusion, concurrency conflict, retention, persistence across application restart, and a real HTTP integration with the actual Flask application. Frontend tests cover loading, empty/disconnected states, backend-value rendering, manual checks, navigation, history filtering and expansion, provider configuration, clipboard copy, API errors, and distinguishing failed actions from connection failures.

Initial failures were resolved: invalid `exact` options in Testing Library role queries, Vite parent-directory reads denied by the sandbox, a test querying the lazy chart before its module loaded, and transient npm/Docker registry network failures. The first Docker frontend build had captured source before the TypeScript correction; rebuilding the corrected source passed. An initial 625 KB frontend bundle warning was removed by loading the chart separately and limiting bundled fonts to the interface's Latin character set.

The remaining backend warning is a dependency deprecation in Starlette's test client referring to an AnyIO alias. It did not fail a test and is not suppressed. npm also reports a deprecation in jsdom's transitive `whatwg-encoding` package.

## Commands executed

Environment checks: `py --list-paths`, `py -3 --version`, `python --version`, `node --version`, `npm.cmd --version`, `git --version`, `docker --version`, `docker compose version`, `docker info`, `wsl --version`, and `wsl --list --verbose`. Python's initial launcher/alias checks failed because no interpreter was installed.

Setup and verification, with the working directory indicated in the README:

```powershell
git init
# UV_CACHE_DIR and UV_PYTHON_INSTALL_DIR pointed inside this workspace.
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r backend/requirements-dev.txt -r demo-app/requirements.txt
# In frontend/; registry retries also used the workspace cache:
npm.cmd install --cache ../.cache/npm --no-fund --no-audit --prefer-offline --fetch-timeout=300000 --fetch-retries=2 --fetch-retry-mintimeout=5000 --fetch-retry-maxtimeout=20000
# In backend/, then demo-app/ respectively:
& ../.venv/Scripts/python.exe -m pytest -q
# In frontend/:
npm.cmd test
npm.cmd run build
& ./node_modules/.bin/tsc.cmd -b
# Native dev servers were started using the README commands, then stopped.
# From repository root:
& ./.venv/Scripts/python.exe scripts/smoke.py --frontend http://127.0.0.1:5173
docker compose config --quiet
docker compose build
docker compose build frontend
docker image inspect failureverse-ai-backend failureverse-ai-demo-app --format '{{.RepoTags}} user={{.Config.User}}'
docker compose up --no-build --wait --wait-timeout 120
& ./.venv/Scripts/python.exe scripts/smoke.py --frontend http://127.0.0.1:8080
docker inspect failureverse-ai-demo-app-1 failureverse-ai-backend-1 failureverse-ai-frontend-1 --format '{{.Name}} user={{.Config.User}} readonly={{.HostConfig.ReadonlyRootfs}} memory={{.HostConfig.Memory}} nano_cpus={{.HostConfig.NanoCpus}} health={{.State.Health.Status}}'
docker network inspect failureverse-ai_test-lab --format 'test-lab internal={{.Internal}}'
docker compose down --timeout 10
docker compose ps --all --format json
git status --short --untracked-files=all
git check-ignore .env .venv .tools .cache frontend/node_modules backend/data/failureverse.db frontend/tsconfig.tsbuildinfo
```

Docker inspection commands restricted output to users, health, resource limits, and network isolation; full environment configuration was not printed. Downloads, Docker engine access, and Vite commands needed explicit tool escalation outside the sandbox. No global Python installation was made.

## Files

The repository was created from an empty workspace. [phase-1-files.txt](phase-1-files.txt) lists every created source/configuration/documentation file. Major groups are the modular backend and tests, typed React dashboard and UI tests, Flask demo, Docker/Prometheus configuration, initial CI workflow, environment example, README, architecture, demo guide, smoke tool, and this report. Generated caches, databases, binaries, build output, and virtual environments are ignored by Git.

## Run and review

Use the exact native-development or Compose commands in the [README](../README.md). For a local Docker demonstration:

```powershell
Copy-Item .env.example .env
docker compose up --build --wait
```

Open `http://localhost:8080` and use **Run health check**. The optional Prometheus profile was configured but not started or verified against the external Prometheus image. The initial foundation smoke-test stack and native servers were stopped, preserving SQLite; that cleanup check returned no containers. A local stack was subsequently already running when the authorized commit re-verification began. It was refreshed with the corrected probe settings and left healthy for local review. No GitHub push, public deployment, or Phase 2 implementation is included in this milestone.

Before a visual sign-off, review desktop/tablet/mobile layouts and keyboard interactions in a real browser. CSS breakpoints, mobile navigation, focus states, reduced-motion handling, and horizontal table scrolling are implemented, but jsdom cannot verify their physical layout. This limitation must not be reported as successful browser QA.

## External conditions

Initial sandbox network access blocked Python/npm downloads; explicit tool escalation was requested. The first npm registry attempt outside the sandbox timed out and the longer-timeout retry succeeded. Docker Hub DNS failed transiently on a rebuild; the next attempt succeeded. External CI is configured but cannot be described as run until executed in GitHub.

## Next phase

The Phase 1 commit was explicitly authorized subject to fresh verification. The recommended next phase is **Phase 2: the first genuine local Ollama investigation agent**, using validated read-only tools for a designated, explicitly labeled Docker test container. Prepare the plan after the Phase 1 commit, then wait for the user's confirmation before implementing or installing Phase 2 dependencies. Manual browser layout review remains an outstanding verification item. Simulation and recovery mutations remain outside Phase 2's scope.
