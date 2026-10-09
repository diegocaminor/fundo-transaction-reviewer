"""Pre-registered reviewer hypotheses and their literal checks.

SKELETON: predictions are written, reviewed by the user and committed in the
Phase 6 freeze, before the first real API call. Each check takes the review
report document and returns (passed, observed).
"""

PREDICTIONS = {}
CHECKS = {}


def evaluate(doc):
    out = []
    for hid, check in CHECKS.items():
        passed, observed = check(doc)
        out.append({"id": hid, "prediction": PREDICTIONS[hid],
                    "status": "passed" if passed else "failed", "observed": observed})
    return out
