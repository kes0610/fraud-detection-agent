# Model Card: Card Transaction Fraud Classifier

A one-page summary of what this model is, how it was built and tested, and — just as
important — what it can't do and who needs to check its work before anyone relies on it.

## Model details

- **Type:** XGBoost binary classifier (gradient-boosted decision trees), predicting the
  probability that a card transaction is fraudulent.
- **Baseline compared against:** Logistic Regression with class weighting.
- **Built:** November 2026. An independent project, not a production system.
- **Inputs:** ~469 features derived from transaction, card, address, and device/identity
  columns (see `data_dictionary.md` for every column). Most are anonymized by the data
  provider (Vesta) — their individual real-world meaning is unknown.
- **Output:** a fraud probability (0-1) per transaction, flagged above a chosen threshold.

## Intended use

- **Primary intended use:** flag transactions for a human fraud analyst to review, and
  draft a supporting case note (also for human review) — never to autonomously decline or
  approve a transaction.
- **Primary intended users:** fraud operations analysts and the data science team
  maintaining the model.
- **Out of scope:** this model should not be used to make or automate any final decision
  about an account, a customer, or a transaction without a human in the loop. It was never
  evaluated on live transactions, non-US cardholders, or any population beyond this specific
  historical dataset.

## Training data

- IEEE-CIS Fraud Detection dataset (via Kaggle): 590,540 real, anonymized US card
  transactions, 3.5% confirmed fraud.
- Split by **time**, not randomly: trained on the oldest 75% of transactions, tested on the
  newest 25% — chosen specifically because a random split would leak future information
  into training (e.g. the same card appearing in both sets) and overstate real performance.
- Many features are anonymized; this project never guesses at what an individual anonymized
  column means, and says so explicitly wherever one is cited (e.g. in SHAP explanations).

## Evaluation

Evaluated on the held-out, chronologically later 25% of transactions (147,635 transactions)
— data the model never saw during training.

| Metric | Baseline (Logistic Regression) | This model (XGBoost) |
|---|---|---|
| PR-AUC | 0.1944 | **0.4999** |
| Precision @ 0.5 cutoff | 0.060 | 0.229 |
| Recall @ 0.5 cutoff | 0.798 | 0.707 |

Plain accuracy is deliberately never reported: with fraud at 3.5% of transactions, a model
that flags nothing at all would score 96.5% "accurate" while catching zero fraud.

**Chosen operating threshold:** 0.43 (under an illustrative 5%-of-amount cost assumption for
wrongly declining a legitimate transaction — see `RESULTS.md` for the full sensitivity
table across other assumptions). At this threshold: catches ~$616K of fraud dollars per
~$3.2M of legitimate dollars wrongly declined, on the test period evaluated.

## Known limitations and failure cases

- **Precision is low in absolute terms.** At the recommended threshold, roughly 1 in 4-5
  flagged transactions is actually fraud — most flags are false alarms a human must sort
  through. This is a real, structural cost of fraud being rare, not a bug.
- **The chosen threshold is highly sensitive to an unverified cost assumption** (the dollar
  cost of annoying/declining a good customer). This project used an illustrative 5%
  assumption; a real deployment must replace this with the bank's actual figures.
- **Most driving features are anonymized.** SHAP can show that a feature mattered and in
  which direction, but not *why* in business terms, for roughly 300 of the ~469 features.
- **The "same card" approximation used by the investigation agent is not exact** (see
  README) — it can both over-merge different cards and under-merge the same card.
- **The AI-drafted investigation notes are not reliable on their own, even after one round
  of fixing.** A 25-case audit found the AI agent initially skipped the model's actual top
  reasons in 60% of notes. A targeted prompt fix (always name the top driver) raised how
  often it named the *correct* driver (40% → 64%) but also introduced a new failure mode —
  confidently naming the *wrong* feature with a real-looking number attached — pushing the
  confirmed error rate to 44% (see `outputs/stage6_evaluation_report.md` for the full
  before/after). **Every AI-drafted note requires human review before any
  action is taken on it; this is a hard requirement, not a suggestion.**
- **Time-based evaluation reflects one slice of time only.** Fraud patterns change
  (concept drift); this evaluation does not establish how performance holds up months or
  years after training without retraining.
- **No fairness/disparate-impact analysis was performed** — this dataset doesn't include
  demographic fields, so this project cannot and does not claim the model treats any group
  of cardholders differently or fairly. This is a real gap, not an assumption of fairness.

## Sensitive data used

Several input columns are sensitive by nature: payment card details (`card1`-`card6`),
billing address/distance fields, purchaser/recipient email domains, and device/network
fingerprint data (`id_01`-`id_38`, `DeviceType`, `DeviceInfo`) — flagged individually in
`data_dictionary.md`. Access to this data, and to any investigation notes derived from it,
should be restricted to authorized fraud-operations and data-science personnel.

## Who should review this model's output

- **Every flagged transaction** requires human fraud-analyst review before any action
  (hold, decline, contact customer) — this model only flags and explains, it never decides.
- **Every AI-drafted case note** requires the same analyst's review against the underlying
  evidence before being trusted, given the error rate found in Stage 6's evaluation.
- **The data science team** should periodically re-evaluate PR-AUC/precision/recall on
  fresh data (recommended: monthly) to catch performance drift, and re-run the
  threshold/dollar analysis whenever the bank's real false-decline cost estimate changes.
