"""Pre-registered sensitivity hypotheses (Part 2) and their literal checks.

PREDICTIONS is the user-reviewed text, committed before sensitivity ran on the
real data and never edited afterwards. Each check implements the operational
definition written next to it. "Approved" means approved under ground truth.
"""

MATERIALITY = 0.01

PREDICTIONS = {
    "S1": "Under the confusion model, the median offer change is negative for a majority of "
          "businesses that are approved under ground truth, and the negative effect becomes "
          "more pronounced as the corruption rate increases.",
    "S2": "At 2% confusion, biz_09 has the highest decision-flip probability because it sits "
          "exactly one NSF correction away from crossing the > 5 decline threshold.",
    "S3": "Uniform corruption produces a higher decision-flip rate than realistic confusion "
          "overall, especially for approved businesses, because arbitrary group swaps can "
          "create implausibly large active_advance effects.",
    "S4": "Truncating 90-day histories to 61 days does not systematically reduce offers or cause "
          "widespread approve→decline flips, because monthly revenue is normalized by observed "
          "history length. Any remaining changes should come from reduced observation coverage "
          "rather than the shorter window mechanically lowering revenue.",
}

# Operational definitions (fixed before running):
# S1: (a) at the 10% rate, more than half of approved businesses have p50 offer delta < 0;
#     (b) the mean offer delta averaged over approved businesses strictly decreases 2% > 5% > 10%.
# S2: biz_09's decision-flip probability at 2% confusion is strictly greater than every other business's.
# S3: the decision-flip probability averaged over all business x rate cells is higher for uniform.
#     ("especially for approved businesses" is reported as an observation, not tested.)
# S4: among approved 90-day businesses, (a) fewer than half have a 61-day offer lower by >= 1% of
#     their 90-day offer, and (b) at most one flips approve -> decline.
#     (The causal sentence is rationale, not tested.) The < 50% and <= 1 flip limits are pre-run
#     operational thresholds chosen to make "not systematic" and "not widespread" testable; they
#     are not requirements of the challenge.
# S1(a) is evaluated only at 10% because at 2% most corruptions hit debits and the median is often 0;
# S1(b) uses the mean because the trend is about effect size, which medians stuck at 0 cannot show.
RATES = ("0.02", "0.05", "0.1")


def _approved(result):
    return sorted(b for b, t in result["truth"].items() if t["offer"] > 0)


def _cell(result, bid, model, rate):
    return result["monte_carlo"][bid][model][rate]


def check_s1(result):
    approved = _approved(result)
    negative = [b for b in approved if _cell(result, b, "confusion", "0.1")["offer_delta"]["p50"] < 0]
    means = [round(sum(_cell(result, b, "confusion", r)["offer_delta"]["mean"] for b in approved)
                   / len(approved), 2) for r in RATES]
    passed = len(negative) > len(approved) / 2 and means[0] > means[1] > means[2]
    return passed, (f"p50 < 0 at 10% for {len(negative)}/{len(approved)} approved; "
                    f"mean offer delta 2%/5%/10%: {means[0]} / {means[1]} / {means[2]}")


def check_s2(result):
    probs = {b: _cell(result, b, "confusion", "0.02")["decision_flip_prob"] for b in result["monte_carlo"]}
    others = max(p for b, p in probs.items() if b != "biz_09")
    return probs["biz_09"] > others, f"biz_09 {probs['biz_09']} vs highest other {others}"


def check_s3(result):
    def pooled(model, businesses):
        cells = [_cell(result, b, model, r)["decision_flip_prob"] for b in businesses for r in RATES]
        return round(sum(cells) / len(cells), 4)
    everyone, approved = sorted(result["monte_carlo"]), _approved(result)
    u, c = pooled("uniform", everyone), pooled("confusion", everyone)
    ua, ca = pooled("uniform", approved), pooled("confusion", approved)
    return u > c, f"all: uniform {u} vs confusion {c}; approved only: uniform {ua} vs confusion {ca}"


def check_s4(result):
    rows = {b: t for b, t in result["truncation"].items() if t["d90"]["offer"] > 0}
    lower = [b for b, t in rows.items() if t["d90"]["offer"] - t["d61"]["offer"] >= MATERIALITY * t["d90"]["offer"]]
    flips = [b for b, t in rows.items() if t["d61"]["offer"] == 0]
    passed = len(lower) < len(rows) / 2 and len(flips) <= 1
    return passed, (f"offer lower by >=1% for {len(lower)}/{len(rows)} approved 90-day businesses "
                    f"{sorted(lower)}; approve->decline flips: {sorted(flips)}")


CHECKS = {"S1": check_s1, "S2": check_s2, "S3": check_s3, "S4": check_s4}


def evaluate(result):
    out = []
    for hid, check in CHECKS.items():
        passed, observed = check(result)
        out.append({"id": hid, "prediction": PREDICTIONS[hid],
                     "status": "passed" if passed else "failed", "observed": observed})
    return out
