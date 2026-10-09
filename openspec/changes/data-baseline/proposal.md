# Proposal: Data Baseline

## Intent

The reviewer (next change) needs realistic Plaid-format data, trusted ground truth, and a flawed legacy classifier to correct. This change builds that deterministic foundation. It also shows that legacy mislabels already move the offer.

## Scope

### In Scope
- Seeded stdlib generator: hand-written `biz_01` Casa Norte fixture and templated archetypes `biz_02`–`biz_10` (~90 days, ~2000 txns)
- Ground truth labels (generator-produced)
- Legacy keyword engine with realistic failures
- Deterministic features and offer
- Legacy-vs-truth delta report (checkpoint)
- pytest suite; single command `python -m fundo all`

### Out of Scope
- Mislabel sensitivity (2/5/10%), any LLM call, cache → `reviewer-credit-impact`
- SOLUTION.md / production strategy → `production-delivery`

## Capabilities

### New Capabilities
- `synthetic-data`: seeded Plaid-format transactions, businesses, ground truth
- `legacy-classifier`: ordered keyword rules, first match wins, unmatched → `none`
- `credit-features`: revenue rule, features, offer formula
- `baseline-report`: legacy-vs-truth label accuracy and offer delta per business

### Modified Capabilities
None

## Approach

Modules live under `src/fundo/`: schema, generate, legacy, features, offer, report, cli. They use local `random.Random(seed)`, a fixed start date, counter ids, sorted keys, and 2-decimal amounts. Features and offer stay label-source-agnostic, so the next change reuses them on corrected labels.

## Assumptions (user-approved)

- 13 groups, all exclude revenue. Revenue = business credit AND group == `none`. A single `is_revenue` rule feeds both truth and legacy; revenue is never hand-labeled.
- NSF > 5 counts NSF only. Overdraft is a separate feature.
- `daily_funder_payments` = mean of the per-day sum of funder (Active advance) debits, over days with such debits. The ×20 approximates business days per month.
- `avg_monthly_revenue` = revenue_total / (history_days / 30). This does not fix reduced evidence on 61-day histories.
- `personal_finance_category` is a noisy auxiliary signal, not truth.
- Features: revenue share of deposits, NSF count, overdraft count, high-risk debit share (dollar-weighted), avg monthly revenue, daily funder payments.
- Offer = max(0, 1.2 × avg_monthly_revenue − 20 × daily_funder_payments), or 0 if NSF > 5. **The floor at 0 is an explicit assumption.**
- Amount sign follows the PDF (credit positive), the reverse of native Plaid. Documented in schema.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/fundo/` | New | Generator, engine, features, offer, report, CLI |
| `data/` | New | transactions, businesses, ground_truth, legacy_labels, baseline_report |
| `tests/`, `pyproject.toml` | New | pytest only |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Engine matches too well or too poorly, so the delta is meaningless | Med | Per-business predictions written before the first run; a missed prediction is investigated, never fixed by loosening the criterion |
| Ground truth only as ambiguous as the generator makes it | Med | Trap table per business; document the limitation |
| Overfitting the engine to the data | Med | Rules frozen first; traps target generic keyword weaknesses |

## Rollback Plan

Greenfield. Delete the `feat/data-baseline` branch.

## Dependencies

- pytest (dev only)

## Success Criteria

- [ ] Two runs of `python -m fundo all` produce byte-identical outputs
- [ ] `biz_01` contains every PDF baseline trap
- [ ] Every per-business prediction below holds (asserted by tests)
- [ ] `python -m pytest` passes

### Per-business predictions

Written before any data is generated. Delta = legacy − truth. Each trap must produce its predicted effect and direction; if a prediction fails, the data or the engine is wrong, not the prediction. Changing a prediction requires a written justification in this file.

| Business | Trap | Predicted effect (legacy vs truth) |
|---|---|---|
| biz_01 Casa Norte | Internal transfer credit and Square Capital lines mislabeled | Revenue inflated, funder payments understated → offer **higher** |
| biz_02 Salon, no-fee bank | Overdrafts without NSF fee lines | NSF = 0 in both; overdraft risk invisible to legacy; offer **unchanged** (risk hidden, not priced) |
| biz_03 Trucking, 61 days | Short history, no planted mislabels | Labels and offer **exactly equal**; avg monthly revenue uses history_days / 30 |
| biz_04 Retailer + MCA | Funder funding credit counted as revenue; daily debits missed by punctuation | Revenue inflated, funder payments understated → offer **higher** |
| biz_05 Contractor | Owner personal credits in business account | Revenue inflated → offer **higher** |
| biz_06 Sports bar | "Lucky Dragon" restaurant flagged as gambling (hard negative) | High-risk share **overstated**; offer **unchanged** |
| biz_07 Auto repair shop | High-risk debits missed by punctuation | High-risk share **understated**; offer **unchanged** |
| biz_08 Ecommerce | `STRIPE TRANSFER` payouts match `nsf` inside "tra**nsf**er" | Legacy NSF > 5, truth NSF ≤ 5 → legacy offer = 0, truth offer > 0 → **false decline** |
| biz_09 Clinic | One "N.S.F." line missed (legacy 5, truth 6) | Truth offer = 0, legacy offer > 0 → **approves a decline** |
| biz_10 Consultant | Clean control | Labels and offer **exactly equal** |

#### Prediction change log

- **biz_08 (2026-10-09).** Original prediction: Stripe payouts matched by rule 13 (`transfer`) → revenue understated → offer lower. Phase 3 tests showed rule 1 (`nsf`) matches the substring inside "transfer", so rule 13 is unreachable and every description containing "transfer" is labeled NSF. The legacy rule is kept unchanged as a realistic substring bug. biz_08 now predicts a false decline through the NSF threshold, the mirror of biz_09 (approves a decline).

#### Routine data policy

Routine descriptions are written to be realistic for each business type. They are NOT filtered to avoid legacy keywords (including "transfer"). Legacy mislabels on non-trap transactions are measured as collateral in the report. If collateral changes an offer decision (0 vs > 0) in a business not predicted to change, or breaks the exact-equality predictions for biz_03/biz_10, that is surfaced as a design problem and not tuned away in the data.
