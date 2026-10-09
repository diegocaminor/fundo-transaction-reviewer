"""Tests the evaluator on synthetic report entries, not the dataset outcome."""

import copy

import pytest

from fundo import hypotheses as H

FEATS = {"avg_monthly_revenue": 0.0, "daily_funder_payments": 0.0, "high_risk_debit_share": 0.0,
         "nsf_count": 0, "overdraft_count": 0, "revenue_share": 0.0}


def entry(truth_offer=1000.0, legacy_offer=1000.0, truth=None, legacy=None, mislabels=0):
    t, l = {**FEATS, **(truth or {})}, {**FEATS, **(legacy or {})}
    return {
        "accuracy": {"group": 1.0 if not mislabels else 0.9, "business": 1.0, "revenue": 1.0},
        "mislabels": {"planned": mislabels, "unplanned": 0},
        "features": {"truth": t, "legacy": l, "delta": {k: round(l[k] - t[k], 4) for k in t}},
        "offer": {"truth": truth_offer, "legacy": legacy_offer,
                  "delta": round(legacy_offer - truth_offer, 2)},
    }


def rev_up(legacy_offer=1100.0):
    return entry(truth_offer=1000.0, legacy_offer=legacy_offer,
                 truth={"avg_monthly_revenue": 100.0, "daily_funder_payments": 10.0},
                 legacy={"avg_monthly_revenue": 200.0, "daily_funder_payments": 5.0})

CASES = {
    "biz_01": (rev_up(), rev_up(1005.0)),  # 0.5% is below materiality
    "biz_02": (entry(), entry(legacy={"nsf_count": 2})),
    "biz_03": (entry(), entry(mislabels=1)),
    "biz_04": (rev_up(), rev_up(900.0)),
    "biz_05": (entry(truth_offer=1000.0, legacy_offer=1100.0, truth={"avg_monthly_revenue": 100.0},
                legacy={"avg_monthly_revenue": 150.0}),
               entry(truth_offer=1000.0, legacy_offer=1100.0)),  # no revenue inflation
    "biz_06": (entry(legacy={"high_risk_debit_share": 0.1}), entry(legacy={"high_risk_debit_share": 0.1},
                                                                 legacy_offer=1200.0)),
    "biz_07": (entry(truth={"high_risk_debit_share": 0.1}), entry()),
    "biz_08": (entry(truth_offer=500.0, legacy_offer=0.0, truth={"nsf_count": 0}, legacy={"nsf_count": 9}),
               entry(truth_offer=500.0, legacy_offer=500.0)),
    "biz_09": (entry(truth_offer=0.0, legacy_offer=800.0, truth={"nsf_count": 6}, legacy={"nsf_count": 5}),
               entry(truth_offer=0.0, legacy_offer=0.0, truth={"nsf_count": 6}, legacy={"nsf_count": 7})),
    "biz_10": (entry(), entry(legacy_offer=1000.01)),
}


@pytest.mark.parametrize("bid", sorted(CASES))
def test_passing_and_failing_entries(bid):
    good, bad = CASES[bid]
    ok, obs = H.CHECKS[bid](good)
    assert ok is True and isinstance(obs, str) and obs
    ok, obs = H.CHECKS[bid](bad)
    assert ok is False and obs


def test_biz_01_materiality_boundary():
    at_one_percent = rev_up(1010.0)  # exactly 1% is not "exceeds"
    assert H.check_biz_01(at_one_percent)[0] is False


def test_biz_09_requires_exact_nsf_counts():
    e = entry(truth_offer=0.0, legacy_offer=800.0, truth={"nsf_count": 7}, legacy={"nsf_count": 5})
    assert H.check_biz_09(e)[0] is False


def test_predictions_cover_all_businesses_verbatim():
    assert sorted(H.PREDICTIONS) == sorted(H.CHECKS) == [f"biz_{i:02d}" for i in range(1, 11)]


def test_evaluate_records():
    report = {f"biz_{i:02d}": copy.deepcopy(entry()) for i in range(1, 11)}
    recs = H.evaluate(report)
    assert [r["business_id"] for r in recs] == sorted(report)
    assert all(set(r) == {"business_id", "prediction", "status", "observed"} for r in recs)
    assert all(r["prediction"] == H.PREDICTIONS[r["business_id"]] for r in recs)
    assert {r["status"] for r in recs} <= {"passed", "failed"}
    assert next(r for r in recs if r["business_id"] == "biz_03")["status"] == "passed"
