import pytest

from fundo.schema import (
    DISPLAY_NAMES,
    GROUPS,
    RISK_GROUPS,
    is_revenue,
    risk_signal_for,
    validate_business,
    validate_label,
    validate_transaction,
    validate_truth_covers,
)

CREDIT = {"amount": 100.0}
DEBIT = {"amount": -100.0}
EXCLUDING = [g for g in GROUPS if g != "none"]


def test_group_set():
    assert len(GROUPS) == 14
    assert len(EXCLUDING) == 13
    assert "none" in GROUPS
    assert set(DISPLAY_NAMES) == set(GROUPS)
    assert DISPLAY_NAMES["high_risk_gambling"] == "High risk — gambling"


def test_business_credit_no_group_is_revenue():
    assert is_revenue(CREDIT, "none", True) is True


@pytest.mark.parametrize("group", EXCLUDING)
def test_every_group_excludes_revenue(group):
    assert is_revenue(CREDIT, group, True) is False


def test_personal_credit_not_revenue():
    assert is_revenue(CREDIT, "none", False) is False


def test_debit_not_revenue():
    assert is_revenue(DEBIT, "none", True) is False


def test_risk_signal_mapping():
    assert risk_signal_for("high_risk_gambling") == "gambling"
    assert risk_signal_for("high_risk_bankruptcy") == "bankruptcy"
    assert risk_signal_for("high_risk_debt_settlement") == "debt_settlement"
    assert risk_signal_for("high_risk_garnishment") == "garnishment"
    assert risk_signal_for("high_risk_other") == "other"
    assert RISK_GROUPS == {
        g for g in GROUPS if g.startswith("high_risk_")
    }


@pytest.mark.parametrize("group", [g for g in GROUPS if g not in RISK_GROUPS])
def test_non_risk_groups_have_no_signal(group):
    assert risk_signal_for(group) is None


def test_risk_signal_rejects_unknown_group():
    with pytest.raises(ValueError):
        risk_signal_for("bogus")


def good_txn(**over):
    t = {
        "transaction_id": "txn_biz_01_0001",
        "business_id": "biz_01",
        "account_id": "acc_01",
        "date": "2026-06-01",
        "amount": 12.5,
        "iso_currency_code": "USD",
        "payment_channel": "ACH",
        "description": "CARD DEPOSIT",
        "transaction_type": "credit",
    }
    t.update(over)
    return t


def test_valid_transaction_passes():
    validate_transaction(good_txn())


@pytest.mark.parametrize(
    "field",
    [
        "transaction_id",
        "business_id",
        "account_id",
        "date",
        "amount",
        "iso_currency_code",
        "payment_channel",
        "description",
    ],
)
def test_missing_or_null_required_field(field):
    t = good_txn()
    t[field] = None
    with pytest.raises(ValueError):
        validate_transaction(t)
    del t[field]
    with pytest.raises(ValueError):
        validate_transaction(t)


def test_credit_must_be_positive():
    with pytest.raises(ValueError):
        validate_transaction(good_txn(amount=-5.0))
    with pytest.raises(ValueError):
        validate_transaction(good_txn(amount=0))


def test_debit_must_be_negative():
    validate_transaction(good_txn(amount=-5.0, transaction_type="debit"))
    with pytest.raises(ValueError):
        validate_transaction(good_txn(amount=5.0, transaction_type="debit"))


def good_business(**over):
    b = {
        "business_id": "biz_01",
        "name": "Casa Norte Restaurant",
        "type": "restaurant",
        "account_id": "acc_biz_01",
        "history_days": 90,
        "bank_charges_nsf_fee": True,
    }
    b.update(over)
    return b


def test_business_validation():
    validate_business(good_business())
    with pytest.raises(ValueError):
        validate_business(good_business(history_days=None))
    with pytest.raises(ValueError):
        validate_business(good_business(history_days=0))


def good_label(**over):
    lab = {
        "group": "none",
        "business": True,
        "revenue": True,
        "risk_signal": None,
        "notes": "",
    }
    lab.update(over)
    return lab


def test_label_validation():
    validate_label(good_label())
    with pytest.raises(ValueError):
        validate_label(good_label(group="bogus"))
    with pytest.raises(ValueError):
        validate_label(good_label(business=None))


def test_truth_covers_all_transactions():
    txns = [good_txn(), good_txn(transaction_id="txn_biz_01_0002")]
    truth = {"txn_biz_01_0001": good_label(), "txn_biz_01_0002": good_label()}
    validate_truth_covers(txns, truth)
    del truth["txn_biz_01_0002"]
    with pytest.raises(ValueError):
        validate_truth_covers(txns, truth)
    truth["txn_biz_01_0002"] = good_label(group="bogus")
    with pytest.raises(ValueError):
        validate_truth_covers(txns, truth)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    import json

    from fundo.generate import generate

    out = tmp_path_factory.mktemp("schema_gen")
    generate(42, out)
    load = lambda name: json.loads((out / name).read_text())
    return load("transactions.json"), load("ground_truth.json"), load("businesses.json")


def test_generated_truth_key_sets_equal_and_valid(generated):
    txns, truth, businesses = generated
    validate_truth_covers(txns, truth)
    for t in txns:
        validate_transaction(t)
    for b in businesses:
        validate_business(b)


def test_generated_truth_revenue_follows_rule(generated):
    txns, truth, _ = generated
    for t in txns:
        label = truth[t["transaction_id"]]
        assert label["revenue"] == is_revenue(t, label["group"], label["business"])
        assert label["risk_signal"] == risk_signal_for(label["group"])
        assert label["notes"]


def test_generated_volume_is_about_two_thousand(generated):
    txns, _, _ = generated
    assert 1800 <= len(txns) <= 2200
    assert all(t["iso_currency_code"] == "USD" for t in txns)
    assert all(t["personal_finance_category"]["primary"] for t in txns)
