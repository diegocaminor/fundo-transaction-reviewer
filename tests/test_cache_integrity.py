"""Integrity of the committed LLM cache (offline; no key needed)."""

import json
from pathlib import Path

from fundo import llm, review_report
from fundo.reviewer import PROMPT_VERSION, SYSTEM_PROMPT_SHA

ROOT = Path(__file__).resolve().parent.parent
RECORDS = [json.loads(line) for line in (ROOT / "data/llm_cache.jsonl").read_text().splitlines() if line.strip()]


def test_total_spend_including_superseded_runs_is_under_budget():
    assert llm.estimate_spend(RECORDS) < 10.0


def test_every_record_uses_the_frozen_system_prompt_and_a_known_version():
    assert {r["system_prompt_sha"] for r in RECORDS} == {SYSTEM_PROMPT_SHA}
    assert {r["prompt_version"] for r in RECORDS} == {"r1", PROMPT_VERSION}
    assert {r["model"] for r in RECORDS} == {llm.MODEL}


def test_current_version_has_no_cache_misses():
    assert review_report.preflight(ROOT / "data") == {"pfc": 0, "no_pfc": 0, "adv_pfc": 0, "adv_no_pfc": 0}


def test_no_secrets_in_cache():
    raw = (ROOT / "data/llm_cache.jsonl").read_text()
    assert "Bearer" not in raw and "OPENAI_API_KEY" not in raw and "sk-" not in raw
