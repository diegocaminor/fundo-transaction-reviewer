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

Modules live under `fundo/` (flat layout; see design): schema, generate, legacy, features, offer, report, cli. They use a local per-business `random.Random` seeded from sha256(seed, business_id), a fixed start date, counter ids, sorted keys, and 2-decimal amounts. Features and offer stay label-source-agnostic, so the next change reuses them on corrected labels.

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
| `fundo/` | New | Generator, engine, features, offer, report, CLI |
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
- [ ] Every per-business prediction below is evaluated and its status recorded in the report (see Prediction change log)
- [ ] `python -m pytest` passes

### Per-business predictions

Written before any data is generated. Delta = legacy − truth. Each trap must produce its predicted effect and direction; if a prediction fails, the data or the engine is wrong, not the prediction. Changing a prediction requires a written justification in this file.

| Business | Trap | Predicted effect (legacy vs truth) | Observed (seed 42) |
|---|---|---|---|
| biz_01 Casa Norte | Internal transfer credit and Square Capital lines mislabeled | Revenue inflated, funder payments understated → offer **higher** | PASSED: offer +12,100.01 (+21.4%); revenue +7,666.67/mo, funder payments -145.00/day |
| biz_02 Salon, no-fee bank | Overdrafts without NSF fee lines | NSF = 0 in both; overdraft risk invisible to legacy; offer **unchanged** (risk hidden, not priced) | FAILED: legacy NSF 2 vs truth 0 (routine savings sweeps contain "transfer" → legacy `nsf`); offer delta 0 |
| biz_03 Trucking, 61 days | Short history, no planted mislabels | Labels and offer **exactly equal**; avg monthly revenue uses history_days / 30 | FAILED: labels not equal, 2 sweep mislabels, NSF +2; offer delta 0.00 holds |
| biz_04 Retailer + MCA | Funder funding credit counted as revenue; daily debits missed by punctuation | Revenue inflated, funder payments understated → offer **higher** | PASSED: offer +22,200.00 (+52.3%); revenue +13,333.33/mo, funder payments -310.00/day |
| biz_05 Contractor | Owner personal credits in business account | Revenue inflated → offer **higher** | PASSED: offer +6,215.80 (+13.4%); revenue +5,179.84/mo |
| biz_06 Sports bar | "Lucky Dragon" restaurant flagged as gambling (hard negative) | High-risk share **overstated**; offer **unchanged** | PASSED: high-risk share +0.0039; offer delta 0 |
| biz_07 Auto repair shop | High-risk debits missed by punctuation | High-risk share **understated**; offer **unchanged** | PASSED: high-risk share -0.0308; offer delta 0 |
| biz_08 Ecommerce | `STRIPE TRANSFER` payouts match `nsf` inside "tra**nsf**er" | Legacy NSF > 5, truth NSF ≤ 5 → legacy offer = 0, truth offer > 0 → **false decline** | PASSED: NSF legacy 92 vs truth 0; offer 0.00 vs 39,230.32 |
| biz_09 Clinic | One "N.S.F." line missed (legacy 5, truth 6) | Truth offer = 0, legacy offer > 0 → **approves a decline** | FAILED: legacy NSF 7 vs truth 6, both offers 0 (two legacy bugs cancel) |
| biz_10 Consultant | Clean control | Labels and offer **exactly equal** | FAILED: labels not equal, 2 sweep mislabels, NSF +2; offer delta 0.00 holds |

#### Prediction change log

- **biz_08 (2026-10-09).** Original prediction: Stripe payouts matched by rule 13 (`transfer`) → revenue understated → offer lower. Phase 3 tests showed rule 1 (`nsf`) matches the substring inside "transfer", so rule 13 is unreachable and every description containing "transfer" is labeled NSF. The legacy rule is kept unchanged as a realistic substring bug. biz_08 now predicts a false decline through the NSF threshold, the mirror of biz_09 (approves a decline).

- **biz_09 data (2026-10-09).** Phase 5 generated biz_09 as the only business without routine savings sweeps; the stated reason was that sweeps would push legacy NSF above 5 and flip its decision. That reasoning protected a prediction using legacy behavior and violates the routine data policy. Two monthly `ONLINE TRANSFER TO SAV` debits (truth `internal_transfer`) were added, matching peer businesses. The biz_09 prediction ("approves a decline") is NOT changed and the legacy engine is NOT changed. Phase 6 measures the interaction: legacy NSF may become 5 (plain) + 2 (substring bug on sweeps) = 7, which would cancel the punctuation miss and make legacy and truth both decline. If that happens, the prediction fails and is reported as a finding (two legacy bugs masking each other) for SOLUTION.md, not tuned away.

- **Phase 6 measurement (2026-10-09).** The report evaluated every original prediction literally; the prediction texts above were NOT rewritten. Passed: biz_01, 04, 05, 06, 07, 08. Failed: biz_02, biz_03, biz_09, biz_10.
  - biz_02, biz_03, biz_10: routine savings sweeps (`ONLINE TRANSFER TO SAV`) contain "transfer", so legacy rule 1 labels them `nsf`. Every business gets 2-3 collateral NSF mislabels (legacy NSF headroom under the > 5 threshold shrinks by 2-3). biz_02 therefore has legacy NSF 2 (not 0); biz_03 and biz_10 have unequal labels and NSF +2. Their offers still match exactly (delta 0), because NSF stays <= 5.
  - biz_09: the two legacy bugs cancel, as anticipated above. Legacy NSF = 5 (plain) + 2 (sweeps) = 7 vs truth 6, so both decline. Only the punctuation miss alone (`planned_only`) would approve $67,478.75 against a truth decline; the substring bug on sweeps hides it (`collateral_changes_outcome` = true). Finding for SOLUTION.md.
  - Hypotheses are kept verbatim and marked passed/failed in this file and in `data/baseline_report.json` (`hypotheses`). pytest asserts the measured baseline and invariants, not these hypotheses; no xfail.
- **Success criterion wording (2026-10-09).** The criterion "Every per-business prediction below holds (asserted by tests)" became "Every per-business prediction below is evaluated and its status recorded in the report". Why: the predictions are hypotheses about how legacy errors move credit outcomes, written before any data existed. Requiring them to hold would make a failed hypothesis a failed build, which creates pressure to edit data, the engine or the prediction until it passes. That is the overfitting this change was designed to avoid. Failed hypotheses are results, not defects. Regression protection moved to pytest, which asserts the measured baseline (snapshot) and system invariants. The prediction texts themselves were not changed.

#### Routine data policy

Routine descriptions are written to be realistic for each business type. They are NOT filtered to avoid legacy keywords (including "transfer"). Legacy mislabels on non-trap transactions are measured as collateral in the report. If collateral changes an offer decision (0 vs > 0) in a business not predicted to change, or breaks the exact-equality predictions for biz_03/biz_10, that is surfaced as a design problem and not tuned away in the data.
