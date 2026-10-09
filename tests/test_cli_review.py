"""CLI behavior for review, sensitivity and `all` (offline, from the committed cache)."""

import json
import shutil
from pathlib import Path

import pytest

from fundo import cli, llm

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def generated(tmp_path):
    out = tmp_path / "out"
    assert cli.main(["generate", "--out", str(out)]) == 0
    return out


def inputs_copy(tmp_path, drop_last=0):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    shutil.copy(DATA / "adversarial.json", inputs / "adversarial.json")
    lines = (DATA / "llm_cache.jsonl").read_text().splitlines(keepends=True)
    (inputs / "llm_cache.jsonl").write_text("".join(lines[: len(lines) - drop_last]))
    return inputs


def test_review_and_sensitivity_standalone_match_committed(tmp_path):
    out = generated(tmp_path)
    assert cli.main(["review", "--out", str(out)]) == 0
    assert cli.main(["sensitivity", "--out", str(out)]) == 0
    for name in ("review_report.json", "reviewed_labels.json", "sensitivity.json"):
        assert (out / name).read_bytes() == (DATA / name).read_bytes(), name


def test_review_uses_frozen_inputs_not_the_output_dir(tmp_path):
    out = generated(tmp_path)
    assert not (out / "llm_cache.jsonl").exists() and not (out / "adversarial.json").exists()
    assert cli.main(["review", "--out", str(out)]) == 0


def test_refresh_without_key_exits_3(tmp_path, capsys):
    assert cli.main(["review", "--out", str(generated(tmp_path)), "--refresh"]) == 3
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_all_with_incomplete_cache_exits_3_with_miss_count(tmp_path, capsys):
    inputs = inputs_copy(tmp_path, drop_last=3)
    code = cli.main(["all", "--out", str(tmp_path / "out"), "--inputs", str(inputs)])
    assert code == 3
    assert "At least 3 cache misses" in capsys.readouterr().err


def test_api_failure_exits_1(tmp_path, monkeypatch, capsys):
    inputs = inputs_copy(tmp_path, drop_last=1)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def fail(*a, **k):
        raise llm.ApiError("boom")
    monkeypatch.setattr(llm, "call_openai", fail)
    assert cli.main(["review", "--out", str(generated(tmp_path)), "--inputs", str(inputs)]) == 1
    assert "OpenAI API failure" in capsys.readouterr().err
    assert len((inputs / "llm_cache.jsonl").read_text().splitlines()) == \
        len((DATA / "llm_cache.jsonl").read_text().splitlines()) - 1  # nothing appended on failure


def test_usage_error_is_argparse_exit_2():
    with pytest.raises(SystemExit) as e:
        cli.main(["nonsense"])
    assert e.value.code == 2
