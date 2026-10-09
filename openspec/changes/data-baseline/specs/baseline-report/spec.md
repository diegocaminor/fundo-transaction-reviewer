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
Each prediction below MUST be asserted by a test. Businesses without planted mislabels (`biz_03`, `biz_10`) MUST show exact equality: labels and computations are deterministic, so no tolerance is needed. Direction predictions ("offer delta > 0" / "< 0") MUST exceed a materiality threshold of 1% of the truth offer in the predicted direction. This 1% is a materiality threshold chosen by this project to ignore financially irrelevant deltas; it is NOT a requirement of the challenge and NOT a numerical tolerance. A failed prediction MUST be investigated (data or engine is wrong); the criterion MUST NOT be loosened. Changing a prediction requires written justification in the proposal.

#### Scenario: biz_01 Casa Norte
- Given internal transfer credit and Square Capital lines mislabeled by legacy
- When deltas are computed
- Then legacy revenue is higher, daily funder payments are lower, and offer delta > 0

#### Scenario: biz_02 Salon, no-fee bank
- Given overdrafts without NSF fee lines
- When deltas are computed
- Then NSF = 0 under both labelings, and offer delta = 0 (overdraft count is not priced)

#### Scenario: biz_03 Trucking, 61 days
- Given a 61-day history with no planted mislabels
- When deltas are computed
- Then legacy labels equal truth labels, offer delta is exactly 0, and avg monthly revenue uses history_days / 30

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
- Given Stripe payouts matched by legacy as transfers
- When deltas are computed
- Then legacy revenue is lower and offer delta < 0

#### Scenario: biz_09 Clinic
- Given one "N.S.F." line missed by legacy
- When deltas are computed
- Then legacy NSF = 5, truth NSF = 6, truth offer = 0, legacy offer > 0 (approves a decline)

#### Scenario: biz_10 Consultant control
- Given a clean control business
- When deltas are computed
- Then legacy labels equal truth labels and all feature and offer deltas are exactly 0
