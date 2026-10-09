"""Credit features computed from (txns, labels, business).

Label-source-agnostic: `labels` is {transaction_id: Label} from truth, the
legacy engine, or LLM-corrected labels. Revenue is recomputed with the shared
`is_revenue` rule from group and business, never read from `label["revenue"]`.
Amounts follow the schema sign convention (credits > 0, debits < 0).
"""

from collections import defaultdict

from fundo.schema import RISK_GROUPS, is_revenue


def _ratio(num, den):
    return round(num / den, 4) if den else 0.0


def compute_features(txns, labels, business):
    credits = revenue = high_risk = debits = 0.0
    nsf = overdraft = 0
    funder_by_day = defaultdict(float)
    for t in txns:
        label = labels[t["transaction_id"]]
        group, amount = label["group"], t["amount"]
        if amount > 0:
            credits += amount
            if is_revenue(t, group, label["business"]):
                revenue += amount
        else:
            debits += -amount
            if group in RISK_GROUPS:
                high_risk += -amount
            if group == "active_advance":
                funder_by_day[t["date"]] += -amount
        if group == "nsf":
            nsf += 1
        elif group == "overdraft":
            overdraft += 1
    daily = sum(funder_by_day.values()) / len(funder_by_day) if funder_by_day else 0.0
    return {
        "revenue_share": _ratio(revenue, credits),
        "nsf_count": nsf,
        "overdraft_count": overdraft,
        "high_risk_debit_share": _ratio(high_risk, debits),
        "avg_monthly_revenue": round(revenue / (business["history_days"] / 30), 2),
        "daily_funder_payments": round(daily, 2),
    }
