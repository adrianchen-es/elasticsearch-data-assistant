import subprocess
import sys
from pathlib import Path


def test_validate_test_fixtures_script():
    # Resolve script relative to the repository root regardless of pytest rootdir
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / '.github' / 'preflight' / 'validate_test_fixtures.py'
    assert script.exists(), "validate_test_fixtures.py missing"
    res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"Preflight fixture audit failed: {res.stdout}\n{res.stderr}"
