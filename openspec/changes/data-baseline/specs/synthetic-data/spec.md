# synthetic-data Specification (new)

## Purpose

Seeded, Plaid-format synthetic transactions, business facts, and generator-produced ground truth for 10 businesses.

## Requirements

### Requirement: Dataset composition
The generator MUST produce 10 businesses (`biz_01`..`biz_10`) with about 90 days and about 2000 transactions in total. `biz_03` MUST have a 61-day history. `biz_01` (Casa Norte Restaurant) MUST be a hand-written fixture; `biz_02`..`biz_10` MUST be templated archetypes. `biz_01` MUST contain every PDF baseline trap: card processor deposits, internal transfer credit, Square Capital repayment vs Square revenue, NSF fee, high-risk debit, hard negative, and one instruction-like description.

Business roster (`type` in businesses data drives the routine background): biz_01 restaurant (Casa Norte), biz_02 hair salon, biz_03 trucking, biz_04 retail store, biz_05 contractor, biz_06 sports bar, biz_07 auto repair shop, biz_08 ecommerce, biz_09 medical clinic, biz_10 consulting.

All generated content (descriptions, merchant names, business names, notes, report text) MUST be in English.

#### Scenario: Business set and history length
- Given the default seed
- When the dataset is generated
- Then it contains exactly `biz_01`..`biz_10`, and `history_days` is 61 for `biz_03`

#### Scenario: biz_01 contains every baseline trap
- Given the generated `biz_01` transactions and ground truth
- When each trap type is looked up
- Then at least one transaction exists for each trap listed above

### Requirement: Schema completeness
Every transaction MUST include all PDF minimum fields (`transaction_id`, `business_id`, `account_id`, `date`, `description`, signed `amount`, `iso_currency_code`, `payment_channel`); `merchant_name` is optional. Amount sign MUST follow the PDF (credit positive), documented in the schema. `personal_finance_category` MAY be present and MUST be treated as a noisy auxiliary signal, not truth. Bank-level facts (`history_days`, `bank_charges_nsf_fee`, account type) MUST live in the businesses data, not in transactions.

#### Scenario: Required fields present
- Given all generated transactions and businesses
- When each record is checked against the PDF field list
- Then no required field is missing or null

#### Scenario: Credit is positive
- Given a deposit transaction
- When its amount is read
- Then the amount is greater than 0

### Requirement: Determinism
Generation MUST depend only on the seed (default 42): a local `random.Random(seed)`, a fixed start date, counter-based ids, sorted output, and amounts rounded to 2 decimals. It MUST NOT use the global RNG or the current date.

#### Scenario: Byte-identical output
- Given the same seed
- When generation runs twice
- Then every output file is byte-identical across runs

#### Scenario: Committed data matches regeneration
- Given the committed files in `data/`
- When regenerated with the default seed
- Then they equal the committed bytes

### Requirement: Ground truth
Ground truth MUST be keyed by transaction id with `{group, business, revenue, risk_signal, notes}` for every transaction. `risk_signal` MUST be derived from `group` by a shared function (null when the group carries no risk). `group` MUST be one of the 13 groups or `none`. `revenue` MUST be derived only by the shared `is_revenue` rule (see credit-features) and never hand-labeled.

#### Scenario: Truth covers all transactions
- Given transactions and ground truth
- When ids are compared
- Then the key sets are equal and every group is valid

#### Scenario: Truth revenue comes from the rule
- Given each ground-truth entry and its transaction
- When `is_revenue` is recomputed
- Then it equals the stored `revenue` value

### Requirement: Untrusted descriptions are data
Counterparty text MUST be treated as untrusted. At least one transaction in 1-2 businesses MUST carry an instruction-like description (e.g. telling a reviewer to label it revenue). It MUST be stored verbatim as a plain description string with no special handling.

#### Scenario: Instruction-like description stored as plain data
- Given a transaction whose description contains an instruction aimed at a reviewer
- When data is written and reloaded
- Then the description is preserved verbatim, its ground-truth group follows its real nature, and no field or code path acts on the instruction
