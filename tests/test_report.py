import json

from fundo.report import build_report

BIZ = lambda i: {
    "business_id": i, "name": i, "type": "t", "account_id": "a",
    "history_days": 30, "bank_charges_nsf_fee": True,
}


def T(tid, biz, amount, desc="X"):
    return {"transaction_id": tid, "business_id": biz, "account_id": "a", "date": "2026-06-01",
            "description": desc, "amount": amount}


def L(group, business=True):
    return {"group": group, "business": business, "revenue": False, "risk_signal": None, "notes": ""}


def fixture():
    businesses = [BIZ("b2"), BIZ("b1"), BIZ("b3")]
    txns = [
        # b1: one collateral mislabel (credit 500) and one planned (funder debit)
        T("a1", "b1", 3000.0), T("a2", "b1", 500.0), T("a3", "b1", -50.0),
        # b2: six clean credits, legacy calls them nsf (collateral) -> false decline
        *[T(f"b{i}", "b2", 1000.0) for i in range(6)],
        # b3: six NSF fees, legacy misses them (planned) -> approves a decline
        T("c0", "b3", 5000.0), *[T(f"c{i}", "b3", -35.0) for i in range(1, 7)],
    ]
    truth = {t["transaction_id"]: L("none") for t in txns}
    truth["a3"] = L("active_advance")
    for i in range(1, 7):
        truth[f"c{i}"] = L("nsf")
    legacy = {t["transaction_id"]: L("none") for t in txns}
    legacy["a2"] = L("internal_transfer")
    for i in range(6):
        legacy[f"b{i}"] = L("nsf")
    traps = {"a3": "funder_debit", **{f"c{i}": "nsf_miss" for i in range(1, 7)}}
    return businesses, txns, truth, legacy, traps


def test_sorted_and_structure():
    r = build_report(*fixture())
    assert list(r) == ["b1", "b2", "b3"]
    assert r["b1"]["n_txns"] == 3
    assert set(r["b1"]) >= {"n_txns", "accuracy", "features", "offer", "mislabels", "decision",
                            "collateral_only", "planned_only"}
    assert set(r["b1"]["features"]) == {"truth", "legacy", "delta"}


def test_accuracy_and_offers_b1():
    b = build_report(*fixture())["b1"]
    assert b["accuracy"]["group"] == round(1 / 3, 4)
    assert b["accuracy"]["business"] == 1.0
    assert b["accuracy"]["revenue"] == round(2 / 3, 4)  # a2 revenue differs
    assert b["offer"] == {"truth": 3200.0, "legacy": 3600.0, "delta": 400.0}
    assert b["features"]["delta"]["avg_monthly_revenue"] == -500.0


def test_attribution_b1():
    b = build_report(*fixture())["b1"]
    assert b["mislabels"] == {
        "planned": 1, "unplanned": 1,
        "planned_by_trap": {"funder_debit": 1},
        "unplanned_by_pattern": {"none->internal_transfer": 1},
    }
    assert b["collateral_only"]["offer"] == 2600.0
    assert b["planned_only"]["offer"] == 4200.0
    assert b["collateral_flips_decision"] is False
    assert b["decision"] == {"truth": "approve", "legacy": "approve", "flipped": False}


def test_collateral_flip_false_decline():
    b = build_report(*fixture())["b2"]
    assert b["decision"] == {"truth": "approve", "legacy": "decline", "flipped": True}
    assert b["mislabels"]["planned"] == 0 and b["mislabels"]["unplanned"] == 6
    assert b["mislabels"]["unplanned_by_pattern"] == {"none->nsf": 6}
    assert b["collateral_only"]["decision"] == "decline"
    assert b["collateral_flips_decision"] is True


def test_planned_flip_not_collateral():
    b = build_report(*fixture())["b3"]
    assert b["decision"] == {"truth": "decline", "legacy": "approve", "flipped": True}
    assert b["collateral_flips_decision"] is False
    assert b["planned_only"]["decision"] == "approve"
    assert b["mislabels"]["planned_by_trap"] == {"nsf_miss": 6}


def test_json_serializable():
    json.dumps(build_report(*fixture()), sort_keys=True)


def test_collateral_changes_outcome():
    r = build_report(*fixture())
    # legacy decision vs planned_only decision (legacy on traps, truth elsewhere)
    assert r["b1"]["collateral_changes_outcome"] is False
    assert r["b2"]["collateral_changes_outcome"] is True   # collateral alone causes the decline
    assert r["b3"]["collateral_changes_outcome"] is False  # planned traps decide the outcome
