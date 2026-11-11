# Results

Real numbers from the actual runs, recorded here as they're produced (no placeholders -
this file is the source of truth for every number cited in the model card and memo). Full
detail and methodology for each is in `outputs/`.

## Dataset (Stage 1-2)

- 590,540 transactions, 3.5% fraud (20,663 fraudulent)
- 24.4% of transactions have identity/device info attached
- Data quality: 0 duplicate TransactionIDs, 0 fully-duplicate rows, 0 invalid amounts, 0
  unexpected category values, 0 join problems
- 214 of 434 columns are 50-99% missing (0 columns fully empty)

## Model performance (Stage 3), time-based split (75% train / 25% test)

| Model | PR-AUC | Precision @ 0.5 | Recall @ 0.5 |
|---|---|---|---|
| Baseline: Logistic Regression (class weighting) | 0.1944 | 0.060 | 0.807 |
| Stronger model: XGBoost (scale_pos_weight) | **0.4999** | 0.229 | 0.711 |

XGBoost improves PR-AUC by +0.3055 over the baseline (more than 2.5x). (Re-run once, after
Stage 6's encoder-persistence work - XGBoost has minor run-to-run noise from multi-threaded
training; these numbers match the model file currently saved in `models/`.)

## Threshold selection (Stage 4), using test-set dollars

| False-decline cost assumption | Threshold | Fraud $ caught | Fraud $ missed | Legit $ wrongly declined |
|---|---|---|---|---|
| 2% | 0.27 | $712,758 | $78,285 | $6,646,028 |
| **5% (headline)** | **0.43** | **$615,681** | **$175,362** | **$3,214,782** |
| 10% | 0.60 | $497,187 | $293,857 | $1,533,712 |
| 20% | 0.72 | $380,352 | $410,692 | $693,636 |

At the headline (5% assumption) threshold of 0.43: **$615,681 of fraud dollars caught per
$3,214,782 of legitimate dollars wrongly declined** - roughly $0.19 of fraud caught per $1
of legitimate business wrongly declined, on this one test period. 16,836 of 147,635 test
transactions (11.4%) are flagged at this threshold.

*(Note: Stage 4 was re-run once after a later encoder-persistence change required
retraining the model - XGBoost has minor run-to-run noise, so this threshold shifted from
0.45 to 0.43. Stages 5-6 below were analyzed at the original 0.45 and were not re-run, since
the shift is within normal noise and doesn't change any finding - see
`outputs/stage6_evaluation_report.md` for that detail.)*

## Investigation agent evaluation (Stage 6), n=25 sampled flagged transactions

Same 25 transactions evaluated twice: v1 (original prompt) and v2 (one targeted fix —
always name the top SHAP driver explicitly — after v1 showed 60% of notes omitted the
model's actual reasoning).

| | Named the real top driver | Unsupported/incorrect claims (confirmed) | Reasonable next step |
|---|---|---|---|
| Template baseline (no AI) | 25/25 (100%) | 0/25 (0%) | 25/25 (100%)* |
| AI agent v1 | 10/25 (40%) | 5/25 (20%, lower bound) | 25/25 (100%)* |
| AI agent v2 (after the fix) | 16/25 (64%) | **11/25 (44%, lower bound)** | 25/25 (100%)* |

\* Both baselines' "next step" was non-differentiated across nearly all 25 cases - see
`outputs/stage6_evaluation_report.md` for the full honest discussion.

**Bottom line, and it's a genuinely interesting one:** the fix improved how often the agent
named the *correct* driver (40% → 64%), but it also introduced a new failure mode — the
agent would sometimes name the *wrong* feature with real-looking confidence and a plausible
number attached, which is arguably worse than v1's vague omissions. The template baseline
remains more reliable than either AI version, at zero risk of fabrication. Full analysis
with specific before/after examples is in `outputs/stage6_evaluation_report.md`; v1's
original (unmodified) report is preserved at `outputs/stage6_evaluation_report_v1.md`.
