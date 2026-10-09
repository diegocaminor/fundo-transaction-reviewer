import json
import random

from fundo import sensitivity as s
from fundo.offer import compute_offer
from fundo.schema import GROUPS


def txn(tid, amount, date="2026-06-30", biz="b1"):
    return {"transaction_id": tid, "business_id": biz, "date": date, "amount": amount,
            "description": tid}


def lab(group="none", business=True):
    return {"group": group, "business": business}


def biz(bid="b1", days=90, fee=True):
    return {"business_id": bid, "history_days": days, "bank_charges_nsf_fee": fee}


def small_business(n=50, bid="b1"):
    rows = [txn(f"{bid}_{i:03d}", 100.0 if i % 2 else -40.0, biz=bid) for i in range(n)]
    return rows, {r["transaction_id"]: lab() for r in rows}


def test_confusion_map_is_complete_and_realistic():
    assert set(s.CONFUSION) == set(GROUPS)
    for group, outcomes in s.CONFUSION.items():
        assert outcomes and all(w > 0 for _, w in outcomes)
        assert all(o == s.FLIP_BUSINESS or (o in GROUPS and o != group) for o, _ in outcomes)
    targets = lambda g: {o for o, _ in s.CONFUSION[g]}
    assert "internal_transfer" in targets("nsf") and "nsf" in targets("internal_transfer")
    assert "none" in targets("active_advance")
    assert all("none" in targets(g) for g in GROUPS if g.startswith("high_risk_"))
    assert {"not_average_monthly_revenue", s.FLIP_BUSINESS} <= targets("none")


def test_transaction_level_rate_one_corruption_each():
    rows, labels = small_business(50)
    for model in s.MODELS:
        new, n_group, n_flip = s.corrupt(rows, labels, 0.10, model, random.Random(1))
        changed = [t for t in labels if new[t] != labels[t]]
        assert len(changed) == round(0.10 * 50) == n_group + n_flip
        for t in changed:
            group_changed = new[t]["group"] != labels[t]["group"]
            flipped = new[t]["business"] != labels[t]["business"]
            assert group_changed != flipped  # exactly one kind of corruption
        if model == "uniform":
            assert n_flip == 0


def test_flip_probability_and_offer_distribution():
    offers = [0.0] * 30 + [1000.0] * 170
    out = s.summarize_offers(1000.0, offers)
    assert out["decision_flip_prob"] == 0.15
    d = out["offer_delta"]
    assert d["min"] == -1000.0 and d["max"] == 0.0 and d["p5"] == -1000.0 and d["p50"] == 0.0
    assert d["share_lower"] == 0.15 and d["share_higher"] == 0.0 and d["share_material"] == 0.15


def test_percentiles_nearest_rank():
    assert s.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5) == 1
    assert s.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert s.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5


def fixture():
    rows_a, lab_a = small_business(40, "b1")
    rows_b, lab_b = small_business(40, "b2")
    return rows_a + rows_b, {**lab_a, **lab_b}, [biz("b1"), biz("b2", fee=False)]


def test_grid_and_byte_identical_runs(tmp_path):
    txns, truth, businesses = fixture()
    a = s.run(txns, truth, businesses, reps=5)
    b = s.run(txns, truth, businesses, reps=5)
    s.write(tmp_path / "a.json", a)
    s.write(tmp_path / "b.json", b)
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    grid = a["monte_carlo"]["b1"]
    assert set(grid) == set(s.MODELS)
    assert all(set(grid[m]) == {"0.02", "0.05", "0.1"} for m in s.MODELS)
    cell = grid["confusion"]["0.1"]
    assert set(cell["features"]) == {"revenue_share", "nsf_count", "overdraft_count",
                                     "high_risk_debit_share", "avg_monthly_revenue",
                                     "daily_funder_payments"}
    assert set(cell["features"]["revenue_share"]) == {"mean", "p5", "p95"}
    assert cell["corruptions"]["group_change"] + cell["corruptions"]["business_flip"] == 5 * 4
    assert a["meta"]["reps"] == 5


def test_seeding_changes_with_seed_and_avoids_builtin_hash():
    txns, truth, businesses = fixture()
    assert s.run(txns, truth, businesses, reps=3, seed=1) != s.run(txns, truth, businesses, reps=3, seed=2)
    assert "hash(" not in open(s.__file__).read()


def test_nsf_observability_is_informational():
    txns, truth, businesses = fixture()
    truth["b2_001"] = lab("overdraft")
    out = s.run(txns, truth, businesses, reps=1)["observability"]
    assert out["b1"] == {"nsf_observable": True, "overdraft_count": 0, "warning": None}
    assert out["b2"]["nsf_observable"] is False and out["b2"]["overdraft_count"] == 1
    assert out["b2"]["warning"]


def test_truncation_compares_each_90_day_business_with_itself():
    rows = [txn("old", 9000.0, date="2026-04-01"), txn("new", 6100.0, date="2026-06-01")]
    truth = {"old": lab(), "new": lab()}
    out = s.run(rows, truth, [biz("b1")], reps=1)["truncation"]["b1"]
    # 90 days: revenue 15100 -> 5033.33/mo. 61 days: only "new" -> 6100 / (61/30) = 3000/mo.
    assert out["d90"]["features"]["avg_monthly_revenue"] == 5033.33
    assert out["d61"]["features"]["avg_monthly_revenue"] == 3000.0
    assert out["offer_delta"] == round(out["d61"]["offer"] - out["d90"]["offer"], 2)
    assert out["decision_flips"] is False


def test_short_history_business_gets_warning_not_truncation():
    rows = [txn("x", 1000.0)]
    out = s.run(rows, {"x": lab()}, [biz("b1", days=61)], reps=1)
    assert "b1" not in out["truncation"]
    low = out["low_history"]["b1"]
    assert low["history_days"] == 61 and low["warning"] and "nsf_x_90_over_history" in low


def test_offer_formula_untouched():
    assert compute_offer({"nsf_count": 6, "avg_monthly_revenue": 1e6, "daily_funder_payments": 0}) == 0.0
    assert json.dumps(s.run([], {}, [], reps=1)["meta"]["offer_formula_changed"]) == "false"
