# fundo-transaction-reviewer

LLM-based reviewer that validates labels produced by a legacy keyword transaction classification engine. Instead of re-labeling from scratch, it flags suspect classifications with a corrected label, a confidence level, and a short reason an underwriter can read in five seconds.

Built for the [Fundo AI Engineer Take-Home Challenge](https://fundo-llc.github.io/fundo-take-home/ai-engineer-challenge/).

> Status: work in progress.

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

_TBD — commands will be documented here once the pipeline exists._

```bash
# Run from cache (no API key needed)
# TBD

# Regenerate the LLM cache (requires API key)
# TBD
```

## Deliverables

- [ ] Code that runs from a clean checkout and reproduces output from cache
- [ ] `README.md` with copy-paste run and cache-regeneration commands
- [ ] `SOLUTION.md` (2–3 pages): approach, results, model/prompt choices, code vs. model boundary, Part 2 answers, Part 3 plan, AI tooling disclosure
