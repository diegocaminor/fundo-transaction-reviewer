import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_committed_baseline_equals_fresh_run(tmp_path):
    p = subprocess.run([sys.executable, "-m", "fundo", "all", "--out", str(tmp_path)],
                       cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    for name in ("baseline_report.json", "legacy_labels.json"):
        assert (ROOT / "data" / name).read_bytes() == (tmp_path / name).read_bytes(), name


def test_committed_hypotheses_are_recorded():
    doc = json.loads((ROOT / "data" / "baseline_report.json").read_text())
    assert len(doc["hypotheses"]) == 10
