# credit-sensitivity Specification

## Purpose

Quantify how mislabel rates move features and offers (challenge Part 2). The offer formula is unchanged.

## ADDED Requirements

### Requirement: Mislabel Monte Carlo
For rates 2%, 5% and 10%, `round(p·n)` transactions per business MUST be corrupted, 200 repetitions each, seeded via sha256 (not `hash()`), under two models: a confusion map fixed in code before running, and a uniform swap. The rate MUST be defined at the transaction level: each corrupted transaction receives exactly one corruption. The confusion model MUST include business/personal flips (group kept, `business` toggled) as well as group changes, so revenue errors from personal/business misclassification are covered; the uniform model changes `group` only. The output MUST report how many corruptions were group changes vs business flips. Output (`data/sensitivity.json`) MUST give mean, p5 and p95 of features and offer, plus decision-flip probability.

#### Scenario: Grid and determinism
- Given the same seed
- When sensitivity runs twice
- Then the output is byte-identical and contains 3 rates x 2 models x 200 reps summarized per business

#### Scenario: Flip probability
- Given a business whose decision flips in 30 of 200 reps
- Then its decision-flip probability is 0.15

### Requirement: NSF observability
Each business MUST report `nsf_observable`, false for no-fee banks where NSF cannot be observed, with the overdraft count as the proxy signal. The offer formula MUST NOT change.

#### Scenario: biz_02
- Given the no-fee-bank business
- Then `nsf_observable` is false and the overdraft count is reported

### Requirement: Truncation experiment
A 61-day truncation experiment MUST be reported: each of the nine 90-day businesses is recomputed on only its last 61 days and compared with its own 90-day features, offer and decision (truth labels). biz_03 has no 90-day counterpart and MUST NOT be used as the experiment's evidence. Businesses with history below 90 days MUST carry a low-history warning, and an NSF count scaled to 90 days (`nsf × 90 / history_days`) MAY be reported as information only. These add reported fields only; the offer formula is unchanged.

#### Scenario: Truncation compares a business with itself
- Given a 90-day business
- When the truncation experiment runs
- Then its 61-day and 90-day features, offer and decision are reported side by side, with the offer delta and whether the decision flips

#### Scenario: Low-history warning
- Given biz_03 with 61 days of history
- When the report runs
- Then a low-history warning is present and the formula output is unchanged
