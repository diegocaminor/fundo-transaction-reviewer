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
