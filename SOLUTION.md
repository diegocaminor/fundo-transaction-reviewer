# Solution

Every number below is **measured** from committed artifacts (`data/*.json`, `data/runs/`, change logs in `openspec/changes/archive/`) unless marked as an *assumption* or *estimate*; `tests/test_docs_numbers.py` recomputes each one. Everything reproduces offline with `python3 -m fundo all`.

## 1. How each part was solved

**Data and baseline (prerequisite).** A seeded generator produces 10 Plaid-format businesses (2,000 transactions, 90 days; one with 61 days) with ground truth and a list of planted traps. The legacy keyword engine is ours (the challenge provides none): 13 ordered substring rules, no normalization, frozen before any data existed. It mislabels 254 of 2,000 transactions (12.7%). One bug was found rather than designed: the rule `nsf` matches inside "tra**nsf**er", so every savings sweep becomes an NSF and biz_08's daily Stripe payouts turn a healthy business into a decline.

**Part 1, reviewer.** Code-only rules flag 546 suspicious transactions (27%) and a seeded 5% random audit adds 74. `gpt-4.1-mini` reviews each one in a separate call and returns only `group`, `business`, `confidence` and `reason` under a strict JSON schema. A deterministic gate decides whether to accept a correction (section 4). Raw responses are committed as a cache.

**Part 2, credit impact.** Features and the offer are computed under truth, legacy and reviewed labels with the same functions. A Monte Carlo corrupts truth labels at 2/5/10% (200 seeded runs per rate) under two models: realistic confusions, including business/personal flips, and uniform random swaps. A truncation experiment cuts each 90-day business to its last 61 days.

**Part 3** is the one-page production strategy in section 8.

**Skipped, and why.** No few-shot examples or prompt iteration beyond one bug fix, to avoid fitting the prompt to our own synthetic traps. No confidence calibration, which needs labeled production data.

**Method.** Every prediction was committed before its measurement and kept verbatim. Failures are reported as results; data, rules and thresholds were never adjusted to pass.

## 2. Results

**Legacy baseline (6 of 10 predictions passed).** Most legacy errors push offers *up* (biz_04 +$22,200, +52%). biz_08 is a false decline (truth $39,230, legacy $0). In biz_09 two bugs cancel: the punctuation miss alone would approve $67,479 on a decline, and two phantom NSFs from the substring bug restore it. Legacy is right for the wrong reason.

**Reviewer, r1 vs r2** (same 7 predictions; primary variant with the Plaid category):

| Prediction | r1 | r2 | r2 measured |
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

Accuracy is secondary: the goal is the credit decision and dollar error. Per-business before/after revenue share, NSF and overdraft counts, high-risk debit share and offer (truth, legacy, reviewed) are in `data/review_report.json`.

**Sensitivity (3 of 4 predictions passed).** Realistic mislabels lower the mean offer by $938, $2,440 and $5,926 at 2, 5 and 10%. biz_09, at 6 NSF against a > 5 limit, is the only business whose decision flips at 2% (8% of runs). Random swaps flip decisions more often than realistic confusions (4.2% vs 1.9% of runs), mostly through implausible funder labels. S4 failed: 6 of 8 approved businesses lose ≥ 1% of their offer at 61 days.

**Flag coverage.** 100% of legacy errors were flagged, but this is an **optimistic upper bound**: the rules were written knowing the planted scenarios. The independent estimate is the audit: 0 errors in 74 sampled transactions, Wilson 95% upper bound 4.9%, i.e. up to ~72 misses among the 1,454 unflagged.

**Estimates and assumptions, not measurements.** The 0.70/0.85 confidence bars, the 1% materiality threshold and every prediction threshold are design choices fixed before running, not challenge requirements. Spend comes from token counts in the cache priced at the published `gpt-4.1-mini` rates: $0.70 for both runs. The synthetic data reflects our assumptions about bank descriptions, so absolute rates will not transfer to production.

## 3. Model and prompt choices, and the failed attempt

`gpt-4.1-mini`: cheap, non-reasoning, strict JSON schemas, temperature 0. One transaction per call keeps cache keys simple and stops one injected description from influencing others. The client uses only the standard library, so running needs no install. Descriptions are wrapped in `<<<UNTRUSTED>>>` markers and declared data, never instructions.

**r1 failed (5 of 7 predictions) because of our payload, not only the model.** The per-transaction payload included the business-level field `bank_charges_nsf_fee: true`. The model read it as evidence that each transaction was an NSF charge and declined 8 of 10 healthy businesses. The proof came before any r2 call: biz_02, the only business with the field false, got 0 wrong NSF proposals, while the other nine got 205, and 185 of those reasons mention "bank charges" or "NSF fee".

**r2 changed only that field** and the prompt version. Thresholds, rules, schema, gate, system prompt and predictions are identical, and r1 is kept next to r2. The prompt does **not** mention the "transfer → NSF" bug: that would coach the model on our own synthetic failure mode.

## 4. Code vs model boundary

The model **proposes**: group, business/personal, confidence and reason. Code **decides and computes** everything financial:

- Revenue is always recomputed from group and business; the model cannot set it.
- Features, offer and the NSF > 5 rule use the same functions for truth, legacy and reviewed labels.
- **The gate measures credit impact, not field changes.** Each correction is applied alone to the original legacy labels and the offer is recomputed. If it flips the decision, moves the offer by ≥ 1%, or changes NSF, overdraft or high-risk share, it needs confidence ≥ 0.85; otherwise 0.70. Judging against the original labels makes the result independent of review order (tested).
- Invalid or refused output gets one retry, then keeps the legacy label as `review_failed`.

The model judges meaning; arithmetic, thresholds and authority stay auditable.

## 5. Part 2 answers

**Zero NSF at a bank that charges no NSF fees** is *unobserved*, not clean: biz_02 has 0 NSF lines but 7 items paid into overdraft. We report `nsf_observable: false`, use overdrafts as the proxy and route the file to manual review, without changing the formula. Reading that zero as clean rewards exactly the accounts the threshold targets.

**61-day histories on a model built for 90 days.** Normalizing monthly revenue by `history_days / 30` fixes scale, not evidence. Cutting each 90-day business to 61 days lowered 6 of 8 approved offers by ≥ 1%, driven by infrequent deposits (biz_10 lost 35% of monthly revenue when its two largest deposits fell outside the window). Worse, **biz_09 flips from decline to approve** ($66,970) because its older NSFs drop out. A short history hides stress signals, so it should carry a low-history flag and a reviewed or reduced offer.

## 6. Limitations

- **Funder over-labeling.** The model labels ordinary financing debits (a truck lease, auto-loan payments) as `active_advance`. The formula subtracts 20 × daily funder payments, so one $3,100 lease payment removed $62,000 from biz_03's offer. This is the main reason total offer error rose.
- **Uncalibrated confidence.** 616 of 620 answers report ≥ 0.9, so the gate kept only 4 proposals and accepted 106 of 110 hard negatives. Self-reported confidence cannot be the filter; it needs calibration against labeled outcomes or a second signal.
- **Injection resistance is imperfect.** 3 of 12 injected instructions were obeyed (4 of 12 without the Plaid category), including a casino debit described as office supplies and an owner's personal credit claimed as business income.
- **Synthetic validity.** We wrote the traps, the legacy rules and the flag rules, and our Plaid category is derived from truth with 8% noise. With and without that field, accuracy on the 560 shared transactions was 0.823, but every rate here describes our own data.

## 7. Tools and AI assistance

AI-assisted development was used throughout the project. Claude Code was used for implementation, debugging, test execution, and repository changes. OpenSpec was used to structure planning and record design decisions. ChatGPT was used to review architecture choices, hypotheses, experimental methodology, and documentation. All measured results were produced by the committed code and reports; AI-generated suggestions were treated as proposals and verified before being incorporated.

OpenAI `gpt-4.1-mini` is the model under test, not a development tool.

## 8. Part 3: production strategy (one page)

One page, no code. It builds on what the evaluation measured: the reviewer gets every credit decision right on our data, but it over-labels funder debt, reports uncalibrated confidence and obeys some injected text.

### 8.1 Shadow deployment and gates to go live

Run the reviewer on every application next to the keyword engine while **decisions keep coming from the keyword engine**. For each application, store both label sets, the features, the offer and the decision under each, so every disagreement can be priced.

Promote in stages, each with its own gate:

1. **Suggest only.** Underwriters see the proposed correction, its 5-second reason and its credit impact (offer change, decision flip). Nothing is applied automatically.
2. **Auto-apply non-material corrections:** those that move no decision, no NSF/overdraft count and no high-risk share, and change the offer by less than 1%.
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
