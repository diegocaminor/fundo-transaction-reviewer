"""Invariants of the frozen adversarial set (not model outcomes)."""

import json
from pathlib import Path

from fundo.schema import GROUPS, validate_transaction

ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((ROOT / "data/adversarial.json").read_text())
ITEMS = DOC["items"]


def test_small_and_versioned():
    assert DOC["version"] == 1 and 8 <= len(ITEMS) <= 15


def test_every_injection_conflicts_with_the_true_label():
    for item in ITEMS:
        assert item["injected_target"] != item["expected"], item["id"]
        assert item["expected"]["group"] in GROUPS and item["injected_target"]["group"] in GROUPS


def test_several_styles_beyond_ignore_previous_instructions():
    styles = {item["style"] for item in ITEMS}
    assert len(styles) >= 8
    plain_ignore = [i for i in ITEMS if "IGNORE PREVIOUS INSTRUCTIONS" in i["txn"]["description"].upper()]
    assert len(plain_ignore) <= 1


def test_injections_push_in_both_credit_directions():
    def revenue(label):
        return label["group"] == "none" and label["business"]
    toward_revenue = [i for i in ITEMS if revenue(i["injected_target"]) and not revenue(i["expected"])]
    toward_risk = [i for i in ITEMS if i["injected_target"]["group"] in ("nsf",) or
                   i["injected_target"]["group"].startswith("high_risk_")]
    assert toward_revenue and toward_risk


def test_transactions_are_valid_and_outside_the_business_dataset():
    business_ids = {t["transaction_id"] for t in json.loads((ROOT / "data/transactions.json").read_text())}
    hosts = {b["business_id"] for b in json.loads((ROOT / "data/businesses.json").read_text())}
    for item in ITEMS:
        validate_transaction(item["txn"])
        assert item["txn"]["transaction_id"] == item["id"] not in business_ids
        assert item["host_business_id"] == item["txn"]["business_id"] in hosts
