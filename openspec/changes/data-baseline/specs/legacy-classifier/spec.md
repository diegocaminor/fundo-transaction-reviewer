# legacy-classifier Specification (new)

## Purpose

A deliberately naive keyword engine that mimics the legacy system, with realistic failures for the reviewer to correct.

## Requirements

### Requirement: First-match-wins ordered rules
The engine MUST apply an ordered list of (keyword, group) rules using case-insensitive substring matching. The first matching rule MUST decide the group. Unmatched descriptions MUST get `none`.

#### Scenario: Earlier rule wins
- Given a description that contains keywords of two rules
- When it is classified
- Then the group of the earlier rule is returned

#### Scenario: No match
- Given a description matching no rule
- When it is classified
- Then the group is `none`

### Requirement: No normalization
The engine MUST NOT normalize descriptions (no punctuation stripping, no whitespace collapsing, no token handling), so punctuation breaks keywords.

#### Scenario: Punctuation defeats a keyword
- Given the description "N.S.F. FEE" and an NSF keyword rule "NSF"
- When classified
- Then the group is `none`

### Requirement: Output shape and revenue rule
Legacy labels MUST be keyed by transaction id with the same shape as ground truth. `business` MUST default to true. `revenue` MUST use the same `is_revenue` rule as ground truth.

#### Scenario: Same shape as truth
- Given legacy labels and ground truth
- When keys and fields are compared
- Then both have the same transaction ids and fields

#### Scenario: Business defaults to true
- Given a legacy label for a personal credit that truth marks `business = false`
- When the label is read
- Then `business` is true and `revenue` is true if its group is `none`

### Requirement: Realistic failures
Rules MUST be written and frozen before trap tuning, and MUST target generic keyword weaknesses (punctuation, ambiguous counterparties, benign "loan"/hard-negative words), not specific rows.

#### Scenario: Hard negative misflagged
- Given "Lucky Dragon Chinese Buffet" in `biz_06`
- When classified by legacy
- Then it gets a gambling group while truth is `none`
