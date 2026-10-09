# Proposal: Production and Delivery (lightweight)

## Intent

Write the two remaining deliverables: `SOLUTION.md` (2–3 pages) and the one-page production strategy (challenge Part 3). Documentation only: no code, data, model, prompt, threshold or formula changes. Lightweight process approved by the user: this proposal only, no separate specs, design or tasks.

## Scope

In: `SOLUTION.md`, `PRODUCTION.md`, README links and deliverable checkboxes.
Out: any behavioral change. r2 remains the final evaluated reviewer.

## Outline: SOLUTION.md (2–3 pages)

1. **Approach per part.** Part 1 (synthetic data, legacy baseline, reviewer), Part 2 (credit impact and sensitivity), Part 3 (pointer to PRODUCTION.md). What was skipped and why.
2. **Results.** Measured results vs estimates, kept visibly separate. Legacy baseline; reviewer r1 vs r2; sensitivity; hypothesis scoreboards including failures.
3. **Model and prompt choices, failed attempts.** gpt-4.1-mini, strict schema, one transaction per call, untrusted-text handling; r1 failure and the r2 fix; why the prompt was not coached on synthetic failure modes.
4. **Code vs model boundary.** What the model may change, what stays deterministic, and why.
5. **Part 2 answers.** Zero NSF at a no-fee bank; 61-day histories on a model calibrated for 90 days.
6. **Limitations.** active_advance false positives, uncalibrated self-reported confidence, injection resistance, optimistic flag coverage, synthetic-data validity.
7. **Tools and AI assistance disclosure.**

## Outline: PRODUCTION.md (one page, no code)

1. Shadow deployment alongside the keyword engine, and the gates for letting reviewer output affect live decisions.
2. Drift detection when the keyword engine or the classifier changes, or inputs shift.
3. Reproducibility of declined decisions after keywords change.
4. Underwriter feedback loop.

## Acceptance criteria

- [ ] Every challenge requirement for SOLUTION.md and Part 3 is covered (checked against the challenge text).
- [ ] Every quantitative claim is traceable to a committed artifact (`data/*.json`, `data/runs/*`, or the archived proposals' change logs) and is checked by a script before archiving.
- [ ] SOLUTION.md stays within 2–3 pages (target ≤ 1,500 words).
- [ ] PRODUCTION.md stays within one page (target ≤ 550 words) and contains no code.
- [ ] Measured results are clearly separated from assumptions and estimates.
- [ ] The main limitations and every failed hypothesis are disclosed, not hidden.

## Rollback

Documentation only: revert the commits.
