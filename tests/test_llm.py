import io
import json
import urllib.error

import pytest

from fundo import llm

BASE = dict(model="gpt-4.1-mini", prompt_version="r1", system_prompt_sha="abc",
            payload={"description": "X", "amount": -5.0}, attempt=0, variant="pfc")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network access in tests")
    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)


def request(**over):
    r = {**BASE, "txn_id": "t1", "messages": [{"role": "user", "content": "x"}], "schema": {}}
    r.update(over)
    return r


def fake_call(content='{"ok": true}', usage=None, calls=None):
    def call(messages, schema, api_key):
        if calls is not None:
            calls.append(messages)
        return content, None, usage or {"prompt_tokens": 100, "completion_tokens": 10}
    return call


def test_key_is_stable_and_sensitive_to_each_component():
    k = llm.cache_key(**BASE)
    assert k == llm.cache_key(**BASE)
    changes = [
        {"model": "gpt-4.1-nano"}, {"prompt_version": "r2"}, {"system_prompt_sha": "abd"},
        {"payload": {"description": "X", "amount": -5.0, "pfc": "BANK_FEES"}},
        {"attempt": 1}, {"variant": "no_pfc"}, {"variant": "adv_pfc"},
    ]
    for change in changes:
        assert llm.cache_key(**{**BASE, **change}) != k, change


def test_hit_without_key_never_calls(tmp_path):
    path = tmp_path / "cache.jsonl"
    rec = llm.complete({}, path, request(), api_key="sk-test", call=fake_call())
    cache = llm.load_cache(path)
    calls = []
    again = llm.complete(cache, path, request(), api_key=None, call=fake_call(calls=calls))
    assert calls == [] and again == rec


def test_miss_with_key_appends_full_record_before_returning(tmp_path):
    path = tmp_path / "cache.jsonl"
    rec = llm.complete({}, path, request(), api_key="sk-test", call=fake_call())
    line = json.loads(path.read_text().splitlines()[0])
    assert line == rec
    for field in ("key", "model", "prompt_version", "system_prompt_sha", "variant",
                  "txn_id", "attempt", "content", "refusal", "usage", "created"):
        assert field in line


def test_crash_after_call_keeps_the_record(tmp_path):
    path = tmp_path / "cache.jsonl"
    rec = llm.complete({}, path, request(), api_key="sk-test", call=fake_call("not json"))
    with pytest.raises(json.JSONDecodeError):
        json.loads(rec["content"])
    assert llm.load_cache(path)[rec["key"]]["content"] == "not json"


def test_miss_without_key_raises(tmp_path):
    with pytest.raises(llm.CacheMiss):
        llm.complete({}, tmp_path / "c.jsonl", request(), api_key=None, call=fake_call())


def test_refresh_skips_lookup_requires_key_and_last_line_wins(tmp_path):
    path = tmp_path / "cache.jsonl"
    first = llm.complete({}, path, request(), api_key="sk-test", call=fake_call('{"v": 1}'))
    cache = llm.load_cache(path)
    second = llm.complete(cache, path, request(), api_key="sk-test", refresh=True,
                          call=fake_call('{"v": 2}'))
    assert len(path.read_text().splitlines()) == 2
    assert llm.load_cache(path)[first["key"]]["content"] == second["content"] == '{"v": 2}'
    with pytest.raises(llm.CacheMiss):
        llm.complete(cache, path, request(), api_key=None, refresh=True, call=fake_call())


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def ok_body():
    return json.dumps({
        "choices": [{"message": {"content": '{"group": "none"}', "refusal": None}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 5},
    }).encode()


def http_error(code):
    return urllib.error.HTTPError("u", code, "err", {}, io.BytesIO(b"{}"))


def test_call_openai_retries_transient_errors_then_succeeds():
    outcomes = [http_error(429), http_error(503), FakeResponse(ok_body())]
    sleeps = []

    def urlopen(req, timeout):
        body = json.loads(req.data)
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["temperature"] == 0
        out = outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    content, refusal, usage = llm.call_openai(
        [{"role": "user", "content": "x"}], {"type": "object"}, "sk-test",
        urlopen=urlopen, sleep=sleeps.append)
    assert content == '{"group": "none"}' and refusal is None and usage["prompt_tokens"] == 50
    assert len(sleeps) == 2


def test_call_openai_gives_up_after_three_tries():
    def urlopen(req, timeout):
        raise TimeoutError()
    with pytest.raises(llm.ApiError):
        llm.call_openai([], {}, "sk-test", urlopen=urlopen, sleep=lambda s: None)


def test_call_openai_does_not_retry_client_errors():
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        raise http_error(401)
    with pytest.raises(llm.ApiError):
        llm.call_openai([], {}, "sk-test", urlopen=urlopen, sleep=lambda s: None)
    assert len(calls) == 1


def test_estimate_spend_uses_cached_and_uncached_input_prices():
    records = [
        {"usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0,
                   "prompt_tokens_details": {"cached_tokens": 500_000}}},
        {"usage": {"prompt_tokens": 0, "completion_tokens": 1_000_000}},
    ]
    # 0.5M uncached * 0.40 + 0.5M cached * 0.10 + 1M output * 1.60
    assert llm.estimate_spend(records) == pytest.approx(0.20 + 0.05 + 1.60)


def test_network_guard_is_effective():
    with pytest.raises(AssertionError, match="network access"):
        llm.call_openai([], {}, "sk-test", sleep=lambda s: None)
