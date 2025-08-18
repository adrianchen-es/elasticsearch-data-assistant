import subprocess
import sys
from pathlib import Path


def test_validate_test_fixtures_script():
    # Locate script relative to this test file
    test_dir = Path(__file__).parent
    script = test_dir.parent / '.github' / 'preflight' / 'validate_test_fixtures.py'
    assert script.exists(), f"validate_test_fixtures.py missing at {script}"
    res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"Preflight fixture audit failed: {res.stdout}\n{res.stderr}"
