"""Command line: `python -m fundo {all,generate,report,review} [--seed N] [--out DIR] [--refresh]`.

Exit codes: 0 ok, 1 API failure or budget abort, 3 cache miss without OPENAI_API_KEY
(2 is argparse's usage error).
"""

import argparse
import os
import sys

from . import llm, review_report
from .generate import generate
from .report import format_scoreboard, format_table, write_report

BUDGET_USD = 10.0
# Conservative per-call projection used only before live calls: tokens in/out, retries included.
PROJECTED_TOKENS = (1200, 100)


def _projected_usd(calls):
    uncached, _, output = llm.PRICES[llm.MODEL]
    return calls * (PROJECTED_TOKENS[0] * uncached + PROJECTED_TOKENS[1] * output) / 1_000_000


def _review(out, refresh):
    api_key = os.environ.get("OPENAI_API_KEY")
    if refresh and not api_key:
        print("--refresh needs OPENAI_API_KEY.", file=sys.stderr)
        return 3
    misses = review_report.preflight(out)
    total = sum(misses.values())
    if (total or refresh) and not api_key:
        print(f"At least {total} cache misses {misses}; export OPENAI_API_KEY or restore "
              f"{out}/llm_cache.jsonl.", file=sys.stderr)
        return 3
    if total or refresh:
        projected = _projected_usd(total * 2 if refresh else total)
        print(f"Live calls needed (attempt 0): {misses}; projected spend ${projected:.2f}")
        if projected > BUDGET_USD:
            print(f"Projected spend exceeds ${BUDGET_USD}; aborting.", file=sys.stderr)
            return 1
    try:
        doc = review_report.run(out, api_key=api_key, refresh=refresh)
    except llm.ApiError as e:
        print(f"OpenAI API failure: {e}", file=sys.stderr)
        return 1
    print(f"Reviewed with {llm.MODEL}; cached spend ${doc['spend_usd']:.4f}")
    for h in doc["hypotheses"]:
        print(f"{h['id']}  {h['status'].upper():6}  {h['observed']}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fundo")
    parser.add_argument("command", choices=("all", "generate", "report", "review"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="data")
    parser.add_argument("--refresh", action="store_true", help="re-call the API for every request")
    args = parser.parse_args(argv)
    if args.command in ("all", "generate"):
        generate(args.seed, args.out)
    if args.command in ("all", "report"):
        doc = write_report(args.out)
        print(format_table(doc["businesses"]))
        print(format_scoreboard(doc["hypotheses"]))
    if args.command == "review":
        return _review(args.out, args.refresh)
    return 0
