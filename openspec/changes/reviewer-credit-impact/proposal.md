# Proposal: Reviewer and Credit Impact

## Intent

Phase 1 showed that legacy mislabels move offers (biz_01/04/05 inflated, biz_08 false decline). This change adds an LLM reviewer that confirms or corrects legacy labels under code-enforced authority limits. It measures the reviewer against ground truth and quantifies how sensitive the offer is to mislabel rates (challenge Parts 1 and 2).

## Scope

### In Scope
- Code-only flagging plus a seeded 5% audit sample of unflagged txns
- OpenAI reviewer (one txn per call, strict schema) with acceptance policy and failure statuses
- Committed JSONL cache, spend tracking, offline reproduction
- Evaluation: accuracy, dollar error, hard negatives, per-business credit outcomes, error analysis, flag coverage
- PFC ablation (with vs without `personal_finance_category`)
- Adversarial injection set (`data/adversarial.json`), outside the 10-business data
- Mislabel sensitivity (2/5/10%), biz_02 zero-NSF and biz_03 61-day analyses
- `python -m fundo all` extended; runs from cache without a key

### Out of Scope
- Part 3 production strategy, README overhaul, SOLUTION.md → `production-delivery`
- Any change to the legacy engine, generator, offer formula or Phase 1 data

## Capabilities

### New Capabilities
- `transaction-flagging`: frozen code rules plus a seeded audit sample. Never reads truth or traps.
- `llm-review`: prompt, strict schema, validation, retry, credit-impact acceptance gate, statuses
- `review-cache`: sha256-keyed JSONL cache, fail-loud on miss without key, `--refresh`, spend estimate
- `review-evaluation`: metrics, PFC ablation, adversarial compliance, reviewer hypotheses
- `credit-sensitivity`: mislabel Monte Carlo, `nsf_observable`, overdraft proxy, truncation experiment

### Modified Capabilities
- `baseline-report`: `python -m fundo all` also runs review (from cache) and sensitivity. Baseline outputs stay byte-identical.

## Approach

- **Boundary.** The model returns only `group` (enum of 14), `business`, `confidence` and `reason`. Code recomputes `is_revenue`, risk signal, features and offer with the existing unchanged functions.
- **Client.** `gpt-4.1-mini` through stdlib `urllib` on Chat Completions, using strict `json_schema` and temperature 0. The key comes from `OPENAI_API_KEY`. The model constant is part of the cache key.
- **Cache key.** `sha256(model, prompt_version, system_prompt_sha, payload, attempt)`. Each PFC variant and the adversarial set get their own keys.
- **Invalid output.** Refusal, parse failure or enum violation triggers a limited retry. After that, the legacy label is kept with `review_failed`.
- **Acceptance gate (credit impact, symmetric).** For each proposed correction `c` on business `b`, let `L` be the legacy label set and `L' = L` with only `c` applied. Recompute features and offer for `b`. `c` is **credit-material** if any of these hold:
  1. the decision (`offer > 0`) differs between `L` and `L'`
  2. `offer(L) > 0` and `|offer(L') − offer(L)| ≥ 0.01 × offer(L)`. The 1% is the project's chosen materiality threshold, NOT a requirement of the challenge. It reuses the Phase 1 value, but the rule differs: Phase 1 checked a predicted direction against the truth offer, while this gate checks the absolute marginal change against the legacy offer. When `offer(L) = 0`, only a decision flip makes the offer condition material.
  3. the NSF count differs
  4. the overdraft count differs. The formula does not price overdrafts, and at no-fee banks they are the only observable stress signal, so this counts as material on its own.
  5. the high-risk debit share differs. The formula does not price high risk, so this counts as material on its own.

  The gate is symmetric: the same bar applies whether the correction raises or lowers the offer. Material corrections need confidence ≥ 0.85; all others need ≥ 0.70. Below the bar, the legacy label is kept with `kept_low_confidence`. Above it, the status is `corrected`. A model answer equal to legacy is `confirmed`. Marginal effects use `L`, not a running label set, so the result does not depend on order.
- **Injection.** A regex match records `injection_suspected` as a signal only. The defenses are the closed schema and restricted authority.
- **Part 2.** Corruption uses `round(p·n)` seeded by sha256 (not `hash()`), 200 reps, and two models: a confusion map fixed before running, and a uniform swap. Output is mean/p5/p95 of features and offer, plus decision-flip probability.

## Assumptions

- **Thresholds 0.70 and 0.85 are PRE-CHOSEN POLICY THRESHOLDS, not tuned values.** Like the Phase 1 1% materiality threshold, they MUST NOT be adjusted after results are seen.
- Flag rules are frozen before the first API call. Flag recall against truth is an evaluation metric only.
- The 5% audit sample stands in for production monitoring: it estimates residual error where no truth exists.
- PFC is a near-truth proxy (same template as truth, 8% noise). The ablation reports how much it inflates results.
- Model-reported confidence is uncalibrated.
- The biz_02 and biz_03 analyses add reported fields and warnings only. The formula does not change.

## Reviewer hypotheses

A dedicated task writes and commits the hypotheses before the first API call. They are kept verbatim and marked passed/failed in the report. pytest asserts measured results and invariants, never the hypotheses. No xfail. They are not written here.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `fundo/flagging.py`, `llm.py`, `reviewer.py`, `review_report.py`, `reviewer_hypotheses.py`, `sensitivity.py` | New | Reviewer and Part 2 |
| `fundo/cli.py` | Modified | `review`, `sensitivity`, `--refresh`, extended `all` |
| `data/llm_cache.jsonl`, `adversarial.json`, `reviewed_labels.json`, `review_report.json`, `sensitivity.json` | New | Committed outputs |
| `tests/` | New | Network-free tests with a fake client, plus a snapshot from the cache |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Errors outside the flagged set are never reviewed | Med | Audit sample and flag-coverage metric |
| PFC inflates accuracy | High | Ablation reported side by side |
| A prompt edit invalidates the cache | Med | Freeze the prompt and hypotheses first; `PROMPT_VERSION` |
| Several immaterial corrections add up to a material shift | Low | Per-business before/after offer reported; >40% changed triggers a human-review flag |
| Model or pricing changes | Low | Re-verify at build time; spend test < $10 |

## Rollback Plan

All modules are additive. Revert the `feat/reviewer-credit-impact` branch. Phase 1 code and data stay untouched, and that is enforced by the existing snapshot tests.

## Dependencies

- OpenAI API key, needed only to populate the cache. pytest (dev).

## Success Criteria

- [ ] `python -m fundo all` runs without a key from the committed cache, and two runs are byte-identical
- [ ] A test proves flagging never reads truth or traps
- [ ] Spend estimated from cached usage is < $10 (test)
- [ ] Every reviewer hypothesis is evaluated and its status is recorded in the report
- [ ] Accuracy, dollar error, hard negatives, per-business outcomes, PFC ablation delta and injection-compliance rate are reported
- [ ] Sensitivity outputs, `nsf_observable` and the truncation experiment are reported
- [ ] `python -m pytest` passes with no xfail

## Resolved Questions (2026-10-09)

- Gate direction: **symmetric** (user decision).
- Overdraft-count change: **credit-material**, requires 0.85 (user decision).
- The 1% offer-change rule stays documented as a chosen materiality threshold, not a challenge requirement (user decision).
- `data-baseline` is verified and archived before Phase 2 specs are written, so Phase 2 deltas target `openspec/specs/` (user decision).
- Mislabel sensitivity: the realistic corruption model includes business/personal flips as well as group changes; the rate is defined at the transaction level (one corruption per corrupted transaction) (user decision).
- Flagging-rule bias: the rules were written with knowledge of the planted scenarios, so offline coverage on this dataset is optimistic (upper bound). Rules stay unchanged. The random audit sample is the independent, production-style estimate of misses, reported with its sample size and a Wilson 95% interval because of its sampling variance (user decision).
