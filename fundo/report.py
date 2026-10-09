"""Legacy-vs-truth baseline report. Delta = legacy - truth.

Besides the overall comparison, each business gets two counterfactuals that
attribute the credit impact: `collateral_only` applies legacy labels solely to
non-trap transactions, `planned_only` solely to trap transactions.
"""

import json
from pathlib import Path

from .features import compute_features
from .hypotheses import evaluate
from .offer import compute_offer
from .schema import is_revenue


def _decision(offer):
    return "approve" if offer > 0 else "decline"


def _scenario(txns, labels, biz):
    features = compute_features(txns, labels, biz)
    offer = compute_offer(features)
    return features, offer


def _delta(legacy, truth):
    return {k: round(legacy[k] - truth[k], 4) for k in truth}


def _accuracy(txns, truth, legacy):
    n = len(txns) or 1
    hit = {"group": 0, "business": 0, "revenue": 0}
    for t in txns:
        a, b = truth[t["transaction_id"]], legacy[t["transaction_id"]]
        hit["group"] += a["group"] == b["group"]
        hit["business"] += a["business"] == b["business"]
        hit["revenue"] += (
            is_revenue(t, a["group"], a["business"]) == is_revenue(t, b["group"], b["business"])
        )
    return {k: round(v / n, 4) for k, v in hit.items()}


def _mislabels(txns, truth, legacy, traps):
    planned_by_trap, unplanned_by_pattern = {}, {}
    planned = unplanned = 0
    for t in txns:
        tid = t["transaction_id"]
        a, b = truth[tid], legacy[tid]
        if a["group"] == b["group"] and a["business"] == b["business"]:
            continue
        if tid in traps:
            planned += 1
            planned_by_trap[traps[tid]] = planned_by_trap.get(traps[tid], 0) + 1
        else:
            unplanned += 1
            key = f"{a['group']}->{b['group']}"
            unplanned_by_pattern[key] = unplanned_by_pattern.get(key, 0) + 1
    return {
        "planned": planned,
        "unplanned": unplanned,
        "planned_by_trap": dict(sorted(planned_by_trap.items())),
        "unplanned_by_pattern": dict(sorted(unplanned_by_pattern.items())),
    }


def _partial(txns, truth, legacy, traps, biz, use_legacy_on_traps):
    mixed = {
        t["transaction_id"]: (
            legacy if (t["transaction_id"] in traps) == use_legacy_on_traps else truth
        )[t["transaction_id"]]
        for t in txns
    }
    features, offer = _scenario(txns, mixed, biz)
    return {"features": features, "offer": offer, "decision": _decision(offer)}


def build_report(businesses, txns, truth, legacy_labels, traps):
    by_biz = {}
    for t in txns:
        by_biz.setdefault(t["business_id"], []).append(t)
    report = {}
    for biz in sorted(businesses, key=lambda b: b["business_id"]):
        bid = biz["business_id"]
        rows = by_biz.get(bid, [])
        tf, to = _scenario(rows, truth, biz)
        lf, lo = _scenario(rows, legacy_labels, biz)
        truth_dec, legacy_dec = _decision(to), _decision(lo)
        collateral = _partial(rows, truth, legacy_labels, traps, biz, False)
        planned = _partial(rows, truth, legacy_labels, traps, biz, True)
        report[bid] = {
            "n_txns": len(rows),
            "accuracy": _accuracy(rows, truth, legacy_labels),
            "features": {"truth": tf, "legacy": lf, "delta": _delta(lf, tf)},
            "offer": {"truth": to, "legacy": lo, "delta": round(lo - to, 2)},
            "mislabels": _mislabels(rows, truth, legacy_labels, traps),
            "decision": {"truth": truth_dec, "legacy": legacy_dec, "flipped": truth_dec != legacy_dec},
            "collateral_only": collateral,
            "collateral_flips_decision": collateral["decision"] != truth_dec,
            "planned_only": planned,
            # legacy outcome differs from the one reached with legacy errors on traps only
            "collateral_changes_outcome": legacy_dec != planned["decision"],
        }
    return report


def format_table(report):
    head = (f"{'business':<9}{'truth':>11}{'legacy':>11}{'delta':>11}  {'truth/legacy':<16}"
            f"{'planned':>8}{'unplanned':>10}  {'collateral flips':<17}changes outcome")
    lines = [head]
    for bid, r in report.items():
        d = r["decision"]
        lines.append(
            f"{bid:<9}{r['offer']['truth']:>11.2f}{r['offer']['legacy']:>11.2f}"
            f"{r['offer']['delta']:>11.2f}  {d['truth'] + '/' + d['legacy']:<16}"
            f"{r['mislabels']['planned']:>8}{r['mislabels']['unplanned']:>10}  "
            f"{'FLIPS DECISION' if r['collateral_flips_decision'] else '-':<17}"
            f"{'CHANGES OUTCOME' if r['collateral_changes_outcome'] else '-'}"
        )
    return "\n".join(lines)


def format_scoreboard(hypotheses):
    lines = ["", "Hypotheses scoreboard (original predictions, unchanged)"]
    for h in hypotheses:
        lines.append(f"{h['business_id']:<8}{h['status'].upper():<8}{h['observed']}")
    passed = sum(h["status"] == "passed" for h in hypotheses)
    lines.append(f"{passed}/{len(hypotheses)} passed")
    return "\n".join(lines)


def _dump(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def write_report(out_dir="data"):
    """Classify with the legacy engine and write legacy_labels + baseline_report."""
    from .legacy import classify_all

    out = Path(out_dir)
    load = lambda name: json.loads((out / name).read_text())
    businesses, txns = load("businesses.json"), load("transactions.json")
    truth, traps = load("ground_truth.json"), load("traps.json")
    legacy = classify_all(txns)
    _dump(out / "legacy_labels.json", legacy)
    businesses_report = build_report(businesses, txns, truth, legacy, traps)
    doc = {"businesses": businesses_report, "hypotheses": evaluate(businesses_report)}
    _dump(out / "baseline_report.json", doc)
    return doc
