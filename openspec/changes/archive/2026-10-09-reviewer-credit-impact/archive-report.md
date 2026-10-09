# Archive report: reviewer-credit-impact

Archived 2026-10-09.

## Merged into main specs

| Capability | Type | Requirements | Scenarios |
|---|---|---|---|
| transaction-flagging | new | 6 | 6 |
| llm-review | new | 6 | 11 |
| review-cache | new | 5 | 5 |
| review-evaluation | new | 4 | 5 |
| credit-sensitivity | new | 3 | 5 |
| baseline-report | modified | "Report content and command" replaced; other 3 requirements and their 4 "Observed (seed 42)" lines unchanged | 14 total |

## Verification

`verify-report.md`: PASS WITH WARNINGS (0 critical). The three warnings were wording drift between spec and implemented definitions (`changed_share` denominator, residual-error set, ablation fields); specs were aligned in 7f1b3ce before archiving. No correctness or reproducibility bug. 72 of 72 tasks complete.

## Outcome

- Reviewer: r1 failed (payload design bug: business-level `bank_charges_nsf_fee` read as transaction evidence); r2 is the final evaluated version (only change: field removed, `PROMPT_VERSION` r2).
- Reviewer hypotheses r2: R1, R2, R8 passed; R3, R4, R5, R6 failed. Sensitivity hypotheses: S1–S3 passed; S4 failed.
- Remaining limitations: `active_advance` false positives amplified by the ×20 funder term, uncalibrated self-reported confidence (gate rarely binds: 4 of 620 kept), imperfect injection resistance (3 of 12 obeyed).
- Spend: $0.70 total for both runs.
