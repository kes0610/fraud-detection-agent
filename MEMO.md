**TO:** Head of Fraud Operations
**FROM:** Data & AI Team
**RE:** Fraud detection model — results, tradeoffs, and a rollout recommendation

## Summary

We built and tested a transaction fraud model and a prototype AI "investigation agent"
that drafts case notes for flagged transactions. The model clearly outperforms a simple
baseline. The AI agent does not yet meet the bar for unsupervised use. Below is what we
found, what it costs, and how we'd recommend rolling it out carefully.

## Results

Tested on transactions that happened *after* everything the model trained on (not a random
sample — this matters, see note below). The stronger model (XGBoost) more than doubled a
simple baseline's accuracy on catching fraud without drowning in false alarms (PR-AUC 0.50
vs. 0.19).

## The dollar tradeoff — and the one number we need from you

At our recommended flagging threshold, the model would have caught **~$616,000** of fraud
on this test period, while wrongly flagging **~16,800 legitimate transactions (~$3.2M)**
for review. That tradeoff point depends entirely on one number we had to guess:
**how much does it actually cost us when we wrongly decline a good customer's purchase?**
We used an illustrative 5% of the transaction amount (lost margin + goodwill). If the real
figure is lower, we should flag more aggressively (catch more fraud); if it's higher, we
should flag less. **We need your team's real number to set this correctly** — see
`RESULTS.md` for how the recommended threshold shifts across a range of assumptions.

## Risks

1. **False declines have a real cost.** Roughly 1 in 4-5 flagged transactions is actually
   fraud at our recommended threshold — most flags are false alarms. Analyst staffing and
   customer-communication processes need to account for that volume.
2. **The model will degrade over time without maintenance.** Fraud tactics change; a model
   trained on one period will quietly get worse on new ones. We recommend monthly
   performance re-checks and a defined retraining cadence, not a "set and forget" deployment.
3. **The AI-drafted case notes are not reliable without human review — and a quick fix
   didn't solve it.** In a 25-case audit, the AI agent frequently failed to explain the
   model's actual reasoning. We tried one targeted fix; it got better at naming a specific
   reason, but also got worse at making sure that reason was correct (confirmed error rate
   rose to roughly 2-in-5 notes). It must stay a drafting aid only — analysts need to check
   it against the underlying evidence every time,
   not treat it as a finished case file.
4. **This touches sensitive data.** Card details, billing/location info, and device/network
   fingerprints are all inputs. Access to the model's outputs and the agent's notes should
   be restricted to authorized fraud-ops and data-science staff, consistent with existing
   data-handling policy.
5. **We have not evaluated fairness.** This dataset has no demographic fields, so we cannot
   and do not claim the model treats any group of cardholders equitably. This should be
   assessed with appropriate data before any customer-facing rollout.

## Recommended rollout plan

1. **Shadow mode first (4-6 weeks):** run the model against live transactions without
   acting on it at all — just log its flags — to confirm real-world performance matches
   this evaluation before anything customer-facing happens.
2. **Pilot with holds, not auto-declines (4-6 weeks):** flagged transactions get queued for
   human review, never auto-declined. Track the real false-decline rate and fraud-catch
   rate against this report's numbers.
3. **Keep the investigation agent in draft-only mode throughout**, with mandatory analyst
   sign-off before any note is treated as case documentation — not relaxed at any stage
   until its accuracy is independently re-measured and materially improved.
4. **Revisit the threshold** once your team provides a real false-decline cost figure,
   using the sensitivity table in `RESULTS.md`.
5. **Set a recurring review cadence** (recommended: monthly metrics check, quarterly full
   retrain) rather than a one-time launch.

Full technical detail, every number's source, and known limitations are in `MODEL_CARD.md`
and `RESULTS.md`.
