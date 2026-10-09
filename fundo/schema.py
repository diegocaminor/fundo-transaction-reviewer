"""Shared schema and deterministic rules.

Sign convention (Fundo PDF): credit amounts are positive, debit amounts are
negative. This is the reverse of native Plaid, where debits are positive.
"""

from typing import NotRequired, TypedDict

DISPLAY_NAMES = {
    "not_average_monthly_revenue": "Not average monthly revenue",
    "nsf": "NSFs",
    "overdraft": "Overdraft",
    "internal_transfer": "Internal transfer",
    "ucc": "UCC",
    "active_advance": "Active advance",
    "auto_deposit": "Auto deposit",
    "revenue_verification": "Revenue verification",
    "high_risk_gambling": "High risk — gambling",
    "high_risk_bankruptcy": "High risk — bankruptcy",
    "high_risk_debt_settlement": "High risk — debt settlement",
    "high_risk_garnishment": "High risk — garnishment",
    "high_risk_other": "High risk — other",
    "none": "None",
}

GROUPS = tuple(DISPLAY_NAMES)
RISK_GROUPS = frozenset(g for g in GROUPS if g.startswith("high_risk_"))
HIGH_RISK_PREFIX = "high_risk_"


class PersonalFinanceCategory(TypedDict):
    primary: str
    detailed: str


class Transaction(TypedDict):
    transaction_id: str
    business_id: str
    account_id: str
    date: str
    description: str
    amount: float
    iso_currency_code: str
    payment_channel: str
    merchant_name: NotRequired[str | None]
    pending: bool
    transaction_type: str
    personal_finance_category: PersonalFinanceCategory


class Business(TypedDict):
    business_id: str
    name: str
    type: str
    account_id: str
    history_days: int
    bank_charges_nsf_fee: bool


class Label(TypedDict):
    group: str
    business: bool
    revenue: bool
    risk_signal: str | None
    notes: str


def is_revenue(txn, group: str, business: bool) -> bool:
    """Revenue = credit AND business AND no excluding group."""
    return txn["amount"] > 0 and bool(business) and group == "none"


def risk_signal_for(group: str) -> str | None:
    if group not in GROUPS:
        raise ValueError(f"unknown group: {group!r}")
    if group in RISK_GROUPS:
        return group[len(HIGH_RISK_PREFIX):]
    return None


_TXN_REQUIRED = (
    "transaction_id",
    "business_id",
    "account_id",
    "date",
    "description",
    "amount",
    "iso_currency_code",
    "payment_channel",
)
_BIZ_REQUIRED = (
    "business_id",
    "name",
    "type",
    "account_id",
    "history_days",
    "bank_charges_nsf_fee",
)
_LABEL_REQUIRED = ("group", "business", "revenue")


def _require(record, fields, kind):
    for f in fields:
        if record.get(f) is None:
            raise ValueError(f"{kind}: missing or null field {f!r}")


def validate_transaction(txn) -> None:
    _require(txn, _TXN_REQUIRED, "transaction")
    kind = txn.get("transaction_type", "credit" if txn["amount"] > 0 else "debit")
    if kind == "credit" and not txn["amount"] > 0:
        raise ValueError("transaction: credit amount must be > 0")
    if kind == "debit" and not txn["amount"] < 0:
        raise ValueError("transaction: debit amount must be < 0")


def validate_business(biz) -> None:
    _require(biz, _BIZ_REQUIRED, "business")
    if biz["history_days"] <= 0:
        raise ValueError("business: history_days must be > 0")


def validate_label(label) -> None:
    _require(label, _LABEL_REQUIRED, "label")
    if label["group"] not in GROUPS:
        raise ValueError(f"label: invalid group {label['group']!r}")


def validate_truth_covers(txns, truth) -> None:
    ids = {t["transaction_id"] for t in txns}
    if ids != set(truth):
        raise ValueError("truth: key set differs from transaction ids")
    for label in truth.values():
        validate_label(label)
