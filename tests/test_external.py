"""Reviewing transactions we did not generate: no ground truth, no businesses file."""

import json
import shutil
from pathlib import Path

import pytest

from fundo import cli, external

ROOT = Path(__file__).resolve().parent.parent


def raw(tid, amount, name="ACME SALES", date="2026-06-01", account="acc_x", pfc="INCOME", **extra):
    t = {"transaction_id": tid, "account_id": account, "date": date, "name": name, "amount": amount}
    if pfc:
        t["personal_finance_category"] = {"primary": pfc, "detailed": f"{pfc}_OTHER"}
    t.update(extra)
    return t


# --- loading and normalization -------------------------------------------------------------------

def test_accepts_a_list_or_a_plaid_style_wrapper(tmp_path):
    for doc in ([raw("t1", 10.0)], {"transactions": [raw("t1", 10.0)]}):
        path = tmp_path / "in.json"
        path.write_text(json.dumps(doc))
        txns, _ = external.load_transactions(path)
        assert [t["transaction_id"] for t in txns] == ["t1"]


def test_maps_plaid_fields_and_fills_optional_ones():
    t, = external.normalize([raw("t1", 10.0)])
    assert t["description"] == "ACME SALES" and t["business_id"] == "acc_x"
    assert t["iso_currency_code"] == "USD" and t["payment_channel"] == "other"
    explicit, = external.normalize([raw("t2", 5.0, description="REAL DESC", business_id="biz_9")])
    assert explicit["description"] == "REAL DESC" and explicit["business_id"] == "biz_9"


def test_missing_required_field_is_a_clear_error():
    bad = raw("t1", 10.0)
    del bad["date"]
    with pytest.raises(ValueError, match="t1.*date"):
        external.normalize([bad])


def test_plaid_sign_is_flipped_and_credit_positive_is_kept():
    plaid, = external.normalize([raw("t1", 25.0)], sign="plaid")  # Plaid: positive = money out
    ours, = external.normalize([raw("t1", 25.0)], sign="credit-positive")
    assert plaid["amount"] == -25.0 and ours["amount"] == 25.0
    with pytest.raises(ValueError):
        external.normalize([raw("t1", 25.0)], sign="guess")


def test_warns_when_income_looks_sign_inverted():
    income_negative = [raw(f"t{i}", -100.0) for i in range(4)] + [raw("t9", 50.0)]
    assert external.sign_warnings(external.normalize(income_negative))
    assert not external.sign_warnings(external.normalize([raw("t1", 100.0), raw("t2", -20.0, pfc="FOOD")]))


def test_infers_one_business_per_id_with_history_from_dates():
    txns = external.normalize([raw("a", 10.0, date="2026-04-02"), raw("b", 10.0, date="2026-06-30"),
                               raw("c", 10.0, account="acc_y", date="2026-06-01")])
    businesses = {b["business_id"]: b for b in external.infer_businesses(txns)}
    assert businesses["acc_x"]["history_days"] == 90 and businesses["acc_y"]["history_days"] == 1
    assert businesses["acc_x"]["type"] == "unknown"


def test_pfc_rules_are_disabled_when_the_category_is_missing():
    assert external.has_pfc(external.normalize([raw("t1", 10.0)]))
    assert not external.has_pfc(external.normalize([raw("t1", 10.0), raw("t2", 5.0, pfc=None)]))


# --- end to end (fake model; no network) ---------------------------------------------------------

def fake_call(messages, schema, api_key):
    legacy = json.loads(messages[1]["content"])["legacy"]
    return json.dumps({"group": legacy["group"], "business": legacy["business"], "confidence": 0.9,
                       "reason": "fake"}), None, {"prompt_tokens": 10, "completion_tokens": 2}


def their_file(tmp_path):
    rows = [raw("s1", 900.0, "SQUARE DEPOSIT", "2026-04-01"), raw("s2", 1100.0, "SQUARE DEPOSIT", "2026-06-29"),
            raw("x1", -500.0, "ONLINE TRANSFER TO SAVINGS", "2026-05-01", pfc="TRANSFER_OUT"),
            raw("n1", -35.0, "NSF RETURN ITEM FEE", "2026-05-02", pfc="BANK_FEES")]
    path = tmp_path / "theirs.json"
    path.write_text(json.dumps({"transactions": rows}))
    return path


def test_review_file_runs_without_truth_and_reproduces_from_cache(tmp_path):
    out, cache = tmp_path / "out", tmp_path / "cache.jsonl"
    external.run(their_file(tmp_path), out, cache, api_key="sk-test", call=fake_call)
    first = (out / "external_review.json").read_bytes()
    doc = json.loads(first)
    biz = doc["businesses"]["acc_x"]
    assert set(biz["offer"]) == {"legacy", "reviewed"} and biz["history_days"] == 90
    assert doc["summary"]["transactions"] == 4 and doc["summary"]["reviewed"] >= 2
    assert "ground_truth" not in first.decode()
    assert external.misses(their_file(tmp_path), cache) == 0
    external.run(their_file(tmp_path), out, cache, api_key=None)  # cache only
    assert (out / "external_review.json").read_bytes() == first


def test_cli_review_file_exits_3_without_key_on_new_transactions(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    code = cli.main(["review-file", str(their_file(tmp_path)), "--out", str(tmp_path / "o"),
                     "--cache", str(tmp_path / "empty.jsonl")])
    assert code == 3 and "cache misses" in capsys.readouterr().err


def test_cli_review_file_needs_a_path():
    with pytest.raises(SystemExit) as e:
        cli.main(["review-file"])
    assert e.value.code == 2


def test_cli_shows_sign_warning_before_anything_else(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Plaid-native file (income recorded as negative amounts) read with the default credit-positive sign.
    path = tmp_path / "plaid.json"
    path.write_text(json.dumps([raw(f"t{i}", -100.0, "STRIPE PAYOUT") for i in range(5)]))  # repeats get flagged
    code = cli.main(["review-file", str(path), "--out", str(tmp_path / "o"), "--cache", str(tmp_path / "c.jsonl")])
    err = capsys.readouterr().err
    assert code == 3 and "WARNING" in err and "--sign plaid" in err
    assert err.index("WARNING") < err.index("cache misses")
