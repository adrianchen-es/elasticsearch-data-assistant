## Copilot Coding Agent Instructions — elasticsearch-data-assistant

Purpose
-------
This file helps an automated coding agent onboard quickly and safely. It describes the repository purpose, how to build/test/run it, common pitfalls to avoid, and where to make changes. Trust these instructions and only run repository-wide searches if a step here is missing or fails.

Quick checklist for every change
------------------------------
- Read this file before using search tools.
- Reproduce the build/test locally using the steps in "Build & Validation".
- Run preflight scripts: `.github/preflight/check_cross_component_installs.sh` and `.github/preflight/validate_test_fixtures.py`.
- Run full test suite locally with `./run_tests_all.sh` and confirm all three components pass.
- Ensure `OTEL_TEST_MODE` is set in CI contexts to avoid network exporters during tests.

High-level summary
------------------
- What this repo does: an AI-powered assistant that helps users interact with Elasticsearch clusters (React frontend, Node gateway, FastAPI backend). It includes AI provider integrations, mapping visualization, and observability (OpenTelemetry).
- Project size & stack: medium-sized monorepo (~hundreds of files). Languages: TypeScript/JavaScript (frontend, gateway), Python (backend). Runtimes: Node.js 18+ and Python 3.12+. Target: Elasticsearch 8.x.

Build & Validation (always follow in order)
-----------------------------------------
Environment (repeatable):
- Host: Linux (dev container recommended).
- Node.js: 18+ (used by `frontend` and `gateway`).
- Python: 3.12+ (backend). Use a virtualenv for backend steps.

Bootstrap (one-off, developer machine):
1. Clone repo and change directory.
2. Backend: create and activate venv, then install runtime deps.
   - python -m venv .venv && source .venv/bin/activate
   - cd backend && pip install -r requirements.txt
3. Frontend & Gateway: run installs in each folder. Always prefer `npm ci` in CI; for local development use `npm install` when `npm ci` fails.
   - cd frontend && npm install
   - cd ../gateway && npm install

Build & Run (component-local):
- Backend (dev):
  - cd backend
  - source .venv/bin/activate
  - uvicorn main:app --reload --host 0.0.0.0 --port 8000
- Frontend:
  - cd frontend
  - npm start
- Gateway:
  - cd gateway
  - npm start

Tests (always run before pushing changes)
- Run component tests locally in this order (this is the sequence used by `./run_tests_all.sh`):
  1. Frontend (Vitest)
     - cd frontend && npm test
  2. Gateway (Vitest)
     - cd gateway && npm test
  3. Backend (pytest)
     - cd backend && source .venv/bin/activate && pytest test/ --maxfail=1 -q
- Shortcut: from repo root run `./run_tests_all.sh`. Note: script contains a gateway `npm ci` → fallback to `npm install` if `npm ci` fails (this prevents lockfile mismatch issues in developer environments).

Common failures & mitigations
-----------------------------
- Gateway `npm ci` fails locally due to lockfile/platform mismatch: run `npm install` in `gateway` and `frontend` instead. `./run_tests_all.sh` already attempts this fallback.
- CI or Jenkins tests attempting to export OTLP over network during unit tests: ensure `OTEL_TEST_MODE=true` (or equivalent env) is present in CI / Jenkins job so tests use in-memory shims. Look for references to `OTEL_TEST_MODE` in workflows and `Jenkinsfile`.
- Avoid changing global environment or installing cross-component packages inside another component's CI job: run the repository preflight script `.github/preflight/check_cross_component_installs.sh` if you modify workflow files.
- Tests that assert tracing behavior use an in-test in-memory tracer shim — do not add test-only OTEL exporter dependencies. See `test/*` patterns and `backend` telemetry shim in `backend/middleware/telemetry.py` and `backend/services/ai_service.py`.

Key files & where to make changes
---------------------------------
- Root files: `README.md`, `Makefile`, `run_tests_all.sh` (developer orchestration), `docker-compose*.yml`, `Jenkinsfile`, `.github/workflows/*`.
- Backend: `backend/main.py` (FastAPI app entry), `backend/middleware/telemetry.py` (tracing wrapper & sanitizer), `backend/services/` (AI, Elasticsearch, mapping cache), `backend/config/settings.py` (env settings), `backend/requirements.txt`.
- Gateway: `gateway/src/server.js`, `gateway/package.json`, `gateway/vitest.config.js`.
- Frontend: `frontend/src`, `frontend/package.json`, `frontend/vitest.config.js`.
- Tests: top-level `test/` contains backend integration tests; component tests are under `frontend/__tests__` and `gateway/__tests__`.
- Preflight & validators: `.github/preflight/check_cross_component_installs.sh`, `.github/preflight/validate_test_fixtures.py` — run these in CI and locally when editing workflows or test fixtures.

CI & workflows
---------------
- GitHub workflows live under `.github/workflows/`. There are multiple flows (ci.yml, comprehensive-ci-cd.yml, enhanced-ci-cd.yml). They run component-scoped installs and preflight steps.
- Required CI behavior:
  - `OTEL_TEST_MODE` must be set for test jobs to prevent outbound OTLP in CI.
  - The workflows exclude `test`/`tests` directories from sensitive-data greps but run `.github/preflight/validate_test_fixtures.py` to make the exclusion auditable.

Observability & tracing guidance (end-to-end)
--------------------------------------------
- The codebase uses OpenTelemetry for end-to-end traceability. For safe local and CI runs:
  - Use the existing `SecurityAwareTracer` and `DataSanitizer` in `backend/middleware/telemetry.py`.
  - Tests rely on an in-memory test tracer shim (no external OTLP dependency). Do not add test-only OTLP exporters.
  - When adding instrumentation, follow existing patterns: lazy tracer resolution, sanitized attributes, and minimal span lifetimes.

Project layout quick map (top priority order)
--------------------------------------------
- `backend/` — Python FastAPI service (main app, services, telemetry). Entry: `backend/main.py`.
- `gateway/` — Node gateway API (server.js). Tests: `gateway/__tests__`.
- `frontend/` — React app. Tests: `frontend/__tests__` and `src/components/__tests__`.
- `test/` — integration and enhanced backend tests (pytest).
- `.github/preflight/` — preflight checks and fixture validation.
- `.github/workflows/` — CI workflows.
- `run_tests_all.sh` — local script to run all tests in order (frontend → gateway → backend).

Final guidance for agents
------------------------
- Trust these instructions first. Only search the repo if information here is missing or a step fails.
- Reproduce tests locally and fix CI failures locally before opening PRs.
- Avoid adding test-time network exporters; use in-test shims already present.
- Add or update documentation in `COMPREHENSIVE_DOCUMENTATION.md` or README for any behavior or workflow you change.

If something in this file is out of date, update it in a small PR and include a brief validation note showing you ran the commands and test-suite results.

---
Last updated: 2025-08-17
