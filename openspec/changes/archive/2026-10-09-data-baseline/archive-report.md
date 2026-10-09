# Archive Report: data-baseline

**Archive Date**: 2026-10-09
**Change**: data-baseline
**Verdict**: PASS WITH WARNINGS (noted in verify-report; warnings resolved in commit 58c1dfb)

## Verification Status

From `verify-report.md`:
- Test execution: `pytest -q` passed 158 tests
- Manual run: `python3 -m fundo all` OK; 6/10 hypotheses passed (hypothesis scoreboard)
- Compliance: 29/31 scenarios compliant, 2 partial (by design; see below)
- Outcome: PASS WITH WARNINGS, 0 CRITICAL, 4 WARNING (all design/drift related), 2 SUGGESTION

**Critical note**: The verify report flagged design/proposal drift warnings (flat layout vs src/fundo, report shape differences, biz_02/09 trap table updates). All warnings were already resolved in commit 58c1dfb; proposal.md and design.md wording synchronized with actual implementation.

## Specs Synced to Main

All four delta specs (marked as new) were synced directly to main specs. No existing main specs existed, so the delta content becomes the canonical specification with the "(new)" designation removed.

| Domain | Status | Details |
|--------|--------|---------|
| synthetic-data | Created | 4 requirements, 8 scenarios. All Observed lines (none in this spec) preserved. |
| legacy-classifier | Created | 4 requirements, 6 scenarios. All Observed lines (none in this spec) preserved. |
| credit-features | Created | 5 requirements, 9 scenarios. Scenario "Hand-computed fixtures..." documents snapshot approach. All Observed lines (none in this spec) preserved. |
| baseline-report | Created | 4 requirements, 16 scenarios. **4 Observed (seed 42) lines preserved verbatim** (biz_02, biz_03, biz_09, biz_10 outcomes recorded). |

**Observed lines verification**: 
- Before sync: 4 Observed lines in delta spec
- After sync: 4 Observed lines in main spec
- Status: Verified preserved (no modifications)

## Tasks Status

All implementation tasks in `tasks.md` marked `[x]` (7 phases, 33 tasks, all complete).

- Phase 1–7 tasks all checked; no stale checkboxes.
- Phase 6.2 documents the decision to drop independent hand-computation of biz_01 in favor of snapshot testing (pragmatic for ~2000 txns).
- Phase 6.6 documents investigation of failed predictions (findings logged, not tuned).

## Archive Contents

Moved from `openspec/changes/data-baseline/` to `openspec/changes/archive/2026-10-09-data-baseline/`:

- `proposal.md` – scope, capabilities, approach, assumptions, per-business predictions (6/10 passed), prediction change log
- `design.md` – technical approach, module layout, data model, determinism, data flow
- `specs/` – 4 domain specs (synthetic-data, legacy-classifier, credit-features, baseline-report)
- `tasks.md` – 33 tasks across 7 phases (all complete)
- `verify-report.md` – compliance audit, task status, design drift warnings (resolved)
- `exploration.md` – initial concept exploration

## Hypothesis Scoreboard (Predictions)

| Business | Prediction | Observed (seed 42) | Status |
|---|---|---|---|
| biz_01 | Revenue up, funder payments down → offer higher | offer +12,100.01 (+21.4%) | PASSED |
| biz_02 | NSF same, offer unchanged | NSF legacy 2 vs truth 0 (collateral) | FAILED |
| biz_03 | Labels exact, offer 0 delta, 61-day avg monthly | 2 sweep mislabels, delta 0 held | FAILED |
| biz_04 | Revenue up, funder down → offer higher | offer +22,200.00 (+52.3%) | PASSED |
| biz_05 | Personal credits inflate revenue → offer higher | offer +6,215.80 (+13.4%) | PASSED |
| biz_06 | Lucky Dragon misflag → high-risk up, offer unchanged | high-risk +0.0039, delta 0 | PASSED |
| biz_07 | Punctuation miss → high-risk down, offer unchanged | high-risk -0.0308, delta 0 | PASSED |
| biz_08 | Substring bug → NSF threshold breach → false decline | NSF legacy 92 vs truth 0 | PASSED |
| biz_09 | Plain miss + sweep bug → both decline (bugs cancel) | NSF legacy 7 vs truth 6 | FAILED |
| biz_10 | Control, labels exact, offer 0 delta | 2 sweep mislabels, delta 0 held | FAILED |

**Score: 6/10 passed** — A healthy mix of passed and failed predictions surfaces real engine weaknesses (punctuation, substring matching, collateral mislabels via routine vocabulary) for the next change (reviewer-credit-impact) to address.

## Specs Now Source of Truth

The following main specs are now the authoritative specifications:
- `openspec/specs/synthetic-data/spec.md`
- `openspec/specs/legacy-classifier/spec.md`
- `openspec/specs/credit-features/spec.md`
- `openspec/specs/baseline-report/spec.md`

All four .gitkeep files and directory scaffolding remain in place for future specs. The baseline report Observed outcomes are hypothesis records (findings, not regressions) and remain part of the spec for audit trail and proposal change log traceability.

## SDD Cycle Closed

This change is complete. The data-baseline phase is archived with full traceability.
- Artifacts archived to: `openspec/changes/archive/2026-10-09-data-baseline/`
- Specs synced to: `openspec/specs/{domain}/spec.md` (4 new)
- Next change: `reviewer-credit-impact` (design in progress; uses these specs and the generated data as ground truth)
