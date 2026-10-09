import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ("businesses.json", "transactions.json", "ground_truth.json", "traps.json",
           "legacy_labels.json", "baseline_report.json", "review_report.json",
           "reviewed_labels.json", "sensitivity.json")


def run_all(out):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "OPENAI_API_KEY")}
    p = subprocess.run([sys.executable, "-m", "fundo", "all", "--out", str(out)],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_all_twice_byte_identical(tmp_path):
    out_a = run_all(tmp_path / "a")
    out_b = run_all(tmp_path / "b")
    for name in OUTPUTS:
        a = (tmp_path / "a" / name).read_bytes()
        assert a == (tmp_path / "b" / name).read_bytes(), name
        assert a.endswith(b"\n")
    assert out_a == out_b and "biz_01" in out_a


def test_all_without_key_reproduces_every_committed_output(tmp_path):
    run_all(tmp_path)
    for name in OUTPUTS:
        assert (tmp_path / name).read_bytes() == (ROOT / "data" / name).read_bytes(), name


def test_report_has_businesses_and_hypotheses(tmp_path):
    import json

    stdout = run_all(tmp_path)
    doc = json.loads((tmp_path / "baseline_report.json").read_text())
    assert set(doc) == {"businesses", "hypotheses"}
    assert [h["business_id"] for h in doc["hypotheses"]] == sorted(doc["businesses"])
    assert all(h["status"] in ("passed", "failed") for h in doc["hypotheses"])
    assert "hypotheses" in stdout.lower() and "changes outcome" in stdout.lower()
