"""Measured baseline (seed 42) and system invariants.

These assert what the legacy engine actually does on the generated data. The
original pre-registered hypotheses, and which of them held, live in the report
(fundo/hypotheses.py), not here.
"""

import json

import pytest

from fundo import schema
from fundo.features import compute_features
from fundo.generate import generate
from fundo.report import write_report


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("baseline")
    generate(42, out)
    doc = write_report(out)
    load = lambda n: json.loads((out / n).read_text())
    return {
        "doc": doc, "report": doc["businesses"],
        "businesses": load("businesses.json"), "txns": load("transactions.json"),
        "truth": load("ground_truth.json"), "traps": load("traps.json"),
        "legacy": load("legacy_labels.json"),
    }


def test_legacy_groups_valid(run):
    assert set(run["legacy"]) == set(run["truth"])
    assert {v["group"] for v in run["legacy"].values()} <= set(schema.GROUPS)


def test_planned_plus_unplanned_equals_mismatches(run):
    mismatches = {}
    for t in run["txns"]:
        a, b = run["truth"][t["transaction_id"]], run["legacy"][t["transaction_id"]]
        if (a["group"], a["business"]) != (b["group"], b["business"]):
            mismatches[t["business_id"]] = mismatches.get(t["business_id"], 0) + 1
    for bid, r in run["report"].items():
        assert r["mislabels"]["planned"] + r["mislabels"]["unplanned"] == mismatches.get(bid, 0)


def test_decision_is_decline_iff_offer_zero(run):
    for r in run["report"].values():
        for side in ("truth", "legacy"):
            assert (r["decision"][side] == "decline") == (r["offer"][side] == 0)
        for part in ("collateral_only", "planned_only"):
            assert (r[part]["decision"] == "decline") == (r[part]["offer"] == 0)


def test_legacy_revenue_flag_matches_rule(run):
    by_id = {t["transaction_id"]: t for t in run["txns"]}
    for tid, lab in run["legacy"].items():
        assert lab["revenue"] == schema.is_revenue(by_id[tid], lab["group"], lab["business"])


def test_collateral_only_uses_truth_on_trap_txns(run):
    bid = "biz_01"
    biz = next(b for b in run["businesses"] if b["business_id"] == bid)
    rows = [t for t in run["txns"] if t["business_id"] == bid]
    assert any(t["transaction_id"] in run["traps"] for t in rows)
    mixed = {t["transaction_id"]: (run["truth"] if t["transaction_id"] in run["traps"]
                                   else run["legacy"])[t["transaction_id"]] for t in rows}
    assert run["report"][bid]["collateral_only"]["features"] == compute_features(rows, mixed, biz)


def test_every_business_has_only_substring_nsf_collateral(run):
    for bid, r in run["report"].items():
        assert r["mislabels"]["unplanned"] >= 1, bid
        assert set(r["mislabels"]["unplanned_by_pattern"]) == {"internal_transfer->nsf"}, bid


def test_biz_08_false_decline(run):
    r = run["report"]["biz_08"]
    assert r["decision"] == {"truth": "approve", "legacy": "decline", "flipped": True}
    assert r["planned_only"]["decision"] == "decline"
    assert r["collateral_only"]["decision"] == "approve"


def test_biz_09_two_legacy_bugs_cancel(run):
    r = run["report"]["biz_09"]
    assert r["planned_only"]["decision"] == "approve"
    assert r["planned_only"]["features"]["nsf_count"] == 5
    assert r["features"]["legacy"]["nsf_count"] == 7
    assert r["features"]["truth"]["nsf_count"] == 6
    assert r["decision"]["legacy"] == r["decision"]["truth"] == "decline"
    assert r["collateral_changes_outcome"] is True


@pytest.mark.parametrize("bid", ["biz_03", "biz_10"])
def test_clean_businesses_nsf_moves_but_offer_does_not(run, bid):
    r = run["report"][bid]
    assert r["offer"]["delta"] == 0
    assert r["features"]["delta"]["nsf_count"] == 2
