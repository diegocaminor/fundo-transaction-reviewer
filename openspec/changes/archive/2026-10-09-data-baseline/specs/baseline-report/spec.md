# baseline-report Specification (new)

## Purpose

Legacy-vs-truth comparison per business: label accuracy and feature/offer deltas. Delta = legacy - truth.

## Requirements

### Requirement: Report content and command
`python -m fundo all` MUST generate data, classify, and write `data/baseline_report.json`, and print a table. For each business the report MUST include label accuracy, the features and offer under truth and under legacy, and their deltas. Output MUST be deterministic (sorted keys) and byte-identical across runs.

#### Scenario: One command, deterministic
- Given a clean checkout
- When `python -m fundo all` runs twice
- Then all outputs, including `baseline_report.json`, are byte-identical

### Requirement: Per-business predictions
Each pre-registered prediction below MUST be evaluated by a pure check function implementing it literally, and its status ("passed" or "failed") with the deciding observation MUST be recorded in the report's top-level `hypotheses` list and printed on stdout. Prediction text MUST NOT be rewritten after measurement; a failed prediction is a finding, not a defect to hide, and the criterion MUST NOT be loosened. Tests MUST verify the check functions on synthetic entries and the measured baseline, not require that every prediction passes. Businesses without planted mislabels (`biz_03`, `biz_10`) are predicted to show exact equality: labels and computations are deterministic, so no tolerance is needed. Direction predictions ("offer delta > 0" / "< 0") MUST exceed a materiality threshold of 1% of the truth offer in the predicted direction. This 1% is a materiality threshold chosen by this project to ignore financially irrelevant deltas; it is NOT a requirement of the challenge and NOT a numerical tolerance. Changing a prediction requires written justification in the proposal.

#### Scenario: biz_01 Casa Norte
- Given internal transfer credit and Square Capital lines mislabeled by legacy
- When deltas are computed
- Then legacy revenue is higher, daily funder payments are lower, and offer delta > 0

#### Scenario: biz_02 Salon, no-fee bank
- Given overdrafts without NSF fee lines
- When deltas are computed
- Then NSF = 0 under both labelings, and offer delta = 0 (overdraft count is not priced)
- Observed (seed 42): FAILED. Legacy NSF 2 vs truth 0 (routine savings sweeps contain "transfer"); offer delta 0 held.

#### Scenario: biz_03 Trucking, 61 days
- Given a 61-day history with no planted mislabels
- When deltas are computed
- Then legacy labels equal truth labels, offer delta is exactly 0, and avg monthly revenue uses history_days / 30
- Observed (seed 42): FAILED. 2 collateral `internal_transfer→nsf` mislabels (NSF +2); offer delta exactly 0 held.

#### Scenario: biz_04 Retailer with MCA
- Given a funder funding credit counted as revenue and daily debits missed by punctuation
- When deltas are computed
- Then legacy revenue is higher, funder payments are lower, and offer delta > 0

#### Scenario: biz_05 Contractor
- Given owner personal credits (business = false) in the business account
- When deltas are computed
- Then legacy revenue is higher and offer delta > 0

#### Scenario: biz_06 Sports bar (gambling-adjacent)
- Given "Lucky Dragon" flagged as gambling by legacy
- When deltas are computed
- Then legacy high-risk debit share is greater than truth, and offer delta = 0

#### Scenario: biz_07 Auto repair shop (garnishment / debt settlement)
- Given high-risk debits missed by legacy due to punctuation
- When deltas are computed
- Then legacy high-risk share is lower than truth, and offer delta = 0

#### Scenario: biz_08 Ecommerce
- Given daily "STRIPE TRANSFER" payout credits, which legacy labels `nsf` because "transfer" contains the substring "nsf"
- When deltas are computed
- Then legacy NSF > 5, truth NSF <= 5, legacy offer = 0 and truth offer > 0 (false decline)

#### Scenario: biz_09 Clinic
- Given one "N.S.F." line missed by legacy
- When deltas are computed
- Then legacy NSF = 5, truth NSF = 6, truth offer = 0, legacy offer > 0 (approves a decline)
- Observed (seed 42): FAILED. Legacy NSF 7 (5 plain + 2 sweeps via the substring bug) vs truth 6; both decline. The punctuation miss alone (`planned_only`) would approve $67,478.75; `collateral_changes_outcome` = true.

#### Scenario: biz_10 Consultant control
- Given a clean control business
- When deltas are computed
- Then legacy labels equal truth labels and all feature and offer deltas are exactly 0
- Observed (seed 42): FAILED. 2 collateral `internal_transfer→nsf` mislabels (NSF +2); offer delta exactly 0 held.

### Requirement: Collateral mislabels
The generator MUST record which transactions are planted traps (`data/traps.json`: transaction id → trap name), without changing the label shape. The report MUST count, per business, legacy mislabels on non-trap transactions ("collateral") and MUST flag any business where collateral alone changes the offer decision (offer 0 vs > 0). Routine descriptions MUST NOT be filtered to avoid legacy keywords. A flagged business MUST be treated as a design problem to surface, not fixed by editing routine vocabulary.

#### Scenario: Collateral is measured, not hidden
- Given realistic routine descriptions that may contain legacy keywords (e.g. "ONLINE TRANSFER TO SAVINGS")
- When the report runs
- Then each business shows its collateral mislabel count, and businesses where collateral flips the offer decision are flagged

### Requirement: Collateral changes outcome
For each business the report MUST include `collateral_changes_outcome`: true when the full legacy offer decision differs from the decision reached with legacy labels on planted-trap transactions only (`planned_only`) and truth labels elsewhere. It MUST be shown in the stdout table.

#### Scenario: Collateral reverses a planned outcome
- Given a business whose planned traps alone would approve while legacy labels yield a decline
- When the report runs
- Then `collateral_changes_outcome` is true and the table marks it
