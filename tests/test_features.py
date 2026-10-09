from fundo.features import compute_features


def txn(tid, date, amount):
    return {"transaction_id": tid, "date": date, "amount": amount}


def lab(group="none", business=True, revenue=None):
    return {"group": group, "business": business,
            "revenue": (group == "none" and business) if revenue is None else revenue}


def biz(days=30):
    return {"business_id": "b", "history_days": days}


def run(rows, days=30):
    """rows: (date, amount, group[, business])"""
    txns, labels = [], {}
    for i, r in enumerate(rows):
        tid = f"t{i}"
        txns.append(txn(tid, r[0], r[1]))
        labels[tid] = lab(r[2], r[3] if len(r) > 3 else True)
    return compute_features(txns, labels, biz(days))


def test_61_day_normalization():
    # 3000.00 + 3100.00 = 6100.00 revenue; 6100 / (61/30) = 3000.00
    f = run([("2026-01-01", 3000.00, "none"), ("2026-01-02", 3100.00, "none")], days=61)
    assert f["avg_monthly_revenue"] == 3000.00


def test_revenue_share_is_dollar_weighted():
    # revenue 6100 of credits 8000 (1900 internal transfer) -> 0.7625
    f = run([("2026-01-01", 6100.00, "none"), ("2026-01-02", 1900.00, "internal_transfer")])
    assert f["revenue_share"] == 0.7625


def test_revenue_recomputed_not_read_from_label():
    # stale label says revenue=True but group excludes it -> not revenue
    txns = [txn("a", "2026-01-01", 1000.00)]
    labels = {"a": lab("internal_transfer", True, revenue=True)}
    f = compute_features(txns, labels, biz(30))
    assert f["avg_monthly_revenue"] == 0.0
    # personal credit with stale revenue=True is also excluded
    labels = {"a": lab("none", False, revenue=True)}
    assert compute_features(txns, labels, biz(30))["avg_monthly_revenue"] == 0.0


def test_funder_mean_over_days_with_debits():
    # day1: 100; day2: 100 + 50 = 150; day3 none -> (100 + 150) / 2 = 125.00
    f = run([("2026-01-01", -100.00, "active_advance"),
             ("2026-01-02", -100.00, "active_advance"),
             ("2026-01-02", -50.00, "active_advance"),
             ("2026-01-03", -20.00, "none")])
    assert f["daily_funder_payments"] == 125.00


def test_no_funder_debits_is_zero():
    f = run([("2026-01-01", -20.00, "none")])
    assert f["daily_funder_payments"] == 0.0


def test_overdraft_only_has_no_nsf():
    f = run([("2026-01-01", -35.00, "overdraft"), ("2026-01-02", -35.00, "overdraft")])
    assert f["nsf_count"] == 0
    assert f["overdraft_count"] == 2


def test_nsf_counted_separately():
    f = run([("2026-01-01", -35.00, "nsf"), ("2026-01-02", -35.00, "overdraft"),
             ("2026-01-03", -35.00, "nsf")])
    assert f["nsf_count"] == 2
    assert f["overdraft_count"] == 1


def test_high_risk_share_dollar_weighted():
    # high risk 300 + 100 = 400 of 1000 debits (600 plain) -> 0.4
    f = run([("2026-01-01", -300.00, "high_risk_gambling"),
             ("2026-01-02", -100.00, "high_risk_other"),
             ("2026-01-03", -600.00, "none"),
             ("2026-01-04", 5000.00, "none")])
    assert f["high_risk_debit_share"] == 0.4


def test_zero_denominators():
    f = run([])
    assert f["revenue_share"] == 0.0
    assert f["high_risk_debit_share"] == 0.0
    assert f["avg_monthly_revenue"] == 0.0
    assert f["daily_funder_payments"] == 0.0
    assert f["nsf_count"] == 0 and f["overdraft_count"] == 0


def test_rounding():
    # 1/3 share -> 4 dp ; 100.005 style money -> 2 dp
    f = run([("2026-01-01", 100.00, "none"), ("2026-01-02", 200.00, "internal_transfer")])
    assert f["revenue_share"] == 0.3333
    # revenue 100 over 7 days: 100 / (7/30) = 428.571... -> 428.57
    g = run([("2026-01-01", 100.00, "none")], days=7)
    assert g["avg_monthly_revenue"] == 428.57


def test_label_source_agnostic():
    txns = [txn("a", "2026-01-01", 1000.00), txn("b", "2026-01-02", 500.00)]
    b = biz(30)
    set_a = {"a": lab("none"), "b": lab("none")}
    set_b = {"a": lab("none"), "b": lab("internal_transfer")}
    fa = compute_features(txns, set_a, b)
    fb = compute_features(txns, set_b, b)
    # A: revenue 1500 / 1 month; B: only 1000
    assert fa["avg_monthly_revenue"] == 1500.00
    assert fb["avg_monthly_revenue"] == 1000.00
    assert fa["revenue_share"] == 1.0
    assert fb["revenue_share"] == 0.6667
    assert fa["nsf_count"] == fb["nsf_count"] == 0
