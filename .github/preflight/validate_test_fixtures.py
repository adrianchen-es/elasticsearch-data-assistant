#!/usr/bin/env python3
"""Validate test fixtures are auditable when they contain fake secrets.

Rules:
- If `test/README.md` or `tests/README.md` exists, the check passes.
- Otherwise, for any file under `test/` or `tests/` that contains a sensitive pattern,
  the file must contain the literal token 'placeholder' somewhere.

Exit codes:
- 0: OK
- 2: Violations found
"""
import os
import re
import sys
from pathlib import Path

# Resolve repository root relative to this script
SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent.parent  # Go up from .github/preflight to repo root
TEST_DIRS = [ROOT / "test", ROOT / "tests"]

SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9-]{16,}") , # OpenAI-like keys
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"\b(?:10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)"),
    re.compile(r"(mongodb://|mysql://|postgresql://|redis://)"),
    re.compile(r"xoxb-[A-Za-z0-9-]+"),
]

TEXT_EXT = {".py", ".js", ".json", ".env", ".txt", ".md", ".yaml", ".yml", ".ini"}

violations = []

def has_readme(dirpath: Path) -> bool:
    return (dirpath / "README.md").exists() or (dirpath / "readme.md").exists()


def scan_dir(tdir: Path):
    if not tdir.exists():
        return
    # If README exists at top of this dir, consider it auditable
    if has_readme(tdir):
        print(f"Audit: README found in {tdir}, skipping per-file checks")
        return
    # Walk files
    for p in tdir.rglob("*"):
        if p.is_file():
            if p.suffix.lower() not in TEXT_EXT:
                continue
            try:
                text = p.read_text(errors='replace')
            except Exception:
                continue
            found = False
            for pat in SENSITIVE_PATTERNS:
                if pat.search(text):
                    found = True
                    break
            if not found:
                continue
            if 'placeholder' in text.lower():
                continue
            # Violation: sensitive content without 'placeholder' and no README
            violations.append(str(p.relative_to(ROOT)))


def main():
    any_test_dir = False
    for d in TEST_DIRS:
        if d.exists():
            any_test_dir = True
            scan_dir(d)

    if not any_test_dir:
        print("No test directories found; nothing to validate.")
        return 0

    if violations:
        print("\nTest fixture audit violations detected:")
        for v in violations:
            print(f" - {v}")
        print("\nEither add a README.md under test/ or tests/ explaining the fixture policy,\nor include the token 'placeholder' in files containing fake secrets.")
        return 2

    print("Test fixtures audit: OK")
    return 0

if __name__ == '__main__':
    rc = main()
    sys.exit(rc)
