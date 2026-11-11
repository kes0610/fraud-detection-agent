# Picking a flagging threshold with dollars

Analysis uses the 147,635 test-set transactions (the newest 25%, never used in training) and the stronger model's (XGBoost) fraud probability for each one.

**Assumption, clearly labeled:** the cost of wrongly declining a legitimate customer isn't something this dataset tells us - it depends on the bank's real profit margins and how much a false decline damages the relationship. We don't have that number, so below we show the recommended threshold under several illustrative guesses (2%, 5%, 10%, 20% of the declined dollar amount), instead of quietly picking one.

## How the recommended threshold changes with that assumption

| Cost assumption | Threshold | Fraud $ caught | Fraud $ missed | Legit $ wrongly declined | Legit transactions wrongly declined |
|---|---|---|---|---|---|
| 2% of declined $ | 0.27 | $712,758 | $78,285 | $6,646,028 | 35,283 |
| 5% of declined $ | 0.43 | $615,681 | $175,362 | $3,214,782 | 16,836 |
| 10% of declined $ | 0.60 | $497,187 | $293,857 | $1,533,712 | 7,416 |
| 20% of declined $ | 0.72 | $380,352 | $410,692 | $693,636 | 3,475 |

## Recommendation

Using the **5% cost assumption** (a middle-of-the-road guess: wrongly declining $100 of good business costs the bank about $5 in lost margin and goodwill) as the headline number, the recommended threshold is **0.43**.

At that threshold, on this one test period: catches **$615,681** of fraud (3,872 transactions), misses **$175,362** (1,228 transactions), and wrongly declines **$3,214,782** of legitimate purchases (16,836 transactions).

**This threshold is NOT fixed** - it should be revisited with the bank's real cost figures, and the table above shows it would move if that assumption changes (a higher assumed cost of false declines pushes the threshold up, flagging less).


Full threshold-by-threshold numbers: `outputs/stage4_threshold_sweep.csv`. Chart: `outputs/stage4_threshold_chart.png`.
