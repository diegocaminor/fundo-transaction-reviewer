# transaction-flagging Specification

## Purpose

Select which transactions the LLM reviewer sees, using code-only rules, plus a seeded audit sample of the rest.

## ADDED Requirements

### Requirement: Inputs exclude truth and traps
Flagging MUST read only transaction fields observable in production and the legacy label. It MUST NOT read ground-truth labels or `data/traps.json`. A test MUST enforce this.

#### Scenario: Truth and traps are unreachable
- Given flagging run with the truth and trap data replaced by sentinels that raise on access
- When flagging runs on all 10 businesses
- Then it completes and its output is identical to a normal run

### Requirement: Frozen rules
Flag rules MUST be defined and committed before the first API call and MUST NOT change after results are seen.

#### Scenario: Rules are reproducible
- Given the same transactions and legacy labels
- When flagging runs twice
- Then the flagged sets are identical

### Requirement: Seeded audit sample
A deterministic, seeded 5% sample of unflagged transactions MUST also be sent for review. It is documented as production-style monitoring: it estimates residual error where no truth exists. The seed MUST be derived with sha256, not `hash()`.

#### Scenario: Sample is deterministic and sized
- Given N unflagged transactions
- When the sample is drawn twice with the same seed
- Then both samples are identical, each has size round(0.05·N) (±1), and none is a flagged transaction

### Requirement: Coverage measured offline
Flag coverage and recall against synthetic truth MUST be computed only in evaluation, never used in flagging, and reported as an evaluation metric.

#### Scenario: Recall reported
- Given flagged sets and truth
- When evaluation runs
- Then the report includes flag recall of true mislabels and the count of mislabels missed outside the flagged set

### Requirement: Known flagging-rule bias
The flagging rules were written with knowledge of the planted scenarios in the synthetic data (for example, the hint vocabulary overlaps planted descriptions). Offline coverage on this dataset MUST therefore be reported and documented as optimistic, an upper bound, not an estimate of production coverage. The rules MUST NOT be changed to correct this bias, because rewriting them now would be equally informed by the data. The random audit sample MUST be presented as the independent, production-style estimate of misses outside the flagged set.

#### Scenario: Coverage labeled as optimistic
- Given the evaluation report
- When flag coverage is reported
- Then it is labeled optimistic (rules designed with knowledge of planted scenarios) and shown next to the audit-based estimate

### Requirement: Audit estimate with sampling variance
The audit-based residual error rate MUST be reported with its sample size and a 95% binomial confidence interval (Wilson), because a ~5% sample of unflagged transactions is small and its point estimate has high variance. A zero observed error count MUST NOT be reported as zero residual error; the interval's upper bound MUST be shown.

#### Scenario: Zero errors in the audit sample
- Given an audit sample of n transactions with 0 legacy mislabels
- When the report runs
- Then it shows 0/n with a Wilson 95% upper bound above zero, not "no misses"
