# Verify Report: reviewer-credit-impact

Verdict: PASS WITH WARNINGS. CRITICAL 0, WARNING 3, SUGGESTION 3.

## Execution
- `.venv/bin/python -m pytest -q`: 269 passed.
- `env -u OPENAI_API_KEY python3 -m fundo all` (twice): exit 0; `git status --short` shows only the pre-existing untracked PDF, so all tracked outputs (baseline_report, reviewed_labels, review_report, sensitivity, runs/r1_*) reproduce byte-identically from the committed cache without a key.
- Hypotheses (evaluated and recorded, not required to pass): R1 pass, R2 pass, R3 fail (legacy $166,456.67 vs reviewed $110,648.61, more than 50% remains), R4 fail (79,746 -> 92,668), R5 fail (106 of 110 hard negatives accepted), R6 fail (3 of 12 obeyed), R8 pass (0 of 620). S1 pass, S2 pass, S3 pass, S4 fail (6/8 approved 90-day businesses lose at least 1% offer; 0 approve->decline flips). Cached spend $0.6996 (< $10).
- tasks.md: all 72 items are [x]; none unchecked.

## Requirement and scenario matrix
transaction-flagging
- Inputs exclude truth and traps: COMPLIANT. `fundo/flagging.py` takes only txns and legacy; sentinel and static tests in tests/test_flagging.py. Also verified by rg: no truth/traps reference in flagging.py, reviewer.py, llm.py (only a docstring).
- Frozen rules / reproducible: COMPLIANT. `FLAG_RULES_VERSION = "f1"`, deterministic; determinism test.
- Seeded audit sample: COMPLIANT. sha256 ranking, per-business round(0.05 n), never flagged. Measured 74 vs round(0.05*1454)=73 (within +-1).
- Coverage measured offline: PARTIAL. `legacy_error_recall` exists, but `residual_legacy_errors_unreviewed` = errors outside flagged AND outside audit, not "missed outside the flagged set" (value is 0 either way). See W2.
- Known flagging-rule bias: COMPLIANT. `COVERAGE_NOTE` in review_report.py, shown next to the audit block.
- Audit estimate with variance: COMPLIANT. `wilson()`; 0/74, 95% upper bound 0.0494 (no_pfc 0/76, 0.0481); estimated misses reported as a range (0..72).

llm-review
- Closed schema: COMPLIANT. `SCHEMA` additionalProperties false, 14-value enum; `validate()` rejects extra keys, bad enum, out-of-range confidence (never clamped).
- Code recomputes derived fields: COMPLIANT. `_label()` uses `is_revenue` and `risk_signal_for`; model output never supplies them.
- Description untrusted: COMPLIANT. Delimiters stripped from input and wrapped, `INJECTION_RE` only sets `injection_suspected`; test_injection_is_only_a_signal.
- Invalid output handling: COMPLIANT. Two attempts (new key per attempt), then legacy label with `review_failed`; test_persistent_failure_keeps_legacy_as_review_failed.
- Statuses: COMPLIANT. confirmed/corrected/kept_low_confidence/review_failed (+ not_reviewed outside the set); partition test and test_status_counts_partition_the_reviewed_set.
- Gate: COMPLIANT. `is_material` compares L vs L with only c applied; decision flip, `|d| >= 0.01*offer(L)` only when offer(L)>0, tuple (NSF, overdraft, high-risk share) inequality; bars 0.85 / 0.70, symmetric, uses original legacy for every correction. Scenarios decision flip, 1% boundary, counts/share, symmetry, order independence, constants all covered in tests/test_reviewer.py.

review-cache
- Cache key: COMPLIANT. sha256 over model, prompt_version, system_prompt_sha, payload, attempt, variant (variant is an addition that guarantees PFC/adversarial separation).
- Hit without key: COMPLIANT. Full `all` run without key succeeded.
- Loud miss: COMPLIANT. Exit 3, message "At least N cache misses {per-variant}". Wording is a lower bound (attempt-0 only). See S1.
- Append and flush before use: COMPLIANT. `append_record` flush+fsync before return; test_crash_after_call_keeps_the_record; `--refresh` tested.
- Spend estimate: COMPLIANT. `estimate_spend` over all cache lines, including superseded r1; test_total_spend_including_superseded_runs_is_under_budget.

review-evaluation
- Report content: COMPLIANT. Dollar error (revenue and high-risk), business offer error, hard negatives proposed/accepted, per-business truth/legacy/reviewed, error analysis, flag coverage, status counts with review_failed, accuracy flagged and audit.
- Many changes human-review flag: PARTIAL. Denominator is reviewed transactions (`changed_share = corrected / reviewed`), not all business transactions. See W1.
- PFC ablation: PARTIAL. Both variants under separate keys and accuracy delta reported; dollar error is shown per variant but no explicit dollar-error delta field. See W3.
- Adversarial compliance: COMPLIANT. 12 cases, adv_pfc 3 obeyed (0.25), adv_no_pfc 4 (0.3333), in memory only.
- Reviewer hypotheses: COMPLIANT (with user override). R1-R6,R8 evaluated and recorded, failures do not fail the suite, no xfail; R7 removed and PFC ablation descriptive per user decision.

credit-sensitivity
- Mislabel Monte Carlo: COMPLIANT. 3 rates x 2 models x 200 reps, sha256 seeds, round(p n) one corruption each, flip_business plus group changes in confusion, group only in uniform, counts of group_change vs business_flip, mean/p5/p95 and `decision_flip_prob`. Grid/determinism and flip-probability covered in tests/test_sensitivity.py.
- NSF observability: COMPLIANT. biz_02 `nsf_observable` false, overdraft_count 7 reported; formula unchanged.
- Truncation: COMPLIANT. 9 businesses (90-day only) compared with their own 90-day values; biz_03 excluded and carries the low-history warning with NSF x 90/history.

baseline-report (MODIFIED)
- Report content and command: COMPLIANT. `all` writes the three new files, works without key, deterministic. Phase 1 outputs byte-identical (git clean). Cache incomplete: COMPLIANT (exit 3, test_all_with_incomplete_cache_exits_3_with_miss_count). Exit code 3 is the user-approved override of "nonzero".

## Findings
WARNING
- W1: human-review denominator (reviewed, not all business transactions). 7 of 10 businesses flagged under pfc. Spec text "41% of transactions" is ambiguous; clarify spec or code. Not a correctness bug.
- W2: `residual_legacy_errors_unreviewed` excludes audit-sampled errors; spec asks for mislabels missed outside the flagged set. Naming/definition drift; value is 0 either way.
- W3: ablation lacks an explicit dollar-error delta (derivable: revenue $100,872.82 pfc vs $120,585.06 no_pfc over 560 shared txns).
SUGGESTION
- S1: miss message says "At least N" because only attempt-0 requests are counted; document in spec.
- S2: design.md still names `CachedClient` (lines 15, 27) and R7 in the hypothesis list context; Implementation notes already record the override, but the table is stale.
- S3: results note for archive: the gate rarely binds (4 kept_low_confidence of 620 under pfc; 106/110 hard negatives accepted), and R3/R4/R5/R6/S4 failed. These are recorded outcomes, not defects.

## Correctness / reproducibility
No real correctness or reproducibility bug found. Truth is read only in review_report.py (evaluation) and sensitivity (by design). Revenue always recomputed via `is_revenue`. Cache key includes variant. Truncation uses the nine 90-day businesses. All findings above are documentation or definition drift.

Next recommended: sdd-archive.
