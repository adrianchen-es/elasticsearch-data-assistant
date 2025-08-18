#!/usr/bin/env bash
set -euo pipefail

# run_tests_all.sh
# Run frontend, gateway and backend tests in order and report failures.
# Usage: ./run_tests_all.sh

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

FAILED=0
FAIL_SUMMARY=()

run_frontend() {
  if [ -f frontend/package.json ]; then
    echo "==> Running frontend tests (frontend)..."
    if (cd frontend && CI=true npm test --silent); then
      echo "frontend: OK"
      return 0
    else
      echo "frontend: FAILED"
      return 1
    fi
  else
    echo "frontend: SKIPPED (no frontend/package.json)"
    return 0
  fi
}

run_gateway() {
  if [ -f gateway/package.json ]; then
    echo "==> Running gateway tests (gateway)..."
  # ensure dependencies are installed and run tests in CI mode for consistent behavior
  if (cd gateway && (npm ci --silent || (echo "npm ci failed, falling back to npm install" && npm install --silent)) && CI=true npm test --silent); then
      echo "gateway: OK"
      return 0
    else
      echo "gateway: FAILED"
      return 1
    fi
  else
    echo "gateway: SKIPPED (no gateway/package.json)"
    return 0
  fi
}

run_backend() {
  if [ -f backend/requirements.txt ] || [ -d backend ]; then
    echo "==> Running backend tests (pytest)..."

    # Install necessary dependencies
    python -m pip install --upgrade pip
    pip install -r backend/requirements.txt
    pip install pytest pytest-asyncio pytest-html

    # Ensure test-mode is enabled so telemetry exports do not attempt network calls
    export OTEL_TEST_MODE=1
    # Ensure backend package is importable by pytest; avoid unbound PYTHONPATH
    export PYTHONPATH="$ROOT_DIR/backend:${PYTHONPATH:-}"
    if pytest -q; then
      echo "backend: OK"
      return 0
    else
      echo "backend: FAILED"
      return 1
    fi
  else
    echo "backend: SKIPPED (no backend test harness)"
    return 0
  fi
}

main() {
  run_frontend || { FAILED=1; FAIL_SUMMARY+=("frontend"); }
  run_gateway  || { FAILED=1; FAIL_SUMMARY+=("gateway"); }
  run_backend  || { FAILED=1; FAIL_SUMMARY+=("backend"); }

  if [ "$FAILED" -ne 0 ]; then
    echo "\nOne or more test suites failed: ${FAIL_SUMMARY[*]}"
    exit 2
    echo $'\nOne or more test suites failed: '"${FAIL_SUMMARY[*]}"
    exit 2
  fi

  echo $'\nAll test suites passed.'

  echo "\nAll test suites passed."
  exit 0
}

main "$@"
