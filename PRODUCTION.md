# Production strategy

One page, no code. It builds on what the evaluation measured: the reviewer gets every credit decision right on our data, but it over-labels funder debt, reports uncalibrated confidence and obeys some injected text (see `SOLUTION.md`).

## 1. Shadow deployment and gates to go live

Run the reviewer on every application next to the keyword engine while **decisions keep coming from the keyword engine**. For each application, store both label sets, the features, the offer and the decision under each, so every disagreement can be priced.

Promote in stages, each with its own gate:

1. **Suggest only.** Underwriters see the proposed correction, its 5-second reason and its credit impact (offer change, decision flip). Nothing is applied automatically.
2. **Auto-apply non-material corrections:** those that move no decision, no NSF/overdraft count and no high-risk share, and change the offer by less than 1%.
3. **Auto-apply material corrections per error type**, only for types with enough adjudicated history.

Gates are measured on underwriter-adjudicated cases, never on the model's own confidence: lower dollar error than the keyword engine; a low rate of accepted corrections that underwriters reject; no increase in approvals the underwriter would have declined; and a pass on the adversarial set. Funder-debt (`active_advance`) and business→personal corrections stay human-reviewed until their measured precision clears the gate, because one false funder label can erase most of an offer.

## 2. Detecting drift when the engine or the classifier changes

Version everything that can change a decision: keyword rules, flag rules, prompt, model id, gate thresholds and the offer formula. Before any new version goes live, replay a frozen golden set (adjudicated transactions plus the adversarial set) and compare decisions, dollar error and correction rates with the current version.

In production, track weekly by segment (bank, business type, history length):

- input mix: description patterns, new counterparties, Plaid categories, amounts;
- the keyword engine's label mix and the flag rate;
- the reviewer's correction rate per error type and its confidence distribution;
- the share of decisions that differ from the keyword engine;
- the random-audit miss rate with its confidence interval.

A shift beyond the replay baseline pauses further automation until reviewed.

## 3. Reproducing declined decisions after keywords change

Each decision writes an immutable record: a hash of the transactions used, the keyword-engine version and its labels, the flag-rule version, the model id and prompt version with the raw model responses, the thresholds, the features, the offer and the formula version. Replaying a decline from that record must rebuild it exactly offline, as this repository does from its committed cache. Keyword changes never rewrite old decisions; re-scoring an applicant creates a new, separately versioned decision.

## 4. Underwriter feedback loop

Every accepted, rejected or edited correction is stored as a labeled transaction with its error type and credit impact. That data is used to:

- calibrate confidence per error type, replacing self-reported confidence as the gate;
- measure precision and recall per error type (funder debt, personal spend);
- grow the golden set used to approve new versions;
- propose keyword-rule fixes upstream (the "transfer" → NSF collision is the template).

Feedback only covers flagged transactions, so it is biased toward what the rules already catch. The random audit continues as the unbiased estimate of what the flags miss.
