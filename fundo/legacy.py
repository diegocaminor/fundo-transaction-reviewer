"""Legacy keyword classifier (deliberately naive).

Rules frozen before trap data; do not tune to data.

Ordered (keyword, group) rules, case-insensitive substring match on the raw
description, first match wins. No normalization: punctuation and whitespace
are left as-is, so "N.S.F." does not match "nsf". Only `description` and
`amount` are read; Plaid category and merchant fields are ignored.
"""

from .schema import Label, Transaction, is_revenue, risk_signal_for

_RULE_GROUPS = (
    (("nsf",), "nsf"),
    (("overdraft",), "overdraft"),
    (("ucc lien",), "ucc"),
    (("square capital", "ondeck", "mca pmt", "advance pmt"), "active_advance"),
    (("casino", "lucky", "poker"), "high_risk_gambling"),
    (("bankruptcy", "ch 13 trustee"), "high_risk_bankruptcy"),
    (("debt settlement",), "high_risk_debt_settlement"),
    (("garnishment",), "high_risk_garnishment"),
    (("pawn",), "high_risk_other"),
    (("acct verify",), "revenue_verification"),
    (("auto dep",), "auto_deposit"),
    (("refund", "reversal"), "not_average_monthly_revenue"),
    (("transfer",), "internal_transfer"),
)

RULES = [(kw, group) for kws, group in _RULE_GROUPS for kw in kws]


def classify(txn: Transaction) -> Label:
    description = txn["description"].lower()
    group, notes = "none", "legacy: no rule matched"
    for keyword, rule_group in RULES:
        if keyword in description:
            group, notes = rule_group, f"legacy rule: {keyword}"
            break
    business = True
    return {
        "group": group,
        "business": business,
        "revenue": is_revenue(txn, group, business),
        "risk_signal": risk_signal_for(group),
        "notes": notes,
    }


def classify_all(txns) -> dict[str, Label]:
    return {t["transaction_id"]: classify(t) for t in txns}
