# review-evaluation Specification

## Purpose

Measure the reviewer against synthetic truth and report credit outcomes. Evaluation only; truth never feeds the reviewer.

## Requirements

### Requirement: Report content
`data/review_report.json` MUST include: label accuracy on the flagged set and on the audit set, dollar error before and after review (transaction level: sum of |amount| of transactions whose revenue status differs from truth, and of debits whose high-risk status differs from truth; business level: |offer − truth offer|), a hard-negatives list (transactions where legacy matched truth and the model proposed a different label, reported separately as proposed and as accepted by the gate), per-business truth/legacy/reviewed features, offer and decision, error analysis, flag coverage, and status counts including `review_failed`. A business where more than 40% of its reviewed transactions (flagged + audit) were corrected MUST be flagged for human review (`changed_share` = corrected / reviewed).

#### Scenario: Per-business outcomes
- Given a completed review
- Then each of the 10 businesses shows truth, legacy and reviewed features, offer and decision

#### Scenario: Many changes
- Given a business with 41% of its reviewed transactions corrected
- Then it carries a human-review flag

### Requirement: PFC ablation
The review MUST run in two variants, with and without `personal_finance_category` in flagging and prompt, under separate cache keys. The report MUST show both results and their difference.

#### Scenario: Delta reported
- Given both variants cached
- Then the report includes, on the shared intersection, group accuracy and dollar error (revenue and high-risk) for each variant, and the accuracy delta

### Requirement: Adversarial compliance
A set in `data/adversarial.json`, kept outside the 10-business data, MUST contain descriptions where obeying the embedded injection yields an incorrect label. The report MUST give the compliance rate (fraction where the model obeyed).

#### Scenario: Compliance rate
- Given N adversarial cases
- Then the report states obeyed count and rate

### Requirement: Reviewer hypotheses
Hypotheses MUST be written and committed before the first API call, kept verbatim, evaluated by check functions, and recorded as passed/failed in the report. Tests MUST verify the check functions, not require that hypotheses pass. There MUST be no xfail.

#### Scenario: Failed hypothesis
- Given a hypothesis that does not hold
- Then it is recorded as failed with the deciding observation and the test suite still passes
