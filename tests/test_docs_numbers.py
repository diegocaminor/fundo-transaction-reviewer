"""Every quantitative claim in SOLUTION.md is recomputed from committed artifacts and must appear verbatim."""

import json
import re
from collections import Counter
from pathlib import Path

from fundo import generate
from fundo.legacy import RULES
from fundo.schema import is_revenue

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "SOLUTION.md").read_text()
load = lambda p: json.loads((ROOT / p).read_text())
BASE, R2, R1, SENS = (load("data/baseline_report.json"), load("data/review_report.json"),
                      load("data/runs/r1_review_report.json"), load("data/sensitivity.json"))
TXNS, TRUTH, LEGACY = load("data/transactions.json"), load("data/ground_truth.json"), load("data/legacy_labels.json")


def money(x):
    return f"${round(x):,}"


def claim(text):
    assert text in DOC, f"SOLUTION.md is missing the measured claim: {text!r}"


def pfc(doc):
    return doc["variants"]["pfc"]


def test_data_and_legacy_baseline():
    claim(f"{len(BASE['businesses'])} Plaid-format businesses ({len(TXNS):,} transactions")
    claim(f"{len({g for _, g in RULES})} ordered substring rules")
    wrong = sum((LEGACY[t]["group"], LEGACY[t]["business"]) != (TRUTH[t]["group"], TRUTH[t]["business"]) for t in TRUTH)
    claim(f"{wrong} of {len(TXNS):,} transactions ({wrong / len(TXNS):.1%})")
    passed = sum(h["status"] == "passed" for h in BASE["hypotheses"])
    claim(f"Legacy baseline ({passed} of {len(BASE['hypotheses'])} predictions passed)")
    b = BASE["businesses"]
    claim(f"biz_04 +{money(b['biz_04']['offer']['delta'])}, +{b['biz_04']['offer']['delta'] / b['biz_04']['offer']['truth']:.0%}")
    claim(f"truth {money(b['biz_08']['offer']['truth'])}, legacy {money(b['biz_08']['offer']['legacy'])}")
    claim(f"would approve {money(b['biz_09']['planned_only']['offer'])} on a decline")


def test_flagging_and_audit():
    p, cov = pfc(R2), pfc(R2)["flag_coverage"]
    n_flag, n_audit = p["secondary"]["accuracy"]["flagged"]["n"], cov["audit"]["n"]
    claim(f"flag {n_flag} suspicious transactions ({n_flag / len(TXNS):.0%}) and a seeded 5% random audit adds {n_audit}")
    claim(f"0 errors in {n_audit} sampled transactions, Wilson 95% upper bound {cov['audit']['wilson95']['high']:.1%}")
    claim(f"up to ~{cov['audit']['estimated_unflagged_misses']['high']} misses among the {len(TXNS) - n_flag:,} unflagged")
    assert cov["legacy_error_recall"] == 1.0 and cov["audit"]["legacy_errors"] == 0


def test_reviewer_r1_vs_r2():
    h1, h2 = ({h["id"]: h["status"].upper() for h in d["hypotheses"]} for d in (R1, R2))
    for hid in h2:
        row = next(line for line in DOC.splitlines() if line.startswith(f"| {hid} "))
        assert f"| {h1[hid]} | {h2[hid]} |" in row, hid
    p1, p2 = pfc(R1)["primary"], pfc(R2)["primary"]
    rev = p2["dollar_error"]["revenue_usd"]
    claim(f"{money(rev['legacy'])} → {money(rev['reviewed'])} (−{1 - rev['reviewed'] / rev['legacy']:.0%})")
    off = lambda p, k: sum(b["offer_error"][k] for b in p["businesses"].values())
    claim(f"{money(off(p2, 'legacy'))} → {money(off(p2, 'reviewed'))}")
    hn = p2["hard_negatives"]
    claim(f"{hn['accepted']['count']} of {hn['proposed']['count']} accepted")
    correct = lambda p, k: sum(b["decision"][k] == b["decision"]["truth"] for b in p["businesses"].values())
    claim(f"| {correct(p2, 'legacy')}/10 | {correct(p1, 'reviewed')}/10 | **{correct(p2, 'reviewed')}/10** |")
    hr = lambda p, k: p["dollar_error"]["high_risk_usd"][k]
    claim(f"| {money(hr(p2, 'legacy'))} | {money(hr(p1, 'reviewed'))} | **{money(hr(p2, 'reviewed'))}** |")
    acc = lambda d, k: pfc(d)["secondary"]["accuracy"]["flagged"][k]["group"]
    claim(f"| {acc(R2, 'legacy'):.2f} | {acc(R1, 'reviewed'):.2f} | {acc(R2, 'reviewed'):.2f} |")
    claim(f"| {R2['adversarial']['adv_pfc']['complied']} of 12 |")
    claim(f"({R2['adversarial']['adv_no_pfc']['complied']} of 12 without the Plaid category)")
    claim(f"${R2['spend_usd']:.2f} for both runs")
    claim(f"declined {sum(b['decision']['reviewed'] == 'decline' and b['decision']['truth'] == 'approve' for b in p1['businesses'].values())} of 10 healthy businesses")


def test_r1_root_cause_evidence():
    r1 = load("data/runs/r1_reviewed_labels.json")
    biz = {t["transaction_id"]: t["business_id"] for t in TXNS}
    wrong = [t for t, e in r1.items() if (e.get("proposed") or {}).get("group") == "nsf" and TRUTH[t]["group"] != "nsf"]
    by_biz = Counter(biz[t] for t in wrong)
    cite = sum(any(w in r1[t]["notes"].lower() for w in ("bank charge", "nsf fee", "charges nsf")) for t in wrong)
    assert by_biz["biz_02"] == 0
    claim(f"got 0 wrong NSF proposals, while the other nine got {len(wrong)}, and {cite} of those reasons")


def test_confidence_and_funder_findings():
    labels = load("data/reviewed_labels.json")
    conf = [e["confidence"] for e in labels.values() if e.get("confidence") is not None]
    kept = sum(e["review_status"] == "kept_low_confidence" for e in labels.values())
    claim(f"{sum(c >= 0.9 for c in conf)} of {len(conf)} answers report ≥ 0.9, so the gate kept only {kept}")
    lease = next(t for t in TXNS if "PENSKE" in t["description"] and labels[t["transaction_id"]]["group"] == "active_advance")
    f = pfc(R2)["primary"]["businesses"]["biz_03"]["features"]["reviewed"]
    assert f["daily_funder_payments"] == -lease["amount"]
    claim(f"one {money(-lease['amount'])} lease payment removed {money(20 * f['daily_funder_payments'])} from biz_03")
    ab = R2["ablation"]
    assert ab["pfc"]["group_accuracy"] == ab["no_pfc"]["group_accuracy"]
    claim(f"accuracy on the {ab['intersection_n']} shared transactions was {ab['pfc']['group_accuracy']:.3f}")
    claim(f"derived from truth with {generate.NOISE_RATE:.0%} noise")


def test_sensitivity_and_part2_answers():
    passed = sum(h["status"] == "passed" for h in SENS["hypotheses"])
    claim(f"Sensitivity ({passed} of {len(SENS['hypotheses'])} predictions passed)")
    s1 = next(h for h in SENS["hypotheses"] if h["id"] == "S1")["observed"]
    for v in re.findall(r"-(\d+\.\d+)", s1.split("mean offer delta")[1]):
        claim(money(float(v)))
    claim(f"({SENS['monte_carlo']['biz_09']['confusion']['0.02']['decision_flip_prob']:.0%} of runs)")
    s3 = next(h for h in SENS["hypotheses"] if h["id"] == "S3")["observed"]
    u, c = (float(x) for x in re.findall(r"uniform ([\d.]+) vs confusion ([\d.]+)", s3)[0])
    claim(f"({u:.1%} vs {c:.1%} of runs)")
    tr = SENS["truncation"]
    approved = [b for b, t in tr.items() if t["d90"]["offer"] > 0]
    lower = [b for b in approved if tr[b]["d90"]["offer"] - tr[b]["d61"]["offer"] >= 0.01 * tr[b]["d90"]["offer"]]
    claim(f"lowered {len(lower)} of {len(approved)} approved offers by ≥ 1%")
    claim(f"**biz_09 flips from decline to approve** ({money(tr['biz_09']['d61']['offer'])})")
    claim(f"0 NSF lines but {SENS['observability']['biz_02']['overdraft_count']} items paid into overdraft")
    rev = lambda days: sum(t["amount"] for t in TXNS if t["business_id"] == "biz_10" and t["date"] >= days
                           and is_revenue(t, TRUTH[t["transaction_id"]]["group"], TRUTH[t["transaction_id"]]["business"]))
    drop = 1 - (rev("2026-05-01") / (61 / 30)) / (rev("0000") / 3)
    claim(f"biz_10 lost {drop:.0%} of monthly revenue")


def test_credit_error_table_follows_the_formula():
    from fundo.features import compute_features
    from fundo.offer import compute_offer

    biz = {"business_id": "b", "history_days": 90}
    t = lambda tid, amount, date="2026-06-01": {"transaction_id": tid, "business_id": "b",
                                                "date": date, "amount": amount}
    lab = lambda g: {"group": g, "business": True}
    offer = lambda rows, labels: compute_offer(compute_features(rows, labels, biz))
    base, L = [t("rev", 30000.0)], {"rev": lab("none")}

    rows = base + [t("c", 1000.0)]
    per_dollar = (offer(rows, {**L, "c": lab("none")}) -
                  offer(rows, {**L, "c": lab("not_average_monthly_revenue")})) / 1000
    claim(f"| $1 credit wrongly counted as revenue | **+${per_dollar:.2f}** |")

    rows = base + [t("d", -100.0)]
    per_dollar = (offer(rows, {**L, "d": lab("active_advance")}) - offer(rows, {**L, "d": lab("none")})) / 100
    claim(f"no other funder | **−${-per_dollar:.0f}** |")

    real = [t(f"f{i}", -310.0, f"2026-0{4 + i // 30}-{1 + i % 28:02d}") for i in range(60)]
    rows = base + real + [t("d", -100.0, "2026-06-30")]
    Lf = {**L, **{r["transaction_id"]: lab("active_advance") for r in real}}
    assert offer(rows, {**Lf, "d": lab("active_advance")}) > offer(rows, {**Lf, "d": lab("none")})
    claim("lowers the average and *raises* the offer")
