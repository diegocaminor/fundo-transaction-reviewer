# credit-features Specification (new)

## Purpose

Deterministic revenue rule, features, and offer, independent of the label source (truth, legacy, or corrected labels).

## Requirements

### Requirement: Single revenue rule
`is_revenue(txn, group, business)` MUST return true only if the transaction is a credit AND `business` is true AND `group == "none"`. All 13 groups MUST exclude revenue. No other path MAY set revenue.

#### Scenario: Business credit with no group
- Given a credit, business = true, group `none`
- When `is_revenue` is evaluated
- Then it returns true

#### Scenario: Excluding group
- Given a credit, business = true, group "internal_transfer" (or any of the 13)
- When evaluated
- Then it returns false

#### Scenario: Personal credit or debit
- Given a credit with business = false, or a debit with group `none`
- When evaluated
- Then it returns false

### Requirement: Features
Given a business, its transactions, and a label set, the system MUST compute: revenue share of deposits, NSF count, overdraft count, high-risk debit share (dollar-weighted), avg monthly revenue, and daily funder payments. Features MUST be label-source-agnostic.

#### Scenario: Features from any label set
- Given the same transactions with truth labels and with legacy labels
- When features are computed
- Then the same function is used and only the labels differ

#### Scenario: Overdraft is separate
- Given a business with overdraft lines and no NSF lines
- When features are computed
- Then NSF count is 0 and overdraft count is greater than 0

### Requirement: Monthly revenue normalization
`avg_monthly_revenue` MUST equal revenue_total / (history_days / 30), using `history_days` from the business record.

#### Scenario: 61-day history
- Given revenue_total = 6100.00 and history_days = 61
- When avg monthly revenue is computed
- Then it equals 3000.00

### Requirement: Daily funder payments
`daily_funder_payments` MUST be the mean of the per-day sum of funder (Active advance) debits, taken over the days that have at least one such debit. It MUST be 0 if there are none.

#### Scenario: Mean over days with debits
- Given funder debits of 100.00 on day 1, 100.00 and 50.00 on day 2, none on day 3
- When computed
- Then the result is 125.00

#### Scenario: No funder debits
- Given no funder debits
- When computed
- Then the result is 0

### Requirement: Offer formula
Offer MUST be `max(0, 1.2 * avg_monthly_revenue - 20 * daily_funder_payments)`, and 0 if NSF count > 5. The floor at 0 is an explicit assumption. The NSF test MUST use the NSF count only, excluding overdrafts.

#### Scenario: NSF boundary
- Given identical features with NSF = 5 and avg_monthly_revenue = 10000, funder payments = 100
- When offer is computed
- Then the offer is 10000.00 (> 0); with NSF = 6 it is 0

#### Scenario: Overdrafts do not trigger the cap
- Given NSF = 0 and overdraft count = 10
- When offer is computed
- Then the offer follows the formula and is not forced to 0

#### Scenario: Floor at zero
- Given 1.2 * avg_monthly_revenue = 1000 and 20 * daily_funder_payments = 3000
- When offer is computed
- Then the offer is 0, not negative

#### Scenario: Hand-computed fixtures and locked biz_01 values
- Given small inline fixtures whose expected features and offer are derived by hand in the tests
- When features and offer are computed
- Then they equal the hand-derived values
- And the full biz_01 values are locked by the committed report snapshot. This is regression protection, not an independent hand computation (changed from the original "hand-computed biz_01" scenario, which was impractical for 283 transactions; see tasks 6.2).
