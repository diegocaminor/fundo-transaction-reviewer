"""Tests for the hypothesis checks on synthetic results (the evaluator, not the dataset outcome)."""

from fundo import sensitivity_hypotheses as h

RATES = ("0.02", "0.05", "0.1")


def cell(flip=0.0, mean=0.0, p50=0.0):
    return {"decision_flip_prob": flip, "offer_delta": {"mean": mean, "p50": p50}}


def result(offers, cells, truncation=None):
    """offers: {bid: truth offer}; cells: {(bid, model, rate): cell}."""
    mc = {}
    for b in offers:
        mc[b] = {m: {r: cells.get((b, m, r), cell()) for r in RATES} for m in ("confusion", "uniform")}
    return {"truth": {b: {"offer": o} for b, o in offers.items()}, "monte_carlo": mc,
            "truncation": truncation or {}}


def test_s1_passes_and_fails():
    offers = {"a": 100, "b": 100, "c": 0}
    trend = {("a", "confusion", r): cell(mean=m, p50=-1) for r, m in zip(RATES, (-1, -2, -3))}
    trend.update({("b", "confusion", r): cell(mean=m) for r, m in zip(RATES, (-1, -2, -3))})
    trend[("b", "confusion", "0.1")] = cell(mean=-3, p50=-1)
    assert h.check_s1(result(offers, trend))[0]
    flat = {**trend, ("a", "confusion", "0.1"): cell(mean=-1, p50=-1)}  # mean no longer decreasing
    assert not h.check_s1(result(offers, flat))[0]
    minority = {**trend, ("b", "confusion", "0.1"): cell(mean=-3, p50=0)}  # only 1 of 2 negative
    assert not h.check_s1(result(offers, minority))[0]


def test_s2_requires_strictly_highest():
    offers = {"biz_09": 0, "x": 100}
    assert h.check_s2(result(offers, {("biz_09", "confusion", "0.02"): cell(flip=0.2),
                                      ("x", "confusion", "0.02"): cell(flip=0.1)}))[0]
    assert not h.check_s2(result(offers, {("biz_09", "confusion", "0.02"): cell(flip=0.1),
                                          ("x", "confusion", "0.02"): cell(flip=0.1)}))[0]


def test_s3_pooled_over_all_cells():
    offers = {"a": 100, "b": 0}
    cells = {("a", "uniform", "0.1"): cell(flip=0.6), ("b", "confusion", "0.02"): cell(flip=0.3)}
    assert h.check_s3(result(offers, cells))[0]
    cells[("b", "confusion", "0.05")] = cell(flip=0.4)
    assert not h.check_s3(result(offers, cells))[0]


def trunc(d90, d61):
    return {"d90": {"offer": d90}, "d61": {"offer": d61}}


def test_s4_threshold_and_flip_limit():
    ok = {"a": trunc(100, 99.5), "b": trunc(100, 120), "c": trunc(100, 0)}
    assert h.check_s4(result({}, {}, ok))[0]
    too_many_lower = {**ok, "d": trunc(100, 98), "e": trunc(100, 97)}
    assert not h.check_s4(result({}, {}, too_many_lower))[0]
    two_flips = {"a": trunc(100, 0), "b": trunc(100, 0), "c": trunc(100, 150), "d": trunc(100, 150),
                 "e": trunc(100, 150)}
    assert not h.check_s4(result({}, {}, two_flips))[0]
    declined_ignored = {"a": trunc(0, 0), "b": trunc(100, 150)}
    assert h.check_s4(result({}, {}, declined_ignored))[0]


def test_evaluate_keeps_prediction_text_verbatim():
    offers = {"biz_09": 0, "x": 100}
    out = h.evaluate(result(offers, {}, {"x": trunc(100, 100)}))
    assert [o["id"] for o in out] == ["S1", "S2", "S3", "S4"]
    assert all(o["prediction"] == h.PREDICTIONS[o["id"]] for o in out)
    assert all(o["status"] in ("passed", "failed") and o["observed"] for o in out)
