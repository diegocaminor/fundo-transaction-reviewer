"""Review transactions we did not generate (for example, a file brought to the debrief).

Input is a JSON list of transactions or a Plaid-style {"transactions": [...]} object. There is
no ground truth and no businesses file: history length is inferred from the dates, and the
output compares legacy and reviewed labels only.

The amount sign is declared, never guessed: `credit-positive` (this project and the Fundo PDF)
or `plaid` (native Plaid, where positive means money out). A wrong sign silently inverts every
credit, so a warning fires when INCOME-category transactions look inverted.
"""

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from fundo import llm
from fundo.features import compute_features
from fundo.flagging import audit_sample, flag
from fundo.legacy import classify_all
from fundo.offer import compute_offer
from fundo.reviewer import review
from fundo.schema import validate_transaction

SIGNS = ("credit-positive", "plaid")
VARIANT = "external"


def normalize(rows, sign="credit-positive"):
    """Map Plaid-like rows onto this project's transaction schema."""
    if sign not in SIGNS:
        raise ValueError(f"sign must be one of {SIGNS}, got {sign!r}")
    out = []
    for r in rows:
        description = r.get("description") or r.get("name") or r.get("original_description")
        missing = [name for name, value in (("transaction_id", r.get("transaction_id")), ("date", r.get("date")),
                                            ("amount", r.get("amount")), ("description or name", description))
                   if value is None]
        if missing:
            raise ValueError(f"transaction {r.get('transaction_id', '?')}: missing {', '.join(missing)}")
        pfc = r.get("personal_finance_category") or {}
        t = {
            "transaction_id": str(r["transaction_id"]),
            "business_id": r.get("business_id") or r.get("account_id") or "unknown",
            "account_id": r.get("account_id") or "unknown",
            "date": str(r["date"])[:10],
            "description": description,
            "amount": round(float(r["amount"]) * (-1 if sign == "plaid" else 1), 2),
            "iso_currency_code": r.get("iso_currency_code") or "USD",
            "payment_channel": r.get("payment_channel") or "other",
            "merchant_name": r.get("merchant_name"),
            "personal_finance_category": {"primary": pfc.get("primary") or "UNKNOWN",
                                          "detailed": pfc.get("detailed") or "UNKNOWN"},
        }
        validate_transaction(t)
        out.append(t)
    return out


def sign_warnings(txns):
    income = [t for t in txns if t["personal_finance_category"]["primary"] == "INCOME"]
    negative = sum(t["amount"] < 0 for t in income)
    if len(income) >= 3 and negative > len(income) / 2:
        return [f"{negative} of {len(income)} INCOME transactions are negative: the amount sign is probably "
                "inverted (try --sign plaid)."]
    return []


def has_pfc(txns):
    return all(t["personal_finance_category"]["primary"] != "UNKNOWN" for t in txns)


def infer_businesses(txns):
    dates = defaultdict(list)
    for t in txns:
        dates[t["business_id"]].append(date.fromisoformat(t["date"]))
    return [{"business_id": b, "type": "unknown", "history_days": (max(d) - min(d)).days + 1,
             "bank_charges_nsf_fee": None} for b, d in sorted(dates.items())]


def load_transactions(path, sign="credit-positive"):
    doc = json.loads(Path(path).read_text())
    txns = normalize(doc["transactions"] if isinstance(doc, dict) else doc, sign)
    return txns, sign_warnings(txns)


def _review(txns, businesses, complete):
    legacy = classify_all(txns)
    use_pfc = has_pfc(txns)  # filling a missing category would make the PFC rules flag every credit
    flagged = flag(txns, legacy, use_pfc)
    audit = audit_sample(txns, flagged)
    ids = {**flagged, **{t: ["AUDIT"] for t in audit}}
    return legacy, use_pfc, flagged, audit, review(txns, legacy, businesses, ids, VARIANT, use_pfc, complete)


def misses(path, cache_path, sign="credit-positive"):
    """Attempt-0 cache misses for this file, without calling the API."""
    txns, _ = load_transactions(path, sign)
    cache = llm.load_cache(cache_path)
    count = 0

    def dry(r):
        nonlocal count
        key = llm.cache_key(r["model"], r["prompt_version"], r["system_prompt_sha"], r["payload"],
                            r["attempt"], r["variant"])
        if key in cache:
            return cache[key]
        count += r["attempt"] == 0
        return {"content": None, "refusal": "preflight"}

    _review(txns, infer_businesses(txns), dry)
    return count


def run(path, out_dir, cache_path, api_key=None, refresh=False, call=None, sign="credit-positive"):
    txns, warnings = load_transactions(path, sign)
    businesses = infer_businesses(txns)
    cache = llm.load_cache(cache_path)
    legacy, use_pfc, flagged, audit, reviewed = _review(
        txns, businesses, lambda r: llm.complete(cache, cache_path, r, api_key, refresh, call))

    rows = defaultdict(list)
    for t in txns:
        rows[t["business_id"]].append(t)
    per_business = {}
    for b in businesses:
        out = {}
        for name, labels in (("legacy", legacy), ("reviewed", reviewed)):
            f = compute_features(rows[b["business_id"]], labels, b)
            out[name] = (f, compute_offer(f))
        per_business[b["business_id"]] = {
            "history_days": b["history_days"],
            "features": {k: v[0] for k, v in out.items()},
            "offer": {k: v[1] for k, v in out.items()},
            "decision": {k: "approve" if v[1] > 0 else "decline" for k, v in out.items()},
        }
    by_id = {t["transaction_id"]: t for t in txns}
    changes = [{"transaction_id": tid, "description": by_id[tid]["description"], "amount": by_id[tid]["amount"],
                "legacy": {"group": legacy[tid]["group"], "business": legacy[tid]["business"]},
                "proposed": e["proposed"], "status": e["review_status"], "confidence": e["confidence"],
                "reason": e["notes"], "rule_ids": e["rule_ids"], "injection_suspected": e["injection_suspected"]}
               for tid, e in sorted(reviewed.items()) if e["review_status"] in ("corrected", "kept_low_confidence")]
    statuses = Counter(e["review_status"] for e in reviewed.values() if e["review_status"] != "not_reviewed")
    doc = {"summary": {"transactions": len(txns), "flagged": len(flagged), "audit": len(audit),
                       "reviewed": sum(statuses.values()), "status_counts": dict(sorted(statuses.items())),
                       "sign": sign, "pfc_rules_enabled": use_pfc, "warnings": warnings},
           "businesses": per_business, "changes": changes}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, obj in (("external_review.json", doc), ("reviewed_labels.json", reviewed)):
        (out / name).write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")
    return doc
