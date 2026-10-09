import pytest

from fundo import legacy
from fundo.schema import GROUPS, is_revenue


def txn(description, amount=-10.0, **extra):
    t = {
        "transaction_id": "t1",
        "business_id": "biz_x",
        "account_id": "a1",
        "date": "2026-01-01",
        "description": description,
        "amount": amount,
        "iso_currency_code": "USD",
        "payment_channel": "other",
        "merchant_name": "SHOULD NOT BE READ",
        "personal_finance_category": {"primary": "X", "detailed": "Y"},
    }
    t.update(extra)
    return t


def group(description):
    return legacy.classify(txn(description))["group"]


@pytest.mark.parametrize(
    "description,expected",
    [
        ("NSF FEE", "nsf"),
        ("Overdraft charge", "overdraft"),
        ("UCC LIEN FILING", "ucc"),
        ("SQUARE CAPITAL REPAY", "active_advance"),
        ("ONDECK PAYMENT", "active_advance"),
        ("XYZ MCA PMT", "active_advance"),
        ("ADVANCE PMT 01", "active_advance"),
        ("GRAND CASINO", "high_risk_gambling"),
        ("LUCKY DRAGON", "high_risk_gambling"),
        ("POKER STARS", "high_risk_gambling"),
        ("BANKRUPTCY FILING", "high_risk_bankruptcy"),
        ("CH 13 TRUSTEE PMT", "high_risk_bankruptcy"),
        ("DEBT SETTLEMENT CO", "high_risk_debt_settlement"),
        ("WAGE GARNISHMENT", "high_risk_garnishment"),
        ("PAWN SHOP", "high_risk_other"),
        ("ACCT VERIFY 2 DEPOSITS", "revenue_verification"),
        ("AUTO DEP PAYROLL", "auto_deposit"),
        ("CUSTOMER REFUND", "not_average_monthly_revenue"),
        ("PAYMENT REVERSAL", "not_average_monthly_revenue"),
    ],
)
def test_each_rule_fires(description, expected):
    assert group(description) == expected


def test_rules_in_design_order():
    groups = []
    for _, g in legacy.RULES:
        if g not in groups:
            groups.append(g)
    assert groups == [
        "nsf", "overdraft", "ucc", "active_advance", "high_risk_gambling",
        "high_risk_bankruptcy", "high_risk_debt_settlement",
        "high_risk_garnishment", "high_risk_other", "revenue_verification",
        "auto_deposit", "not_average_monthly_revenue", "internal_transfer",
    ]
    assert all(g in GROUPS for _, g in legacy.RULES)


def test_earlier_rule_wins():
    assert group("NSF FEE OVERDRAFT") == "nsf"
    assert group("OVERDRAFT UCC LIEN") == "overdraft"
    assert group("CASINO REFUND") == "high_risk_gambling"


def test_case_insensitive():
    assert group("nsf Fee") == "nsf"
    assert group("LuCkY") == "high_risk_gambling"


def test_no_match_is_none():
    assert group("CARD PROCESSOR SETTLEMENT") == "none"


def test_punctuation_defeats_keyword():
    assert group("N.S.F. FEE") == "none"
    assert group("ONLINE XFER FROM SAV") == "none"
    assert group("SQUARE-CAPITAL REPAY") == "none"


def test_no_whitespace_collapsing():
    assert group("SQUARE  CAPITAL") == "none"
    assert group("UCC  LIEN") == "none"


def test_lucky_false_positive():
    assert group("Lucky Dragon Chinese Buffet") == "high_risk_gambling"


def test_transfer_keyword_is_shadowed_by_nsf():
    # "transfer" contains the substring "nsf" (tra-NSF-er), so the earlier
    # nsf rule always wins and the final transfer rule is unreachable.
    assert group("WIRE TRANSFER FROM CUSTOMER INC") == "nsf"
    assert ("transfer", "internal_transfer") in legacy.RULES


def test_substring_inside_word_matches():
    assert group("FINSFORD SUPPLY") == "nsf"


def test_does_not_read_category_or_merchant():
    a = legacy.classify(txn("PLAIN DEBIT"))
    b = legacy.classify(
        txn(
            "PLAIN DEBIT",
            merchant_name="CASINO",
            personal_finance_category={"primary": "GAMBLING", "detailed": "CASINO"},
        )
    )
    assert a == b
    c = legacy.classify({"description": "PLAIN DEBIT", "amount": -1.0})
    assert c["group"] == "none"


def test_label_shape_matches_truth():
    label = legacy.classify(txn("NSF FEE"))
    assert set(label) == {"group", "business", "revenue", "risk_signal", "notes"}
    assert isinstance(label["notes"], str) and label["notes"]


def test_notes_names_keyword_or_no_match():
    assert "nsf" in legacy.classify(txn("NSF FEE"))["notes"]
    assert "no rule matched" in legacy.classify(txn("HELLO"))["notes"]


def test_business_defaults_true_and_personal_credit_is_revenue():
    t = txn("MOM BIRTHDAY GIFT", amount=200.0)
    label = legacy.classify(t)
    assert label["group"] == "none"
    assert label["business"] is True
    assert label["revenue"] is True
    assert label["revenue"] == is_revenue(t, label["group"], True)


def test_debit_never_revenue_and_excluded_credit_not_revenue():
    assert legacy.classify(txn("HELLO", amount=-5.0))["revenue"] is False
    assert legacy.classify(txn("TRANSFER IN", amount=50.0))["revenue"] is False


def test_risk_signal_mapping():
    assert legacy.classify(txn("CASINO"))["risk_signal"] == "gambling"
    assert legacy.classify(txn("NSF"))["risk_signal"] is None


def test_classify_all_keyed_by_transaction_id():
    txns = [txn("NSF", transaction_id="a"), txn("HELLO", transaction_id="b")]
    labels = legacy.classify_all(txns)
    assert set(labels) == {"a", "b"}
    assert labels["a"]["group"] == "nsf"
