"""Pre-registered per-business predictions and their literal checks.

PREDICTIONS hold the original text from the proposal, never edited after the
fact. Each check takes one business entry of the baseline report and returns
(passed, observed): whether the prediction holds and the numbers that decided
it. Delta = legacy - truth. Direction predictions use a 1% materiality
threshold on the truth offer (a project choice, not a challenge requirement).
"""

MATERIALITY = 0.01

PREDICTIONS = {
    "biz_01": "Revenue inflated, funder payments understated → offer **higher**",
    "biz_02": "NSF = 0 in both; overdraft risk invisible to legacy; offer **unchanged** (risk hidden, not priced)",
    "biz_03": "Labels and offer **exactly equal**; avg monthly revenue uses history_days / 30",
    "biz_04": "Revenue inflated, funder payments understated → offer **higher**",
    "biz_05": "Revenue inflated → offer **higher**",
    "biz_06": "High-risk share **overstated**; offer **unchanged**",
    "biz_07": "High-risk share **understated**; offer **unchanged**",
    "biz_08": "Legacy NSF > 5, truth NSF ≤ 5 → legacy offer = 0, truth offer > 0 → **false decline**",
    "biz_09": "Truth offer = 0, legacy offer > 0 → **approves a decline**",
    "biz_10": "Labels and offer **exactly equal**",
}


def _material_up(e):
    return e["offer"]["delta"] > MATERIALITY * e["offer"]["truth"]


def _nsf(e):
    return e["features"]["truth"]["nsf_count"], e["features"]["legacy"]["nsf_count"]


def _offers(e):
    return e["offer"]["truth"], e["offer"]["legacy"]


def _labels_equal(e):
    m, a = e["mislabels"], e["accuracy"]
    return m["planned"] + m["unplanned"] == 0 and all(v == 1.0 for v in a.values())


def _all_deltas_zero(e):
    return all(v == 0 for v in e["features"]["delta"].values()) and e["offer"]["delta"] == 0


def _fd(e):
    return e["features"]["delta"]


def _revenue_and_funder_up(e):
    ok = _fd(e)["avg_monthly_revenue"] > 0 and _fd(e)["daily_funder_payments"] < 0 and _material_up(e)
    obs = (f"revenue delta {_fd(e)['avg_monthly_revenue']}, funder delta "
           f"{_fd(e)['daily_funder_payments']}, offer delta {e['offer']['delta']} "
           f"(truth offer {e['offer']['truth']})")
    return ok, obs


def check_biz_01(e):
    return _revenue_and_funder_up(e)


def check_biz_02(e):
    t, l = _nsf(e)
    ok = t == 0 and l == 0 and e["offer"]["delta"] == 0
    return ok, f"NSF truth {t}, legacy {l}, offer delta {e['offer']['delta']}"


def check_biz_03(e):
    ok = _labels_equal(e) and _all_deltas_zero(e)
    m = e["mislabels"]
    return ok, (f"mislabels {m['planned'] + m['unplanned']}, offer delta {e['offer']['delta']}, "
                f"all feature deltas zero: {all(v == 0 for v in _fd(e).values())}")


def check_biz_04(e):
    return _revenue_and_funder_up(e)


def check_biz_05(e):
    ok = _fd(e)["avg_monthly_revenue"] > 0 and _material_up(e)
    return ok, (f"revenue delta {_fd(e)['avg_monthly_revenue']}, offer delta {e['offer']['delta']} "
                f"(truth offer {e['offer']['truth']})")


def check_biz_06(e):
    ok = _fd(e)["high_risk_debit_share"] > 0 and e["offer"]["delta"] == 0
    return ok, f"high-risk share delta {_fd(e)['high_risk_debit_share']}, offer delta {e['offer']['delta']}"


def check_biz_07(e):
    ok = _fd(e)["high_risk_debit_share"] < 0 and e["offer"]["delta"] == 0
    return ok, f"high-risk share delta {_fd(e)['high_risk_debit_share']}, offer delta {e['offer']['delta']}"


def check_biz_08(e):
    t, l = _nsf(e)
    to, lo = _offers(e)
    ok = l > 5 and t <= 5 and lo == 0 and to > 0
    return ok, f"NSF legacy {l}, truth {t}; offer legacy {lo}, truth {to}"


def check_biz_09(e):
    t, l = _nsf(e)
    to, lo = _offers(e)
    ok = l == 5 and t == 6 and to == 0 and lo > 0
    return ok, f"NSF legacy {l}, truth {t}; offer legacy {lo}, truth {to}"


def check_biz_10(e):
    ok = _labels_equal(e) and _all_deltas_zero(e)
    m = e["mislabels"]
    return ok, f"mislabels {m['planned'] + m['unplanned']}, offer delta {e['offer']['delta']}"


CHECKS = {f"biz_{i:02d}": globals()[f"check_biz_{i:02d}"] for i in range(1, 11)}


def evaluate(report):
    """One record per business; the prediction text is carried verbatim."""
    out = []
    for bid in sorted(CHECKS):
        passed, observed = CHECKS[bid](report[bid])
        out.append({"business_id": bid, "prediction": PREDICTIONS[bid],
                    "status": "passed" if passed else "failed", "observed": observed})
    return out
