import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_package_imports():
    import fundo

    assert fundo.__doc__


def test_package_imports_from_repo_root_without_pytest_path():
    # pytest's pythonpath hides import problems; run the way a user would.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "-c", "import fundo"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
