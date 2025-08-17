#!/usr/bin/env bash
# Small preflight to detect cross-component install commands in workflow YAMLs.
# It scans .github/workflows for obvious patterns like `pip install` or `npm ci`
# appearing in jobs that target other components (frontend/backend/gateway).

set -euo pipefail
FAIL=0

echo "Running preflight: scan workflows for cross-component installs..."

for wf in .github/workflows/*.yml .github/workflows/*.yaml; do
  [ -f "$wf" ] || continue
  echo "Checking $wf"

  # Find lines with pip install and the surrounding job name
  grep -nE "pip install|pip3 install|python -m pip install" "$wf" || true
  if grep -qE "npm ci|npm install" "$wf"; then
    # Check if npm install appears in backend job contexts
    if grep -n "npm ci\|npm install" "$wf" | grep -v "frontend" | grep -v "gateway" >/dev/null 2>&1; then
      echo "WARNING: npm install found outside frontend/gateway context in $wf"
      FAIL=1
    fi
  fi

  if grep -qE "pip install" "$wf"; then
    if grep -n "pip install" "$wf" | grep -v "backend" >/dev/null 2>&1; then
      echo "WARNING: pip install found outside backend context in $wf"
      FAIL=1
    fi
  fi

done

if [ "$FAIL" -ne 0 ]; then
  echo "Preflight detected potential cross-component install commands. Please review workflows."
  exit 2
fi

echo "Preflight checks passed: no obvious cross-component installs detected."
exit 0
