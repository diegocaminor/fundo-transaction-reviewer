"""Offer formula. The floor at 0 is an explicit assumption."""

NSF_LIMIT = 5


def compute_offer(features):
    """0 if NSF count > 5 (overdrafts excluded), else max(0, 1.2*rev - 20*funder)."""
    if features["nsf_count"] > NSF_LIMIT:
        return 0.0
    raw = 1.2 * features["avg_monthly_revenue"] - 20 * features["daily_funder_payments"]
    return round(max(0.0, raw), 2)
