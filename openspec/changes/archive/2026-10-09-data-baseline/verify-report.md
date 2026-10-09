# Verify Report: data-baseline

Verdict: PASS WITH WARNINGS. 0 CRITICAL, 4 WARNING, 2 SUGGESTION.

## Execution
- `.venv/bin/python -m pytest -q`: 158 passed.
- `python3 -m fundo all` (repo root, no PYTHONPATH): ran OK, 6/10 hypotheses passed; `git status` unchanged (data/ and report byte-identical, no diff).
- Dataset: 2000 txns, 10 businesses, biz_03 history_days 61.

## Compliance (31 scenarios + requirement-level checks)
Totals: 29 COMPLIANT, 2 PARTIAL, 0 NON-COMPLIANT.

- synthetic-data: all COMPLIANT (composition, schema, determinism incl. committed-data test, ground truth, instruction-like text). Evidence: tests/test_generate.py, test_determinism.py, test_biz01.py, test_schema.py.
- legacy-classifier: all COMPLIANT (tests/test_legacy.py; rules frozen header in fundo/legacy.py).
- credit-features: all COMPLIANT except below.
  - PARTIAL: "Hand-computed biz_01" scenario. Replaced by snapshot + invariants (tasks 6.2, documented). Math is covered by inline hand-computed tests in test_features.py/test_offer.py but biz_01 expected values are not independently hand-computed.
- baseline-report:
  - One command, deterministic: COMPLIANT (test_cli.py subprocess twice; manual rerun clean).
  - Per-business predictions: COMPLIANT. Spec says "evaluated ... status recorded in `hypotheses`"; report has top-level `hypotheses` list (business_id, prediction, status, observed); text unchanged; tests check check functions on synthetic entries (tests/test_hypotheses.py). Result 6 passed (01,04,05,06,07,08), 4 failed (02,03,09,10) with observations recorded. Scenario Then-clauses for biz_02/03/09/10 are not met by the data, which the requirement explicitly allows (failed = finding).
  - Collateral mislabels: COMPLIANT (traps.json, per-business `mislabels`, `collateral_flips_decision`, routine vocabulary unfiltered). Observed: no business flagged as flipped by collateral alone vs truth in table.
  - Collateral changes outcome: COMPLIANT (fundo/report.py:102 `collateral_changes_outcome`; table column "changes outcome"; biz_09 flagged TRUE, matching scenario).
  - PARTIAL: Scenario wording for biz_02/03/09/10 reads as hard expectations while the requirement says hypotheses; spec scenarios were not updated to show observed outcomes.

## Tasks
All tasks in tasks.md are [x]; 6.2 documents the dropped hand-computed biz_01 task; 6.6 documents failed predictions.

## Design drift
- WARNING: proposal.md (Approach, Affected Areas) still says `src/fundo/`; actual and design/tasks say flat `fundo/`. Flat deviation is documented in design.md and tasks 1.1, not in the proposal.
- WARNING: design.md report shape says `businesses: [ {...} ]` list with `seed`; actual is `{"businesses": {biz_id: {...}}, "hypotheses": [...]}` (dict keyed by id, plus extra keys: collateral_*, decision, mislabels, planned_only, collateral_only). Check: no `seed` top-level key. Design not updated.
- WARNING: design.md biz_02/09 trap table and Legacy predictions describe pre-measurement expectations (biz_09 "5+1"); biz_09 now also has 2 sweep lines (documented in proposal change log), design not updated.
- SUGGESTION: design Testing Strategy/"biz_01 hand-computed" language vs actual snapshot approach.
- SUGGESTION: generate.py uses `random.Random(business_seed(...))` per business (local RNG, compliant; design says one `Random(seed)`).

## Risks
No CRITICAL issues. Recommended next: sdd-archive (optionally sync proposal/design wording first).
