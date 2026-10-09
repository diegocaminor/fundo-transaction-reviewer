"""OpenAI Chat Completions over urllib, behind a committed append-only JSONL cache.

Every live response is written and fsynced before it is returned, so a crash
never loses a paid call. A cache miss without OPENAI_API_KEY raises CacheMiss;
there is no silent fallback.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

MODEL = "gpt-4.1-mini"
API_URL = "https://api.openai.com/v1/chat/completions"
# USD per 1M tokens: uncached input, cached input, output (OpenAI pricing page, 2026-10-09).
PRICES = {"gpt-4.1-mini": (0.40, 0.10, 1.60)}
TRIES = 3


class CacheMiss(Exception):
    pass


class ApiError(Exception):
    pass


def cache_key(model, prompt_version, system_prompt_sha, payload, attempt, variant):
    parts = {"model": model, "prompt_version": prompt_version,
             "system_prompt_sha": system_prompt_sha, "payload": payload,
             "attempt": attempt, "variant": variant}
    canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_cache(path):
    """{key: record}; if a key appears more than once, the last line wins."""
    cache = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    cache[record["key"]] = record
    return cache


def append_record(path, record):
    with open(path, "a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def complete(cache, path, request, api_key=None, refresh=False, call=None):
    """Return the cached record for `request`, calling the API only on a miss (or refresh)."""
    key = cache_key(request["model"], request["prompt_version"], request["system_prompt_sha"],
                    request["payload"], request["attempt"], request["variant"])
    if not refresh and key in cache:
        return cache[key]
    if not api_key:
        raise CacheMiss(key)
    content, refusal, usage = (call or call_openai)(request["messages"], request["schema"], api_key)
    record = {"key": key, "model": request["model"], "prompt_version": request["prompt_version"],
              "system_prompt_sha": request["system_prompt_sha"], "variant": request["variant"],
              "txn_id": request["txn_id"], "attempt": request["attempt"], "content": content,
              "refusal": refusal, "usage": usage,
              "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    append_record(path, record)
    cache[key] = record
    return record


def call_openai(messages, schema, api_key, urlopen=None, sleep=time.sleep):
    """One Chat Completions call with strict JSON schema output. Returns (content, refusal, usage)."""
    urlopen = urlopen or urllib.request.urlopen  # resolved per call so tests can block the network
    body = json.dumps({
        "model": MODEL, "messages": messages, "temperature": 0, "seed": 42,
        "max_completion_tokens": 200,
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "review", "strict": True, "schema": schema}},
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    for attempt in range(TRIES):
        try:
            with urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            message = data["choices"][0]["message"]
            return message.get("content"), message.get("refusal"), data.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise ApiError(f"HTTP {e.code}: {e.read()[:300]!r}") from e
            error = e
        except (urllib.error.URLError, TimeoutError) as e:
            error = e
        if attempt < TRIES - 1:
            sleep(2 ** attempt)
    raise ApiError(f"gave up after {TRIES} tries: {error!r}")


def estimate_spend(records, model=MODEL):
    uncached_price, cached_price, output_price = PRICES[model]
    total = 0.0
    for r in records:
        usage = r.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        total += (usage.get("prompt_tokens", 0) - cached) * uncached_price
        total += cached * cached_price + usage.get("completion_tokens", 0) * output_price
    return total / 1_000_000
