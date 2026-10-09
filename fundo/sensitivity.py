"""Part 2: how mislabel rates move features and offers, plus NSF observability and 61-day truncation.

No LLM. Starts from truth labels and reuses compute_features / compute_offer unchanged.
Two corruption models are kept separate: `confusion` (realistic mistakes, including
business/personal flips) and `uniform` (random group swaps, a pessimistic bound).
The offer formula is never changed; observability and history fields are informational.
"""

import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import date, timedelta

from fundo.features import compute_features
from fundo.generate import END_DATE
from fundo.offer import compute_offer
from fundo.schema import GROUPS

RATES = (0.02, 0.05, 0.10)
MODELS = ("confusion", "uniform")
REPS = 200
FLIP_BUSINESS = "flip_business"
MATERIALITY = 0.01  # same project-chosen threshold as the reviewer gate
FEATURES = ("revenue_share", "nsf_count", "overdraft_count", "high_risk_debit_share",
            "avg_monthly_revenue", "daily_funder_payments")

# Realistic confusions: outcome -> weight. Authored before running on real data; frozen in Phase 6.
CONFUSION = {
    "none": [("not_average_monthly_revenue", 3), (FLIP_BUSINESS, 3), ("internal_transfer", 1),
             ("nsf", 1), ("high_risk_other", 1)],
    "not_average_monthly_revenue": [("none", 3), (FLIP_BUSINESS, 1)],
    "nsf": [("none", 3), ("internal_transfer", 1)],
    "overdraft": [("none", 3), ("nsf", 1)],
    "internal_transfer": [("nsf", 2), ("none", 2), (FLIP_BUSINESS, 1)],
    "ucc": [("none", 1)],
    "active_advance": [("none", 3), ("internal_transfer", 1)],
    "auto_deposit": [("none", 2), ("not_average_monthly_revenue", 1)],
    "revenue_verification": [("none", 1)],
    "high_risk_gambling": [("none", 3), (FLIP_BUSINESS, 1)],
    "high_risk_bankruptcy": [("none", 1)],
    "high_risk_debt_settlement": [("none", 1)],
    "high_risk_garnishment": [("none", 1)],
    "high_risk_other": [("none", 1)],
}


def _rng(seed, *parts):
    digest = hashlib.sha256(":".join(map(str, (seed, *parts))).encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def corrupt(rows, labels, rate, model, rng):
    """Corrupt exactly round(rate*n) transactions, one corruption each. Returns (labels, n_group, n_flip)."""
    tids = sorted(r["transaction_id"] for r in rows)
    new = dict(labels)
    n_group = n_flip = 0
    for tid in rng.sample(tids, round(rate * len(tids))):
        old = labels[tid]
        if model == "uniform":
            outcome = rng.choice([g for g in GROUPS if g != old["group"]])
        else:
            outcomes, weights = zip(*CONFUSION[old["group"]])
            outcome = rng.choices(outcomes, weights)[0]
        if outcome == FLIP_BUSINESS:
            new[tid] = {**old, "business": not old["business"]}
            n_flip += 1
        else:
            new[tid] = {**old, "group": outcome}
            n_group += 1
    return new, n_group, n_flip


def percentile(values, p):
    """Nearest-rank percentile."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def _stats(values):
    return {"mean": round(sum(values) / len(values), 4),
            "p5": percentile(values, 5), "p95": percentile(values, 95)}


def summarize_offers(truth_offer, offers):
    deltas = [round(o - truth_offer, 2) for o in offers]
    n = len(deltas)
    material = MATERIALITY * truth_offer
    return {
        "offer": _stats(offers),
        "offer_delta": {
            "mean": round(sum(deltas) / n, 2), "min": min(deltas), "p5": percentile(deltas, 5),
            "p50": percentile(deltas, 50), "p95": percentile(deltas, 95), "max": max(deltas),
            "share_higher": round(sum(d > 0 for d in deltas) / n, 4),
            "share_lower": round(sum(d < 0 for d in deltas) / n, 4),
            "share_material": round(sum(abs(d) >= material and d != 0 for d in deltas) / n, 4),
        },
        "decision_flip_prob": round(sum((o > 0) != (truth_offer > 0) for o in offers) / n, 4),
    }


def _evaluate(rows, labels, business):
    features = compute_features(rows, labels, business)
    offer = compute_offer(features)
    return {"features": features, "offer": offer, "decision": "approve" if offer > 0 else "decline"}


def run(txns, truth, businesses, seed=42, reps=REPS):
    rows = defaultdict(list)
    for t in txns:
        rows[t["business_id"]].append(t)
    out = {"meta": {"seed": seed, "reps": reps, "rates": list(RATES), "models": list(MODELS),
                    "materiality": MATERIALITY, "offer_formula_changed": False},
           "truth": {}, "monte_carlo": {}, "observability": {}, "truncation": {}, "low_history": {}}

    for b in businesses:
        bid, biz_rows = b["business_id"], rows[b["business_id"]]
        base = _evaluate(biz_rows, truth, b)
        out["truth"][bid] = base
        grid = out["monte_carlo"][bid] = {}
        for model in MODELS:
            for rate in RATES:
                offers, samples = [], defaultdict(list)
                n_group = n_flip = 0
                for rep in range(reps):
                    labels, g, f = corrupt(biz_rows, truth, rate, model, _rng(seed, model, rate, rep, bid))
                    n_group, n_flip = n_group + g, n_flip + f
                    result = _evaluate(biz_rows, labels, b)
                    offers.append(result["offer"])
                    for name in FEATURES:
                        samples[name].append(result["features"][name])
                grid.setdefault(model, {})[str(rate)] = {
                    **summarize_offers(base["offer"], offers),
                    "features": {name: _stats(samples[name]) for name in FEATURES},
                    "corruptions": {"group_change": n_group, "business_flip": n_flip},
                }

        out["observability"][bid] = {
            "nsf_observable": b["bank_charges_nsf_fee"],
            "overdraft_count": base["features"]["overdraft_count"],
            "warning": None if b["bank_charges_nsf_fee"] else
            "Bank charges no NSF fees: zero NSF is unobserved, not clean. Use overdrafts as proxy; manual review.",
        }
        if b["history_days"] >= 90:
            cutoff = (END_DATE - timedelta(days=60)).isoformat()
            recent = [t for t in biz_rows if t["date"] >= cutoff]
            d61 = _evaluate(recent, truth, {**b, "history_days": 61})
            out["truncation"][bid] = {"d90": base, "d61": d61,
                                      "offer_delta": round(d61["offer"] - base["offer"], 2),
                                      "decision_flips": d61["decision"] != base["decision"]}
        else:
            nsf = base["features"]["nsf_count"]
            out["low_history"][bid] = {
                "history_days": b["history_days"],
                "nsf_x_90_over_history": round(nsf * 90 / b["history_days"], 2),
                "warning": f"Only {b['history_days']} days of history; NSF threshold and averages "
                           "were calibrated on 90 days. Informational only; offer formula unchanged.",
            }
    return out


def write(path, result):
    with open(path, "w") as f:
        f.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
