# baseline-report Delta

## MODIFIED Requirements

### Requirement: Report content and command
`python -m fundo all` MUST generate data, classify, and write `data/baseline_report.json`, print a table, AND ALSO run the review from the committed cache and the sensitivity analysis, writing `data/reviewed_labels.json`, `data/review_report.json` and `data/sensitivity.json`. For each business the baseline report MUST include label accuracy, the features and offer under truth and under legacy, and their deltas. Output MUST be deterministic (sorted keys). All outputs, including pre-existing Phase 1 outputs, MUST be byte-identical across runs and with the same cache and seed, and `all` MUST succeed without `OPENAI_API_KEY`. Phase 1 outputs MUST remain byte-identical to their pre-change content.

(Previously: `all` covered only data, classify and baseline report.)

#### Scenario: One command, deterministic, offline
- Given a clean checkout with the committed cache and no API key
- When `python -m fundo all` runs twice
- Then all outputs, including the three new files, are byte-identical across runs and `baseline_report.json` equals its Phase 1 content

#### Scenario: Cache incomplete
- Given a cache missing required entries and no key
- When `python -m fundo all` runs
- Then it exits nonzero reporting the miss count
