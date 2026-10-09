# fundo-transaction-reviewer

LLM-based reviewer that validates labels produced by a legacy keyword transaction classification engine. Instead of re-labeling from scratch, it flags suspect classifications with a corrected label, a confidence level, and a short reason an underwriter can read in five seconds.

Built for the [Fundo AI Engineer Take-Home Challenge](https://fundo-llc.github.io/fundo-take-home/ai-engineer-challenge/).

> Status: work in progress. Phase 1 (synthetic data, legacy engine, credit features and baseline report) is complete.

## Context

Fundo provides revenue-based advances to small businesses by analyzing 90 days of bank transactions to extract features: monthly revenue, NSF/overdraft counts, other funders' payments, and high-risk activity flags.

Known limitations of the keyword engine:

- Bank descriptions are noisy.
- The same counterparty can mean different things.
- Punctuation can break keyword matching.
- Banks that charge no NSF fees create false signals.

## Scope

### Part 1 — Reviewer

For each flagged transaction, output:

- Corrected label: group, business/personal flag, revenue status
- Confidence level
- Five-second reason for the underwriter

Key design decisions:

- What the model can change vs. what stays in deterministic code
- How to handle untrusted, counterparty-written text (prompt injection)

### Part 2 — Credit impact analysis

Per business, before and after corrections:

- Revenue as share of total deposits
- NSF/overdraft counts
- High-risk share of debits

Offer formula:

```
offer = 1.2 × avg_monthly_revenue − 20 × daily_funder_payments   # 0 if NSF > 5
```

Also: sensitivity of features and offers to 2%, 5%, and 10% mislabeling rates, plus answers to:

- How to interpret zero NSF when the bank charges no fees
- How to handle 61-day histories when the model was trained on 90 days

### Part 3 — Production strategy

One page, no code: shadow deployment and gating, drift detection on engine/classifier retrains, reproducibility of declined decisions, and the underwriter feedback loop. See `SOLUTION.md`.

## Classification groups

| Group |
|---|
| Not average monthly revenue |
| NSFs |
| Overdraft |
| Internal transfer |
| UCC |
| Active advance |
| Auto deposit |
| Revenue verification |
| High risk — gambling |
| High risk — bankruptcy |
| High risk — debt settlement |
| High risk — garnishment |
| High risk — other |

A transaction is **revenue** when it is a business credit AND no excluding group matched.

## Data

Synthetic only — no real customer data.

- Plaid transaction format
- ~10 businesses, 90 days each (~2,000 transactions)
- Includes the edge cases that matter to funders (hard negatives, no-fee banks, short histories, etc.)

## Constraints

- Expected effort: 6–8 hours
- LLM spend: under $10 USD
- Single documented command runs everything, with the API key in an environment variable
- LLM responses are committed as a cache so results reproduce without an API key

## Running

Requires Python 3.11+. The package uses only the standard library, so running it needs no install, virtualenv or API key. Run every command from the repository root.

### Baseline: data, legacy engine and report

```bash
python3 -m fundo all
```

This regenerates the synthetic data (seed 42), labels it with the legacy keyword engine, and writes the legacy-vs-truth report to `data/`:

| File | Content |
|---|---|
| `data/businesses.json` | 10 synthetic businesses |
| `data/transactions.json` | ~2,000 Plaid-format transactions |
| `data/ground_truth.json` | Correct label per transaction |
| `data/traps.json` | Which transactions are planted traps |
| `data/legacy_labels.json` | Legacy keyword engine labels |
| `data/baseline_report.json` | Per-business features, offers, planned vs unplanned mislabels, and hypothesis results |

All outputs are committed. A run with the default seed reproduces them byte for byte, so `git status` stays clean afterwards.

Other subcommands and options:

```bash
python3 -m fundo generate          # data only
python3 -m fundo report            # legacy labels + report from existing data
python3 -m fundo all --seed 7 --out /tmp/fundo   # different seed, separate folder
```

Amounts follow the Fundo PDF sign convention: credits are positive and debits negative, the reverse of native Plaid.

### Tests

```bash
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

### LLM reviewer

Not implemented yet (Phase 2). The commands to run it from the committed cache and to regenerate the cache will be added here.

## Deliverables

- [ ] Code that runs from a clean checkout and reproduces output from cache
- [ ] `README.md` with copy-paste run and cache-regeneration commands
- [ ] `SOLUTION.md` (2–3 pages): approach, results, model/prompt choices, code vs. model boundary, Part 2 answers, Part 3 plan, AI tooling disclosure
