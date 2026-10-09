"""Invariants of the committed review report (measured r2 baseline). Hypotheses are NOT asserted to pass."""

import json
from pathlib import Path

from fundo import reviewer_hypotheses

ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((ROOT / "data/review_report.json").read_text())
LABELS = json.loads((ROOT / "data/reviewed_labels.json").read_text())
STATUSES = {"confirmed", "corrected", "kept_low_confidence", "review_failed"}


def test_meta_records_the_evaluated_version():
    assert DOC["meta"]["prompt_version"] == "r2" and DOC["meta"]["model"] == "gpt-4.1-mini"


def test_status_counts_partition_the_reviewed_set():
    reviewed = [e for e in LABELS.values() if e["review_status"] != "not_reviewed"]
    counts = DOC["variants"]["pfc"]["status_counts"]
    assert set(counts) <= STATUSES and sum(counts.values()) == len(reviewed)


def test_every_business_has_truth_legacy_and_reviewed_outcomes():
    for variant in DOC["variants"].values():
        businesses = variant["primary"]["businesses"]
        assert len(businesses) == 10
        for b in businesses.values():
            assert set(b["offer"]) == set(b["decision"]) == {"truth", "legacy", "reviewed"}
            assert b["needs_human_review"] == (b["changed_share"] > 0.40)


def test_coverage_is_labeled_optimistic_and_audit_bound_is_positive():
    for variant in DOC["variants"].values():
        cov = variant["flag_coverage"]
        assert "optimistic" in cov["note"].lower()
        assert cov["audit"]["wilson95"]["high"] > 0


def test_hypotheses_are_recorded_verbatim_with_a_status():
    recorded = {h["id"]: h for h in DOC["hypotheses"]}
    assert list(recorded) == list(reviewer_hypotheses.PREDICTIONS)
    for hid, h in recorded.items():
        assert h["prediction"] == reviewer_hypotheses.PREDICTIONS[hid]
        assert h["status"] in ("passed", "failed") and h["observed"]


def test_r1_run_is_preserved_next_to_r2():
    r1 = json.loads((ROOT / "data/runs/r1_review_report.json").read_text())
    assert r1["meta"]["prompt_version"] == "r1"
    assert [h["id"] for h in r1["hypotheses"]] == [h["id"] for h in DOC["hypotheses"]]
