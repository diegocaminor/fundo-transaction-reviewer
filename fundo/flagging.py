"""Code-only rules that pick which transactions the LLM reviewer sees.

Inputs are transactions and legacy labels only; ground truth is never read here.
The rules were written with knowledge of the planted scenarios, so offline
coverage on this dataset is an optimistic upper bound. The random audit sample
is the independent estimate of misses. Rules are frozen (FLAG_RULES_VERSION).
"""

import hashlib
import re
from collections import Counter, defaultdict
from statistics import median

FLAG_RULES_VERSION = "f1"

INJECTION_RE = re.compile(r"\b(ignore|instructions?|label as|system)\b", re.IGNORECASE)

RISKY_DEBIT_PFC = {"LOAN_PAYMENTS", "BANK_FEES", "TRANSFER_OUT"}
# Short hints must match a whole token; longer ones may prefix a token (settle -> settlement).
EXACT_HINTS = {"pmt", "mca", "fee", "nsf", "od"}
PREFIX_HINTS = ("xfer", "loan", "funding", "settle", "garnish", "personal", "refund")


def _tokens(description):
    text = description.lower().replace(".", "")
    return re.sub(r"[^a-z0-9]+", " ", text).split()


def _has_hint(description):
    return any(
        tok in EXACT_HINTS or tok.startswith(PREFIX_HINTS) for tok in _tokens(description)
    )


def _mask(description):
    return " ".join(re.sub(r"\d", "#", description.lower()).split())


def flag(txns, legacy, use_pfc=True):
    """Return {transaction_id: [rule ids]} for flagged transactions only."""
    repeats = Counter((t["business_id"], _mask(t["description"]), t["amount"]) for t in txns)
    credits = defaultdict(list)
    for t in txns:
        if t["amount"] > 0:
            credits[t["business_id"]].append(t["amount"])
    medians = {biz: median(amounts) for biz, amounts in credits.items()}

    flagged = {}
    for t in txns:
        group = legacy[t["transaction_id"]]["group"]
        pfc = t["personal_finance_category"]
        credit = t["amount"] > 0
        rules = []
        if group != "none":
            rules.append("R1")
        if use_pfc and group == "none" and credit and pfc["primary"] != "INCOME":
            rules.append("R2")
        if use_pfc and group == "none" and not credit and (
            pfc["primary"] in RISKY_DEBIT_PFC or "GAMBLING" in pfc["detailed"]
        ):
            rules.append("R3")
        if group == "none" and not credit and repeats[
            (t["business_id"], _mask(t["description"]), t["amount"])
        ] >= 5:
            rules.append("R4")
        if _has_hint(t["description"]):
            rules.append("R5")
        if credit and t["amount"] > 3 * medians[t["business_id"]]:
            rules.append("R6")
        if INJECTION_RE.search(t["description"]):
            rules.append("R7")
        if rules:
            flagged[t["transaction_id"]] = rules
    return flagged


def audit_sample(txns, flagged, seed=42, rate=0.05):
    """Seeded random sample of unflagged transactions, per business (production-style monitoring)."""
    unflagged = defaultdict(list)
    for t in txns:
        if t["transaction_id"] not in flagged:
            unflagged[t["business_id"]].append(t["transaction_id"])
    sample = []
    for tids in unflagged.values():
        ranked = sorted(tids, key=lambda tid: hashlib.sha256(f"{seed}:audit:{tid}".encode()).hexdigest())
        sample.extend(ranked[: round(rate * len(tids))])
    return sorted(sample)
