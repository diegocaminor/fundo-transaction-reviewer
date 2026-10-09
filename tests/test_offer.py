from fundo.offer import compute_offer


def feats(nsf=0, od=0, avg=0.0, daily=0.0):
    return {"nsf_count": nsf, "overdraft_count": od,
            "avg_monthly_revenue": avg, "daily_funder_payments": daily}


def test_nsf_5_gets_offer():
    # 1.2 * 10000 - 20 * 100 = 12000 - 2000 = 10000.00
    assert compute_offer(feats(nsf=5, avg=10000.00, daily=100.00)) == 10000.00


def test_nsf_6_is_zero():
    assert compute_offer(feats(nsf=6, avg=10000.00, daily=100.00)) == 0


def test_floor_at_zero():
    # 1.2 * 1000 - 20 * 100 = 1200 - 2000 = -800 -> 0
    assert compute_offer(feats(avg=1000.00, daily=100.00)) == 0


def test_overdrafts_not_capped():
    # 1.2 * 5000 - 20 * 50 = 6000 - 1000 = 5000.00
    assert compute_offer(feats(nsf=0, od=10, avg=5000.00, daily=50.00)) == 5000.00


def test_rounds_to_cents():
    # 1.2 * 3333.33 = 3999.996 -> 4000.00
    assert compute_offer(feats(avg=3333.33)) == 4000.00
