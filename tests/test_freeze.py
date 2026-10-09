"""Frozen before the first real API call. Any edit fails here and requires an explicit version bump
(and, for the prompt or schema, a cache refill)."""

import hashlib
import json

from fundo.flagging import FLAG_RULES_VERSION
from fundo.reviewer import BAR_MATERIAL, BAR_OTHER, MATERIALITY, PROMPT_VERSION, SCHEMA, SYSTEM_PROMPT_SHA
from fundo.sensitivity import CONFUSION


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def test_versions_are_pinned():
    assert FLAG_RULES_VERSION == "f1" and PROMPT_VERSION == "r2"  # r2: payload fix, see proposal log


def test_prompt_schema_and_confusion_are_frozen():
    assert SYSTEM_PROMPT_SHA == "3a62c92082be4448333395069928d8b4ae4067e9a6bc2f9f70ff901e029dfb5e"
    assert sha(SCHEMA) == "2c6f6fad22084929cf3126b514f9d3e2c0fffe76022c26b5f7b12e7f4731f4f4"
    assert sha(CONFUSION) == "6d88f3638b62b86faedd1d1254920debb437062ba5e488113baf7ffcfbd5bc1c"


def test_policy_thresholds_are_frozen():
    assert (BAR_MATERIAL, BAR_OTHER, MATERIALITY) == (0.85, 0.70, 0.01)
