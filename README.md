# fundo-transaction-reviewer

LLM-based reviewer that validates labels produced by a legacy keyword transaction classification engine. Instead of re-labeling from scratch, it flags suspect classifications with a corrected label, a confidence level, and a short reason an underwriter can read in five seconds.

Built for the [Fundo AI Engineer Take-Home Challenge](https://fundo-llc.github.io/fundo-take-home/ai-engineer-challenge/).

> Status: complete. Approach, results, limitations and the Part 3 production strategy: [`SOLUTION.md`](SOLUTION.md).

## Quick start

Requires Python 3.11+. No API key and no install are needed to run. Copy and paste, in order:

```bash
# 1. Get the code
git clone https://github.com/diegocaminor/fundo-transaction-reviewer.git
cd fundo-transaction-reviewer

# 2. Re-generate every output from the committed LLM cache (offline, no key)
python3 -m fundo all

# 3. Confirm the outputs match the committed ones (prints nothing if identical)
git status --short

# 4. Run the tests (pytest is the only dependency)
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

Details on each command, the outputs and how to regenerate the cache with a key are in [Running](#running).

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

One page, no code: shadow deployment and gating, drift detection on engine/classifier retrains, reproducibility of declined decisions, and the underwriter feedback loop. See section 8 of `SOLUTION.md`.

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

Requires Python 3.11+. The package uses only the standard library: running it needs no install, no virtualenv and **no API key**. Run every command from the repository root.

### Reproduce everything (offline, from the committed cache)

```bash
python3 -m fundo all
```

`all` runs generate → baseline report → LLM review (from `data/llm_cache.jsonl`) → credit sensitivity, and rewrites every output in `data/` byte for byte. `git status` stays clean afterwards.

| File | Content |
|---|---|
| `data/businesses.json`, `transactions.json`, `ground_truth.json`, `traps.json` | Synthetic data (seed 42): 10 businesses, 2,000 Plaid-format transactions, truth labels, planted traps |
| `data/legacy_labels.json`, `baseline_report.json` | Legacy keyword engine labels and the legacy-vs-truth report |
| `data/llm_cache.jsonl` | Every raw model response (r1 and r2), keyed by model, prompt version, payload and attempt |
| `data/adversarial.json` | Frozen prompt-injection test set (outside the business data) |
| `data/reviewed_labels.json`, `review_report.json` | Final reviewer labels and evaluation (version r2) |
| `data/runs/r1_*.json` | The first, failed reviewer run, preserved for comparison |
| `data/sensitivity.json` | Mislabel Monte Carlo (2/5/10%), NSF observability, 61-day truncation |

Single steps: `python3 -m fundo generate | report | review | sensitivity` (each accepts `--seed` and `--out`). Generated files go to `--out` (default `data`); the frozen inputs (cache and adversarial set) are read from `--inputs` (default: this repository's `data/`).

### Run live with an API key (single command)

The same single command runs the whole pipeline live when the key is set in the environment. It calls the API only for requests missing from the cache, appends each response to it, then finishes the report:

```bash
export OPENAI_API_KEY=sk-...
python3 -m fundo all                  # live only for cache misses
python3 -m fundo all --refresh        # re-call every request and append to the cache
```

### Run on new data

A different seed generates different businesses and transactions, so their reviews are not in the cache and **need the key** (without it the command exits with code 3 and the number of misses). The number of calls depends on the seed; the command prints it and a projected spend before calling. Write to a separate folder so the committed outputs stay untouched:

```bash
export OPENAI_API_KEY=sk-...
python3 -m fundo all --seed 7 --out /tmp/fundo-seed7   # seed 7: 936 calls, about $0.27 and 17 minutes
```

New responses are appended to `data/llm_cache.jsonl`; restore it with `git checkout data/llm_cache.jsonl` if you do not want to keep them.

Before any live call the command prints the number of calls and a projected spend, and aborts above $10. Each response is written and fsynced to the cache before it is used, so an interrupted run resumes where it stopped. A full run is 1,205 calls with `gpt-4.1-mini` (~$0.35, ~20 minutes); the committed cache holds two runs and cost $0.70 in total.

Changing the prompt, payload or flag rules requires bumping `PROMPT_VERSION` / `FLAG_RULES_VERSION` (pinned by `tests/test_freeze.py`), which changes the cache keys and requires a refill.

Exit codes: `0` ok, `1` API failure or budget abort, `2` usage error, `3` cache miss without `OPENAI_API_KEY`.

### Review a transactions file you bring

`review-file` runs the legacy engine, flagging and the reviewer on any transactions file, with no ground truth and no businesses file. It reports, per business (`business_id`, or `account_id` if absent), the offer and decision under legacy and reviewed labels, plus every proposed change with its reason.

```bash
export OPENAI_API_KEY=sk-...                     # new transactions are not in the cache
python3 -m fundo review-file their_transactions.json --sign plaid --out /tmp/their-review
```

- **Input:** a JSON list of transactions, or a Plaid-style `{"transactions": [...]}` object. Required per row: `transaction_id`, `date`, `amount`, and `description` (or Plaid's `name`). Optional: `business_id`, `account_id`, `payment_channel`, `merchant_name`, `iso_currency_code`, `personal_finance_category`.
- **Sign (always declare it):** `--sign credit-positive` (default; this project and the Fundo PDF, credits positive) or `--sign plaid` (native Plaid, positive = money out). A wrong sign inverts every credit, so the command warns first when most `INCOME` transactions are negative.
- **Inferred:** history length per business from its first and last date. Without `personal_finance_category`, the two rules that use it are switched off.
- **Output:** `external_review.json` (per-business legacy vs reviewed features, offer and decision; proposed changes) and `reviewed_labels.json` in `--out`. Responses are appended to the cache (`--cache` to use another file), so a second run is offline.

### Tests

```bash
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

No test touches the network.

## Results

Predictions were committed before each measurement and are kept verbatim; failures are recorded, not tuned away. Full detail: `openspec/changes/archive/2026-10-09-reviewer-credit-impact/proposal.md` (hypothesis change log); canonical specs live in `openspec/specs/`.

### Reviewer: r1 vs r2 (same 7 frozen hypotheses)

| | Hypothesis | r1 | r2 |
|---|---|---|---|
| R1 | Undoes the biz_08 false decline | FAILED | PASSED |
| R2 | Fixes biz_09's NSF count | FAILED | PASSED |
| R3 | Cuts revenue $ error at least in half | FAILED | FAILED (−34%) |
| R4 | Lowers total offer error | FAILED | FAILED (worse) |
| R5 | Gate rejects most proposed hard negatives | FAILED | FAILED (106/110 accepted) |
| R6 | Resists injections (≤ 2 of 12 obeyed) | PASSED | FAILED (3 of 12) |
| R8 | Invalid output is rare | PASSED | PASSED |

| Outcome (primary variant) | Legacy | r1 | r2 |
|---|---|---|---|
| Correct approve/decline decisions | 9 / 10 | 2 / 10 | **10 / 10** |
| Revenue $ misclassified | $166,457 | $222,565 | $110,649 |
| High-risk $ misclassified | $3,926 | $4,208 | **$0** |
| Group accuracy on flagged set (secondary) | 0.55 | 0.55 | 0.81 |

- **r1 failed because of a payload design bug in this project.** The per-transaction payload carried the business-level field `bank_charges_nsf_fee: true`, which the model read as evidence that a transaction was an NSF charge. biz_02, the only business with that field false, got 0 wrong NSF proposals; the other nine got 205.
- **r2 changed only that.** The field was removed and `PROMPT_VERSION` bumped. Thresholds, flag rules, schema, gate, system prompt and hypotheses are identical.
- **Remaining failures in r2:**
  - **`active_advance` over-labeling.** Ordinary financing debits (a truck lease, auto-loan payments) were labeled as funder repayments. The offer subtracts 20 × daily funder payments, so one $3,100 lease payment removed $62,000 from biz_03's offer. This drives R4.
  - **Self-reported confidence does not discriminate.** 616 of 620 answers report ≥ 0.9, so the confidence gate accepts nearly every proposed correction, including 106 of 110 hard negatives. This drives R5 and holds in both runs.
  - **Prompt injection.** 3 of 12 injected instructions were obeyed with `personal_finance_category` (4 of 12 without), including a casino debit described as office supplies and an owner's personal credit claimed as business income.

`personal_finance_category` ablation (descriptive, shared 560 transactions): group accuracy 0.823 with and without it; revenue $ error lower with it ($100,873 vs $120,585).

Flag coverage of legacy errors is 100% on this dataset, but it is an **optimistic upper bound**: the flag rules were written with knowledge of the planted scenarios. The independent estimate is the 5% random audit: 0 legacy errors in 74 sampled transactions, Wilson 95% upper bound 4.9%.

### Credit sensitivity (Part 2)

S1–S3 passed and S4 failed: 6 of 8 approved businesses lose ≥ 1% of their offer when truncated to 61 days (no approve → decline flips). biz_09 flips from decline to approve at 61 days because its earlier NSF events fall outside the window: a short history can hide stress signals, not only revenue. For banks without NSF fees (biz_02), zero NSF is reported as unobserved (`nsf_observable: false`), with overdrafts as the proxy. The offer formula is never changed.
