# Tasks: Data Baseline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,400 code/tests + ~2k-row generated JSON |
| 400-line budget risk | High |
| Chained PRs recommended | No (single branch, one commit per group) |
| Suggested split | One reviewable commit per Phase |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: High

Generated `data/` is the bulk of lines (Phase 7 only). Code and tests per phase stay under ~400 lines.

Conventions: RED (test) -> GREEN (impl) -> REFACTOR inside each phase. Specs: SD = synthetic-data, LC = legacy-classifier, CF = credit-features, BR = baseline-report.

## Phase 1: Setup (commit: `chore: add pytest project scaffold`)

- [x] 1.1 Create `pyproject.toml` (flat layout, `pythonpath=["."]`, pytest dev extra); `.gitignore` already exists.
- [x] 1.2 Create `fundo/__init__.py`, `tests/__init__.py`, one smoke test; run `python -m pytest`.
- [x] 1.3 Edit `openspec/config.yaml`: `strict_tdd: true`, `rules.apply.tdd: true`, testing runner `pytest (installed)`, layers unit/integration.

## Phase 2: Schema and shared rules (commit: `feat: add schema, revenue and risk rules`)

- [x] 2.1 RED `tests/test_schema.py`: `is_revenue` three scenarios, all 13 groups exclude revenue (CF Single revenue rule); `risk_signal_for` mapping.
- [x] 2.2 GREEN `fundo/schema.py`: `GROUPS` (13 + `none`), display map, TypedDicts, sign-convention docstring, `is_revenue`, `risk_signal_for`.
- [x] 2.3 Add record validators (required fields non-null, credit > 0, valid group) with tests (SD Schema completeness, Truth covers all).

## Phase 3: Legacy engine (commit: `feat: add frozen legacy keyword engine`)

Must be complete and committed BEFORE any trap data exists (anti-overfitting).

- [x] 3.1 RED `tests/test_legacy.py`: earlier rule wins, no match -> `none`, "N.S.F. FEE" -> `none`, `lucky` false positive, `transfer` breadth, no normalization (LC all scenarios except same-shape/biz_06 data).
- [x] 3.2 GREEN `fundo/legacy.py`: `RULES` in design order, `classify(txn) -> Label`; `business=True`, revenue/risk via shared functions.
- [x] 3.3 Test: label shape equals truth shape; personal credit with group `none` -> `business` true, `revenue` true (LC Same shape, Business defaults).
- [x] 3.4 Freeze: add header comment "rules frozen before trap data; do not tune to data".

## Phase 4: Features and offer (commit: `feat: add features and offer`)

- [ ] 4.1 RED `tests/test_features.py` (inline hand-computed): 6100.00 / 61 days -> 3000.00; funder 100 / (100+50) / none -> 125.00; no funder -> 0; overdraft-only -> NSF 0 (CF Monthly, Daily funder, Overdraft separate).
- [ ] 4.2 RED `tests/test_offer.py`: NSF 5 -> 10000.00, NSF 6 -> 0; floor at 0 (1000 vs 3000); overdraft 10 not capped (CF Offer scenarios).
- [ ] 4.3 GREEN `fundo/features.py`: `compute_features(txns, labels, business)`; rounding 2 dp money, 4 dp ratios; per-day sum then mean over funder-debit days.
- [ ] 4.4 GREEN `fundo/offer.py`: `compute_offer(features)`.
- [ ] 4.5 Test: same function on two label sets differs only by labels (CF Features from any label set).

## Phase 5: Generator (commit: `feat: add seeded generator and archetypes`)

- [ ] 5.1 RED `tests/test_biz01.py`: card processor deposits, internal transfer credit, Square Capital repay vs Square revenue, NSF fee, high-risk debit, hard negative, instruction-like text all present; description preserved verbatim after reload (SD biz_01 traps, Instruction-like).
- [ ] 5.2 GREEN `fundo/casa_norte.py`: ~18 hand-written trap lines with truth labels.
- [ ] 5.3 RED `tests/test_determinism.py`: two `generate` runs into `tmp_path` byte-identical; 10 businesses, `biz_03` history 61 (SD Business set, Byte-identical).
- [ ] 5.4 RED `tests/test_generate.py`: generator writes `data/traps.json` (txn id → trap name) covering every planted trap; routine descriptions are NOT filtered for legacy keywords (see proposal "Routine data policy").
- [ ] 5.5 GREEN `fundo/generate.py`: `Archetype`/`LineSpec`, local `Random(seed)`, `END_DATE`, integer cents, sort then counter ids, `sort_keys` JSON; biz_01 routine background (90 days).
- [ ] 5.6 Add archetypes biz_02-biz_06 per design trap table (routine vocabulary realistic for the business type, not keyword-filtered).
- [ ] 5.7 Add archetypes biz_07-biz_10 (biz_09: 5 `NSF RETURN ITEM FEE` + 1 `N.S.F.`; biz_10 routine only).
- [ ] 5.8 Extend `tests/test_schema.py`: truth `revenue == is_revenue(...)` for all rows, key sets equal, ~2000 txns (SD Truth scenarios).

## Phase 6: Report and CLI (commit: `feat: add baseline report and CLI`)

- [ ] 6.1 RED `tests/test_predictions.py`: parametrized biz_01..biz_10 per BR scenarios (|delta| > 1% materiality threshold for direction, biz_03 and biz_10 exact equality, biz_09 NSF 5/6, biz_02 NSF 0/0).
- [ ] 6.2 RED biz_01 hand-computed expected features/offer from truth (CF Hand-computed biz_01), values derived independently of the engine.
- [ ] 6.3 GREEN `fundo/report.py`: accuracy, truth/legacy/delta features and offer, collateral mislabel count per business and decision-flip flag (BR Collateral mislabels), `baseline_report.json`, stdout table.
- [ ] 6.4 GREEN `fundo/cli.py`, `__main__.py`: `all`/`generate`/`report`, `--seed 42`, `--out data/`.
- [ ] 6.5 Test: `python -m fundo all` run as a subprocess from the repo root (no install, no PYTHONPATH), twice into `tmp_path`, byte-identical (BR One command).
- [ ] 6.6 If a prediction fails, investigate data/engine; never loosen criteria (log justification in proposal if changed).

## Phase 7: Data and docs (commit: `docs: commit baseline data and update README`)

- [ ] 7.1 Run `python -m fundo all`; commit `data/*.json`.
- [ ] 7.2 Test: committed `data/` equals regeneration (SD Committed data matches).
- [ ] 7.3 Update `README.md` Running section (`python -m fundo all`, `python -m pytest`, sign convention note).
- [ ] 7.4 Full `python -m pytest` green.
