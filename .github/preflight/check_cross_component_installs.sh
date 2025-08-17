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
  # Helper: check surrounding context (10 lines before..3 lines after) for keywords
  check_context() {
    local file="$1"; local lineno="$2"; shift 2; local keywords=("$@")
    local start=$(( lineno - 10 ))
    if [ $start -lt 1 ]; then start=1; fi
    local end=$(( lineno + 3 ))
    # Use sed to extract the vicinity and grep for any of the keywords
    sed -n "${start},${end}p" "$file" | grep -E "$(printf '%s|' "${keywords[@]}")" >/dev/null 2>&1
  }

  # Scan for npm installs and ensure they are near frontend/gateway contexts
  while IFS= read -r line; do
    lineno=$(echo "$line" | cut -d: -f1)
    if ! check_context "$wf" "$lineno" frontend gateway; then
      echo "WARNING: npm install found outside frontend/gateway context in $wf (line $lineno)"
      FAIL=1
    fi
  done < <(grep -nE "npm ci|npm install" "$wf" || true)

  # Scan for pip installs and ensure they are near backend contexts
  while IFS= read -r line; do
    lineno=$(echo "$line" | cut -d: -f1)
    if ! check_context "$wf" "$lineno" backend; then
      echo "WARNING: pip install found outside backend context in $wf (line $lineno)"
      FAIL=1
    fi
  done < <(grep -nE "pip install|pip3 install|python -m pip install" "$wf" || true)

done

if [ "$FAIL" -ne 0 ]; then
  echo "Preflight detected potential cross-component install commands. Please review workflows."
  exit 2
fi

echo "Preflight checks passed: no obvious cross-component installs detected."
exit 0
