# Test Guide — Elasticsearch Data Assistant

This document explains the repository's test layout, how to run the most useful checks locally, and notes about expected failures when async test support is not installed.

## Overview
- Unit / integration tests live under the `test/` directory.
- Many tests exercise async code paths (AI client initialization, async mapping cache scheduler, streaming chat). These tests are annotated with `pytest.mark.asyncio` in places and require an async-capable pytest plugin (for example, `pytest-asyncio`).
- To get a quick, deterministic pass/fail signal without installing async plugins, run the lightweight smoke test `test/test_consolidated_smoke.py` which focuses on import sanity and mapping utilities.

## How to run
- Run the focused smoke test (fast):

```bash
pytest test/test_consolidated_smoke.py -q
```

- Run the full test suite (may require extra plugins and environment variables):

```bash
pytest test/ --maxfail=1 -q
```

## Common environment issues & expected failures
- Missing async pytest plugin: If `pytest-asyncio` (or equivalent) is not installed, many async tests will fail at collection with the message `async def functions are not natively supported.`
  - Expected: several tests in `test/test_ai_service_initialization.py`, `test/test_chat_fixes.py`, and tracing tests will be reported as failed/errored during collection.
  - Fix: install `pytest-asyncio` into your test environment: `pip install pytest-asyncio`.

- Tests that require external services (Elasticsearch, OTEL collector) will fail if those services are not available or if corresponding env vars are not set. Use the included `docker-compose.yml` to spin up a local stack for integration testing.

## Recommended quick checklist before running full suite
- [ ] Install test extras: `pip install -r backend/requirements.txt` and `pip install pytest-asyncio` if you want async tests.
- [ ] Set environment variables from `.env.example` or `.env.external-es.example` when running against external ES.
- [ ] Start local Elasticsearch with `docker-compose up -d elasticsearch` (optional for integration tests).

## Test file mapping (high level)
- `test/test_consolidated_smoke.py` — Fast smoke tests (sanity checks for mapping utils and imports).
- `test/test_enhanced_mapping_fixes.py` and `test/test_enhanced_mapping_fixes_simple.py` — More detailed mapping unit tests.
- `test/test_ai_service_initialization.py` — AI client initialization (async-heavy).
- `test/test_tracing_hierarchy.py` — Tests tracing hierarchy for mapping cache refreshes (async-heavy).

## Troubleshooting
- If a test complains about missing names or imports, make sure your `PYTHONPATH` includes the `backend/` directory (tests do this automatically by inserting it into `sys.path`).
- For intermittent failures related to async scheduling or background tasks, re-run the tests with increased verbosity to see precise tracebacks.

---
Generated: August 15, 2025
