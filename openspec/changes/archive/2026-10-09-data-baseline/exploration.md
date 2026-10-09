# Exploration: data-baseline

## Current state

Greenfield. The repo contains README.md, openspec/config.yaml and the dataset-schema PDF. No code and no pytest yet. Config rules: stdlib-first, deterministic seeded generation, no LLM calls in this phase.

## Recommendations

### 1. Layout (stdlib only; pytest as the single dev dependency)

```
pyproject.toml            # pytest config only
src/fundo/schema.py       # 13 groups + "none", EXCLUDING_GROUPS, record types, sign convention
src/fundo/generate.py     # business archetypes + seeded generator
src/fundo/legacy.py       # keyword engine
src/fundo/features.py     # revenue rule + features
src/fundo/offer.py        # offer formula
src/fundo/report.py       # legacy-vs-truth delta table
src/fundo/cli.py, __main__.py
data/transactions.json, ground_truth.json, businesses.json, legacy_labels.json
tests/
```

Features and offer live in their own modules so the next change reuses them unchanged on corrected labels.

### 2. CLI

`python -m fundo generate`, `python -m fundo report`, and `python -m fundo all` as the single documented command. Flags: `--seed` (default 42), `--out data/`. The report prints a table and writes `data/baseline_report.json`.

### 3. Determinism

- Local `random.Random(seed)`, never the global RNG.
- Fixed start date; never `date.today()`.
- Counter-based ids (`txn_{biz}_{n:04d}`).
- Output sorted by (business, date, id), dumped with `sort_keys=True, indent=2`.
- Amounts rounded to 2 decimals (or integer cents internally).
- Test: two runs produce byte-identical files; committed files equal regenerated ones.

### 4. Plaid fidelity

Keep the PDF minimum schema exactly. Optional Plaid-like additions: `pending`, `transaction_type`, `personal_finance_category {primary, detailed}` (occasionally noisy, as a second signal). Skip counterparties, location, logo_url. Bank-level facts (`bank_charges_nsf_fee`, `history_days`, `type`) live in businesses.json. Amount sign follows the PDF (credit positive), which is the reverse of Plaid's native convention; document it in schema.py.

### 5. Business archetypes

| Business | Trap |
|---|---|
| biz_01 Casa Norte Restaurant | All PDF baseline traps: card processor deposits, internal transfer, Square Capital repayment vs Square revenue, NSF, high-risk debit, hard negative, instruction-like description |
| biz_02 Salon, no-fee bank | Overdrafts without NSF fee lines → legacy NSF = 0, false clean signal |
| biz_03 Trucking, 61-day history | Part 2 short-history question |
| biz_04 Retailer with MCA funder | Daily ACH funder debits; same funder name as funding credit and repayment debit |
| biz_05 Contractor | Owner personal spending in the business account (business = false) |
| biz_06 Gambling-adjacent | Casino debits plus a legit "Lucky Dragon Chinese Buffet" hard negative |
| biz_07 | Garnishment and debt-settlement debits |
| biz_08 Ecommerce | Shopify/Stripe payouts, UCC lien debits, internal transfer that looks like revenue |
| biz_09 Clinic | NSF count at the threshold (5 vs 6) → offer flips to 0 |
| biz_10 Consultant | Clean control |

Noise levers: punctuation breaking keywords ("N.S.F.", "SQ *"), truncated and ALL-CAPS descriptions, ambiguous counterparties (Square, Venmo, Zelle, Stripe), the word "loan" in benign contexts. Instruction-like text appears in 1–2 businesses as data only.

### 6. Labels and engine output

- ground_truth.json and legacy_labels.json are keyed by transaction_id with the same shape: `{group, business, revenue, risk_signal?, notes}`.
- `revenue` is derived by a single `is_revenue(txn, group, business)` rule, never hand-labeled; a test enforces it.
- Legacy engine: ordered (keyword, group) rules, first match wins, case-insensitive substring, no normalization (so punctuation breaks it). Unmatched → "none". `business` defaults to true; `revenue` uses the same rule function.

### 7. Ambiguities

1. Which groups exclude revenue.
2. NSF > 5 threshold: NSF only, or NSF + Overdraft.
3. Definition of daily funder payments.
4. Monthly averaging: history_days / 30 vs calendar-month buckets.
5. "Not average monthly revenue" vs "none" semantics.
6. Include `personal_finance_category` or not.

### 8. Testing (pytest, unit-heavy)

Determinism, schema completeness, revenue-rule consistency, one parametrized legacy case per trap, hand-computed features/offer for biz_01 (NSF = 5 vs 6 boundary), and a report checkpoint: at least N businesses with a non-zero offer delta, and legacy accuracy within a plausible band (e.g. 60–90%).

## Approach

Recommended: hand-written biz_01 JSON fixture + templated generator for the rest. biz_01 stays readable for review; the rest scales. Alternative: everything generated from archetype specs (one mechanism, harder to inspect).

## Risks

- Data that the engine matches too well or too poorly makes the delta report meaningless; tune using the report as the feedback loop.
- Ground truth is produced by the generator, so ambiguities are only as real as the generator makes them.
- Writing both engine and data invites overfitting; write engine rules before tuning traps.
