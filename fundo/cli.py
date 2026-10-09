"""Command line: `python -m fundo {all,generate,report,review,sensitivity,review-file} [options]`.

`review-file PATH` reviews transactions we did not generate (no ground truth needed); see
`fundo/external.py`. Declare the amount sign with --sign.

`all` runs generate -> baseline report -> review (from the committed cache) -> sensitivity.
Generated files go to --out; the frozen inputs (llm_cache.jsonl, adversarial.json) are read
from --inputs, which defaults to the repository's data/ directory.

Exit codes: 0 ok, 1 API failure or budget abort, 3 cache miss without OPENAI_API_KEY
(2 is argparse's usage error).
"""

import argparse
import json
import os
import sys
from pathlib import Path

from . import external, llm, review_report, sensitivity, sensitivity_hypotheses
from .generate import generate
from .report import format_scoreboard, format_table, write_report

REPO_DATA = Path(__file__).resolve().parent.parent / "data"

BUDGET_USD = 10.0
# Conservative per-call projection used only before live calls: tokens in/out, retries included.
PROJECTED_TOKENS = (1200, 100)


def _projected_usd(calls):
    uncached, _, output = llm.PRICES[llm.MODEL]
    return calls * (PROJECTED_TOKENS[0] * uncached + PROJECTED_TOKENS[1] * output) / 1_000_000


def _review(out, inputs, refresh):
    api_key = os.environ.get("OPENAI_API_KEY")
    if refresh and not api_key:
        print("--refresh needs OPENAI_API_KEY.", file=sys.stderr)
        return 3
    misses = review_report.preflight(out, inputs)
    total = sum(misses.values())
    if (total or refresh) and not api_key:
        print(f"At least {total} cache misses {misses}; export OPENAI_API_KEY or restore "
              f"{inputs}/llm_cache.jsonl.", file=sys.stderr)
        return 3
    if total or refresh:
        projected = _projected_usd(total * 2 if refresh else total)
        print(f"Live calls needed (attempt 0): {misses}; projected spend ${projected:.2f}")
        if projected > BUDGET_USD:
            print(f"Projected spend exceeds ${BUDGET_USD}; aborting.", file=sys.stderr)
            return 1
    try:
        doc = review_report.run(out, api_key=api_key, refresh=refresh, inputs_dir=inputs)
    except llm.ApiError as e:
        print(f"OpenAI API failure: {e}", file=sys.stderr)
        return 1
    print(f"Reviewed with {llm.MODEL}; cached spend ${doc['spend_usd']:.4f}")
    for h in doc["hypotheses"]:
        print(f"{h['id']}  {h['status'].upper():6}  {h['observed']}")
    return 0


def _sensitivity(out):
    load = lambda name: json.loads((Path(out) / name).read_text())
    result = sensitivity.run(load("transactions.json"), load("ground_truth.json"), load("businesses.json"))
    result["hypotheses"] = sensitivity_hypotheses.evaluate(result)
    sensitivity.write(Path(out) / "sensitivity.json", result)
    for h in result["hypotheses"]:
        print(f"{h['id']}  {h['status'].upper():6}  {h['observed']}")
    return 0


def _review_file(path, out, cache, sign, refresh):
    api_key = os.environ.get("OPENAI_API_KEY")
    try:
        _, warnings = external.load_transactions(path, sign)
        for w in warnings:  # shown first: a wrong sign also changes what gets flagged and how many calls run
            print(f"WARNING: {w}", file=sys.stderr)
        missing = external.misses(path, cache, sign)
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"Invalid transactions file: {e}", file=sys.stderr)
        return 2
    if (missing or refresh) and not api_key:
        print(f"At least {missing} cache misses for {path}; export OPENAI_API_KEY to review new "
              "transactions.", file=sys.stderr)
        return 3
    if missing or refresh:
        projected = _projected_usd(missing)
        print(f"Live calls needed (attempt 0): {missing}; projected spend ${projected:.2f}")
        if projected > BUDGET_USD:
            print(f"Projected spend exceeds ${BUDGET_USD}; aborting.", file=sys.stderr)
            return 1
    try:
        doc = external.run(path, out, cache, api_key=api_key, refresh=refresh, sign=sign)
    except llm.ApiError as e:
        print(f"OpenAI API failure: {e}", file=sys.stderr)
        return 1
    s = doc["summary"]
    print(f"{s['transactions']} transactions, {s['reviewed']} reviewed {s['status_counts']}, "
          f"PFC rules {'on' if s['pfc_rules_enabled'] else 'off'}, sign {s['sign']}")
    print(f"{'business':<16}{'days':>5}{'legacy offer':>15}{'reviewed offer':>16}  decision legacy/reviewed")
    for bid, b in doc["businesses"].items():
        print(f"{bid:<16}{b['history_days']:>5}{b['offer']['legacy']:>15.2f}{b['offer']['reviewed']:>16.2f}  "
              f"{b['decision']['legacy']}/{b['decision']['reviewed']}")
    print(f"{len(doc['changes'])} proposed changes; details in {out}/external_review.json")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fundo")
    parser.add_argument("command", choices=("all", "generate", "report", "review", "sensitivity", "review-file"))
    parser.add_argument("path", nargs="?", help="transactions JSON file (review-file only)")
    parser.add_argument("--sign", choices=external.SIGNS, default="credit-positive",
                        help="amount sign of the input: credit-positive (default) or plaid (positive = money out)")
    parser.add_argument("--cache", default=str(REPO_DATA / "llm_cache.jsonl"),
                        help="LLM cache file used by review-file")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="data")
    parser.add_argument("--inputs", default=str(REPO_DATA),
                        help="directory with the frozen llm_cache.jsonl and adversarial.json")
    parser.add_argument("--refresh", action="store_true", help="re-call the API for every request")
    args = parser.parse_args(argv)
    if args.command == "review-file":
        if not args.path:
            parser.error("review-file needs the path to a transactions JSON file")
        return _review_file(args.path, args.out, args.cache, args.sign, args.refresh)
    if args.command in ("all", "generate"):
        generate(args.seed, args.out)
    if args.command in ("all", "report"):
        doc = write_report(args.out)
        print(format_table(doc["businesses"]))
        print(format_scoreboard(doc["hypotheses"]))
    if args.command in ("all", "review"):
        code = _review(args.out, args.inputs, args.refresh)
        if code:
            return code
    if args.command in ("all", "sensitivity"):
        return _sensitivity(args.out)
    return 0
