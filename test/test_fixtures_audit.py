import subprocess
import sys
from pathlib import Path


def test_validate_test_fixtures_script():
    script = Path('.github/preflight/validate_test_fixtures.py')
    assert script.exists(), "validate_test_fixtures.py missing"
    res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"Preflight fixture audit failed: {res.stdout}\n{res.stderr}"
