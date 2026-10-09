import json
from datetime import date, timedelta

from fundo.generate import END_DATE, generate

FILES = ("businesses.json", "transactions.json", "ground_truth.json", "traps.json")


def test_two_runs_are_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate(42, a)
    generate(42, b)
    for name in FILES:
        assert (a / name).read_bytes() == (b / name).read_bytes()
        assert (a / name).read_bytes().endswith(b"\n")


def test_different_seed_differs(tmp_path):
    generate(42, tmp_path / "a")
    generate(7, tmp_path / "b")
    assert (tmp_path / "a/transactions.json").read_bytes() != (
        tmp_path / "b/transactions.json"
    ).read_bytes()


def test_business_set_and_history(tmp_path):
    generate(42, tmp_path)
    biz = json.loads((tmp_path / "businesses.json").read_text())
    assert [b["business_id"] for b in biz] == [f"biz_{i:02d}" for i in range(1, 11)]
    days = {b["business_id"]: b["history_days"] for b in biz}
    assert days["biz_03"] == 61
    assert all(v == 90 for k, v in days.items() if k != "biz_03")


def test_dates_within_fixed_window(tmp_path):
    generate(42, tmp_path)
    txns = json.loads((tmp_path / "transactions.json").read_text())
    assert END_DATE == date(2026, 6, 30)
    biz03 = [t["date"] for t in txns if t["business_id"] == "biz_03"]
    assert min(biz03) >= (END_DATE - timedelta(days=60)).isoformat()
    assert max(t["date"] for t in txns) == END_DATE.isoformat()


def _rows_by_business(txns, truth):
    out = {}
    for t in txns:
        out.setdefault(t["business_id"], []).append((t, truth[t["transaction_id"]]))
    return out


def test_changing_one_business_leaves_others_identical(monkeypatch):
    from dataclasses import replace

    import fundo.generate as gen

    _, txns, truth, _ = gen.build(42)
    before = _rows_by_business(txns, truth)

    changed = tuple(
        replace(a, routine=a.routine + (gen.sweep(1),)) if a.business_id == "biz_05" else a
        for a in gen.ARCHETYPES
    )
    monkeypatch.setattr(gen, "ARCHETYPES", changed)
    _, txns2, truth2, _ = gen.build(42)
    after = _rows_by_business(txns2, truth2)

    assert before["biz_05"] != after["biz_05"]
    for biz_id in before:
        if biz_id != "biz_05":
            assert before[biz_id] == after[biz_id], biz_id


def test_business_seed_is_stable_and_not_builtin_hash():
    from fundo.generate import business_seed

    # First 8 bytes (big-endian) of sha256(b"42:biz_01").
    assert business_seed(42, "biz_01") == 6097565595807422632
    assert business_seed(42, "biz_01") != business_seed(42, "biz_02")
    assert business_seed(42, "biz_01") != business_seed(7, "biz_01")


def test_business_seed_ignores_hash_randomization():
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    code = "from fundo.generate import business_seed; print(business_seed(42, 'biz_03'))"
    outputs = set()
    for hashseed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": hashseed}
        env.pop("PYTHONPATH", None)
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True
        )
        assert out.returncode == 0, out.stderr
        outputs.add(out.stdout)
    assert len(outputs) == 1

