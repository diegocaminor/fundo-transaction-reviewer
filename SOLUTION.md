# Solution

Every number is **measured** from committed artifacts unless marked as an *estimate*; `tests/test_docs_numbers.py` recomputes each one. Everything reproduces offline with `python3 -m fundo all`.

## 1. How each part was solved

**Data and baseline.** A seeded generator builds 10 Plaid-format businesses (2,000 transactions, 90 days; one with 61) with ground truth and a list of planted traps. The legacy keyword engine is ours (the challenge provides none): 13 ordered substring rules, frozen before any data existed. It mislabels 254 of 2,000 transactions (12.7%). One bug was found, not designed: `nsf` matches inside "tra**nsf**er", so savings sweeps become NSFs.

**Part 1.** Code-only rules flag 546 suspicious transactions (27%) and a seeded 5% random audit adds 74. `gpt-4.1-mini` reviews each in its own call and returns only `group`, `business`, `confidence` and `reason` under a strict JSON schema. A deterministic gate decides what to accept (section 4). Raw responses are committed as a cache.

**Part 2.** Features and offer are computed under truth, legacy and reviewed labels with the same functions. A Monte Carlo corrupts truth labels at 2, 5 and 10% (200 seeded runs each), with realistic confusions (including business/personal flips) and with uniform swaps. **Part 3** is section 8.

**Skipped:** few-shot examples and prompt iteration beyond one bug fix (to avoid fitting our own traps), and confidence calibration (needs labeled production data). Every prediction was committed before its measurement; failures are results, never tuned away.

## 2. Results

**Legacy baseline (6 of 10 predictions passed).** Most legacy errors push offers *up* (biz_04 +$22,200, +52%). biz_08 is a false decline (truth $39,230, legacy $0). In biz_09 two bugs cancel: the punctuation miss alone would approve $67,479 on a decline, and phantom NSFs restore it.

| Prediction (reviewer) | r1 | r2 | r2 measured |
|---|---|---|---|
| R1 Undo biz_08 false decline | FAILED | PASSED | approve |
| R2 Fix biz_09 NSF count | FAILED | PASSED | 6 (truth 6, legacy 7) |
| R3 Halve revenue $ error | FAILED | FAILED | $166,457 → $110,649 (−34%) |
| R4 Lower total offer error | FAILED | FAILED | $79,746 → $92,668 |
| R5 Gate rejects most hard negatives | FAILED | FAILED | 106 of 110 accepted |
| R6 ≤ 2 of 12 injections obeyed | PASSED | FAILED | 3 of 12 |
| R8 Invalid output rare | PASSED | PASSED | 0 of 620 |

| Outcome | Legacy | r1 | r2 |
|---|---|---|---|
| Correct approve/decline decisions | 9/10 | 2/10 | **10/10** |
| High-risk $ misclassified | $3,926 | $4,208 | **$0** |
| Group accuracy, flagged set | 0.55 | 0.55 | 0.81 |

Per-business before/after revenue share, NSF/overdraft counts, high-risk share and offer are in `data/review_report.json`.

**Sensitivity (3 of 4 predictions passed).** Realistic mislabels lower the mean offer by $938, $2,440 and $5,926 at 2, 5 and 10%. Only biz_09 (6 NSF, limit > 5) flips at 2% (8% of runs). Uniform swaps flip decisions more often (4.2% vs 1.9% of runs).

**Coverage.** 100% of legacy errors were flagged, an **optimistic upper bound** because the rules were written knowing the traps. The independent audit found 0 errors in 74 sampled transactions, Wilson 95% upper bound 4.9%: up to ~72 misses among the 1,454 unflagged.

***Estimates and choices, not measurements:*** the 0.70/0.85 bars, the 1% materiality and every prediction threshold were fixed before running. Spend ($0.70 for both runs) prices cached token counts at published rates. Rates describe our synthetic data, not production.

## 3. Which mislabels matter for credit

The offer is `1.2 × monthly revenue − 20 × daily funder payment`, zero above 5 NSFs. Derived from that formula for a 90-day history (checked in tests):

| Mislabel | Offer effect | Direction |
|---|---|---|
| $1 credit wrongly counted as revenue | **+$0.40** | over-lends |
| $1 debit wrongly counted as funder payment, no other funder | **−$20** | false decline or cut |
| One extra NSF | $0, then **−100%** past 5 | cliff |
| High-risk or overdraft errors | **$0** (unpriced) | hidden risk |

A dollar of false funder debt weighs 50 times a dollar of false revenue, which is why one $3,100 lease payment removed $62,000 from biz_03. The term is fragile both ways: because it averages payment days, a small false funder debit added to a business that already pays more per day lowers the average and *raises* the offer. Legacy errors mostly over-lend; the reviewer's residual error under-lends.

## 4. Model, prompt and the failed attempt

`gpt-4.1-mini` (cheap, strict JSON schema, temperature 0), one transaction per call so injected text stays isolated. Descriptions are wrapped in `<<<UNTRUSTED>>>` markers and declared data, never instructions.

**r1 failed because of our payload.** It carried the business-level field `bank_charges_nsf_fee: true`, which the model read as evidence that each transaction was an NSF charge, so it declined 8 of 10 healthy businesses. Proof, before any r2 call: biz_02, the only business with the field false, got 0 wrong NSF proposals, while the other nine got 205, and 185 of those reasons cited "bank charges" or "NSF fee". **r2 removed only that field**; thresholds, rules, schema, gate, prompt and predictions are identical, and r1 is kept. The prompt does **not** mention the "transfer → NSF" bug: that would coach the model on our own synthetic failure.

## 5. Code vs model boundary

The model proposes group, business/personal, confidence and reason. Code recomputes revenue, features, offer and the NSF rule with the same functions for every label set. The gate applies each correction alone to the original legacy labels: if it flips the decision, moves the offer ≥ 1%, or changes NSF, overdraft or high-risk share, it needs confidence ≥ 0.85, otherwise 0.70 (order-independent, tested). Invalid output gets one retry, then keeps the legacy label as `review_failed`. The model judges meaning; arithmetic and authority stay auditable.

## 6. Part 2 answers and limitations

**Zero NSF at a no-fee bank** is *unobserved*, not clean: biz_02 has 0 NSF lines but 7 items paid into overdraft. We report `nsf_observable: false`, use overdrafts as the proxy and route the file to review, without changing the formula.

**61-day histories.** Dividing by `history_days / 30` fixes scale, not evidence. Truncating each 90-day business lowered 6 of 8 approved offers by ≥ 1% (biz_10 lost 35% of monthly revenue when two large deposits fell outside the window), and **biz_09 flips from decline to approve** ($66,970) because its older NSFs drop out. Short histories hide stress signals and need a reviewed offer.

**Limitations.** Funder over-labeling (above). Confidence is uncalibrated: 616 of 620 answers report ≥ 0.9, so the gate kept only 4 proposals and accepted 106 of 110 hard negatives. Injection resistance is imperfect: 3 of 12 obeyed (4 of 12 without the Plaid category). Our Plaid category is derived from truth with 8% noise; with and without it, accuracy on the 560 shared transactions was 0.823.

## 7. Tools and AI assistance

AI-assisted development was used throughout the project. Claude Code was used for implementation, debugging, test execution, and repository changes. OpenSpec was used to structure planning and record design decisions. ChatGPT was used to review architecture choices, hypotheses, experimental methodology, and documentation. All measured results were produced by the committed code and reports; AI-generated suggestions were treated as proposals and verified before being incorporated.

OpenAI `gpt-4.1-mini` is the model under test, not a development tool.

## 8. Part 3: production strategy (one page)

It builds on what we measured: correct decisions on our data, but funder over-labeling, uncalibrated confidence and partial injection resistance.

### 8.1 Shadow deployment and gates to go live

Run the reviewer on every application while **decisions keep coming from the keyword engine**, storing both label sets with their features, offer and decision so every disagreement is priced.

Promote in stages, each with its own gate:

1. **Suggest only.** Underwriters see the correction, its 5-second reason and its credit impact; nothing is applied.
2. **Auto-apply non-material corrections** (no decision, NSF, overdraft or high-risk change; offer moves < 1%).
3. **Auto-apply material corrections per error type**, only for types with enough adjudicated history.

Gates are measured on underwriter-adjudicated cases, never on the model's own confidence: lower dollar error than the keyword engine; a low rate of accepted corrections that underwriters reject; no increase in approvals the underwriter would have declined; and a pass on the adversarial set. Funder-debt (`active_advance`) and business→personal corrections stay human-reviewed until their measured precision clears the gate, because one false funder label can erase most of an offer.

### 8.2 Detecting drift when the engine or the classifier changes

Version everything that can change a decision: keyword rules, flag rules, prompt, model id, gate thresholds and the offer formula. Before any new version goes live, replay a frozen golden set (adjudicated transactions plus the adversarial set) and compare decisions, dollar error and correction rates with the current version.

In production, track weekly by segment (bank, business type, history length):

- input mix: description patterns, new counterparties, Plaid categories, amounts;
- the keyword engine's label mix and the flag rate;
- the reviewer's correction rate per error type and its confidence distribution;
- the share of decisions that differ from the keyword engine;
- the random-audit miss rate with its confidence interval.

A shift beyond the replay baseline pauses further automation until reviewed.

### 8.3 Reproducing declined decisions after keywords change

Each decision writes an immutable record: a hash of the transactions used, the keyword-engine version and its labels, the flag-rule version, the model id and prompt version with the raw model responses, the thresholds, the features, the offer and the formula version. Replaying a decline from that record must rebuild it exactly offline, as this repository does from its committed cache. Keyword changes never rewrite old decisions; re-scoring an applicant creates a new, separately versioned decision.

### 8.4 Underwriter feedback loop

Every accepted, rejected or edited correction is stored as a labeled transaction with its error type and credit impact. That data is used to:

- calibrate confidence per error type, replacing self-reported confidence as the gate;
- measure precision and recall per error type (funder debt, personal spend);
- grow the golden set used to approve new versions;
- propose keyword-rule fixes upstream (the "transfer" → NSF collision is the template).

Feedback only covers flagged transactions, so it is biased toward what the rules already catch. The random audit continues as the unbiased estimate of what the flags miss.
