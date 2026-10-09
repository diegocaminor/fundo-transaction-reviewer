"""Command line: `python -m fundo {all,generate,report} [--seed N] [--out DIR]`."""

import argparse

from .generate import generate
from .report import format_scoreboard, format_table, write_report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fundo")
    parser.add_argument("command", choices=("all", "generate", "report"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="data")
    args = parser.parse_args(argv)
    if args.command in ("all", "generate"):
        generate(args.seed, args.out)
    if args.command in ("all", "report"):
        doc = write_report(args.out)
        print(format_table(doc["businesses"]))
        print(format_scoreboard(doc["hypotheses"]))
    return 0
