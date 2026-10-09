"""Check functions on synthetic report documents (the evaluator, not the real outcome)."""

from fundo import reviewer_hypotheses as rh


def doc(**over):
    def biz(decision="approve", nsf=0, legacy_err=100.0, reviewed_err=10.0):
        return {"decision": {"truth": "approve", "legacy": "decline", "reviewed": decision},
                "features": {k: {"nsf_count": nsf} for k in ("truth", "legacy", "reviewed")},
                "offer_error": {"legacy": legacy_err, "reviewed": reviewed_err}}
    businesses = {"biz_08": biz(over.get("biz08", "approve")),
                  "biz_09": biz("decline", over.get("biz09_nsf", 6))}
    return {"variants": {"pfc": {
        "primary": {"businesses": businesses,
                    "dollar_error": {"revenue_usd": {"legacy": 1000.0, "reviewed": over.get("rev_usd", 400.0)}},
                    "hard_negatives": {"proposed": {"count": over.get("hn_p", 8)},
                                       "accepted": {"count": over.get("hn_a", 2)}}},
        "status_counts": {"confirmed": 90, "corrected": 10 - over.get("failed", 0),
                          "review_failed": over.get("failed", 0)}}},
        "adversarial": {"adv_pfc": {"n": 12, "complied": over.get("complied", 1)}}}


def statuses(d):
    return {h["id"]: h["status"] for h in rh.evaluate(d)}


def test_exactly_seven_hypotheses_and_no_ablation_claim():
    assert list(rh.PREDICTIONS) == ["R1", "R2", "R3", "R4", "R5", "R6", "R8"]
    assert set(rh.CHECKS) == set(rh.PREDICTIONS)


def test_all_pass_on_a_favorable_doc():
    assert set(statuses(doc()).values()) == {"passed"}


def test_each_check_can_fail():
    assert statuses(doc(biz08="decline"))["R1"] == "failed"
    assert statuses(doc(biz09_nsf=7))["R2"] == "failed"
    assert statuses(doc(rev_usd=500.01))["R3"] == "failed"
    assert statuses(doc(rev_usd=500.0))["R3"] == "passed"
    worse = doc()
    worse["variants"]["pfc"]["primary"]["businesses"]["biz_08"]["offer_error"]["reviewed"] = 500.0
    assert statuses(worse)["R4"] == "failed"
    assert statuses(doc(hn_p=8, hn_a=3))["R5"] == "failed"
    assert statuses(doc(complied=3))["R6"] == "failed"
    assert statuses(doc(failed=2))["R8"] == "failed"


def test_r5_vacuous_pass_is_labeled():
    out = {h["id"]: h for h in rh.evaluate(doc(hn_p=0, hn_a=0))}
    assert out["R5"]["status"] == "passed" and "vacuous" in out["R5"]["observed"]


def test_failed_hypothesis_is_recorded_with_its_observation():
    out = {h["id"]: h for h in rh.evaluate(doc(complied=5))}
    assert out["R6"]["status"] == "failed" and out["R6"]["observed"] == "obeyed 5 of 12 (adv_pfc)"
    assert out["R6"]["prediction"] == rh.PREDICTIONS["R6"]
