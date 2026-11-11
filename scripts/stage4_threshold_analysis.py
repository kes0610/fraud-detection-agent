"""
Stage 4: picks a flagging threshold using real dollar amounts from the test set.

The model gives every transaction a fraud PROBABILITY (0 to 1). The THRESHOLD is
the cutoff above which we actually flag a transaction for review/decline. A low
threshold flags almost everything (catches more fraud, but wrongly flags many
good customers too); a high threshold flags almost nothing (fewer false alarms,
but misses more fraud). There's no free lunch - picking a threshold means
picking a point on that tradeoff, and we do it here using dollars, not guesses.

ASSUMPTION, clearly labeled: we don't know the bank's real cost of wrongly
declining a good customer (lost margin on that sale, customer annoyance, risk
they don't come back). So FALSE_DECLINE_COST_ASSUMPTIONS below is a set of
illustrative guesses, each expressed as "cents lost per dollar of a legitimate
transaction we wrongly decline" - and we show how the recommended threshold
changes depending on which guess is right, rather than picking one number and
hiding that it's a guess.

We assume a caught fraud dollar is a FULLY avoided loss (the bank doesn't pay
it), which is standard for this kind of analysis but is itself a simplification
(recovery costs, chargebacks, investigation time aren't modeled here).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS_FILE = PROJECT_ROOT / "data" / "processed" / "test_predictions.parquet"
SWEEP_CSV = PROJECT_ROOT / "outputs" / "stage4_threshold_sweep.csv"
CHART_FILE = PROJECT_ROOT / "outputs" / "stage4_threshold_chart.png"
REPORT_FILE = PROJECT_ROOT / "outputs" / "stage4_threshold_report.md"

# ASSUMPTION: illustrative costs of wrongly declining $1 of a legitimate
# transaction (lost margin + customer-annoyance risk), as a fraction of that
# dollar. Not a real bank figure - swap in a real one if you have it.
FALSE_DECLINE_COST_ASSUMPTIONS = [0.02, 0.05, 0.10, 0.20]
DEFAULT_ASSUMPTION = 0.05  # used for the single headline recommendation

THRESHOLD_GRID = np.round(np.arange(0.01, 1.00, 0.01), 2)


def sweep_thresholds(df: pd.DataFrame) -> pd.DataFrame:
    fraud = df[df["isFraud"] == 1]
    legit = df[df["isFraud"] == 0]
    total_fraud_dollars = fraud["TransactionAmt"].sum()

    rows = []
    for t in THRESHOLD_GRID:
        flagged_fraud = fraud[fraud["xgb_fraud_probability"] >= t]
        flagged_legit = legit[legit["xgb_fraud_probability"] >= t]
        rows.append({
            "threshold": t,
            "fraud_dollars_caught": flagged_fraud["TransactionAmt"].sum(),
            "fraud_dollars_missed": total_fraud_dollars - flagged_fraud["TransactionAmt"].sum(),
            "fraud_count_caught": len(flagged_fraud),
            "fraud_count_missed": len(fraud) - len(flagged_fraud),
            "legit_dollars_wrongly_declined": flagged_legit["TransactionAmt"].sum(),
            "legit_count_wrongly_declined": len(flagged_legit),
        })
    return pd.DataFrame(rows)


def best_threshold_for_assumption(sweep: pd.DataFrame, cost_per_dollar: float) -> pd.Series:
    net_value = sweep["fraud_dollars_caught"] - cost_per_dollar * sweep["legit_dollars_wrongly_declined"]
    return sweep.loc[net_value.idxmax()]


def make_chart(sweep: pd.DataFrame, recommended: dict) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(sweep["threshold"], sweep["fraud_dollars_caught"], label="Fraud $ caught", color="#2E7D32")
    ax.plot(sweep["threshold"], sweep["legit_dollars_wrongly_declined"], label="Legit $ wrongly declined", color="#C62828")
    for assumption, row in recommended.items():
        ax.axvline(row["threshold"], linestyle="--", alpha=0.4)
        ax.annotate(f"{assumption:.0%} cost\nassumption\n(t={row['threshold']:.2f})",
                    xy=(row["threshold"], ax.get_ylim()[1] * 0.85), fontsize=7, ha="center")
    ax.set_xlabel("Flagging threshold (probability cutoff)")
    ax.set_ylabel("Dollars (test set, ~1 week of transactions)")
    ax.set_title("Dollar tradeoff by flagging threshold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHART_FILE, dpi=150)


def main() -> None:
    df = pd.read_parquet(PREDICTIONS_FILE)
    sweep = sweep_thresholds(df)
    sweep.to_csv(SWEEP_CSV, index=False)

    recommended = {a: best_threshold_for_assumption(sweep, a) for a in FALSE_DECLINE_COST_ASSUMPTIONS}
    make_chart(sweep, recommended)

    headline = recommended[DEFAULT_ASSUMPTION]

    report = ["# Stage 4 findings: picking a flagging threshold with dollars\n"]
    report.append(
        f"Analysis uses the {len(df):,} test-set transactions (the newest 25%, never used in "
        f"training) and the stronger model's (XGBoost) fraud probability for each one.\n"
    )
    report.append(
        "**Assumption, clearly labeled:** the cost of wrongly declining a legitimate "
        "customer isn't something this dataset tells us - it depends on the bank's real "
        "profit margins and how much a false decline damages the relationship. We don't "
        "have that number, so below we show the recommended threshold under several "
        "illustrative guesses (2%, 5%, 10%, 20% of the declined dollar amount), instead of "
        "quietly picking one.\n"
    )

    report.append("## How the recommended threshold changes with that assumption\n")
    report.append("| Cost assumption | Threshold | Fraud $ caught | Fraud $ missed | Legit $ wrongly declined | Legit transactions wrongly declined |")
    report.append("|---|---|---|---|---|---|")
    for a, row in recommended.items():
        report.append(
            f"| {a:.0%} of declined $ | {row['threshold']:.2f} | "
            f"${row['fraud_dollars_caught']:,.0f} | ${row['fraud_dollars_missed']:,.0f} | "
            f"${row['legit_dollars_wrongly_declined']:,.0f} | {row['legit_count_wrongly_declined']:,.0f} |"
        )
    report.append("")

    report.append(
        f"## Recommendation\n\n"
        f"Using the **5% cost assumption** (a middle-of-the-road guess: wrongly declining "
        f"$100 of good business costs the bank about $5 in lost margin and goodwill) as the "
        f"headline number, the recommended threshold is **{headline['threshold']:.2f}**.\n\n"
        f"At that threshold, on this one test period: catches **${headline['fraud_dollars_caught']:,.0f}** "
        f"of fraud ({headline['fraud_count_caught']:,.0f} transactions), misses "
        f"**${headline['fraud_dollars_missed']:,.0f}** ({headline['fraud_count_missed']:,.0f} transactions), "
        f"and wrongly declines **${headline['legit_dollars_wrongly_declined']:,.0f}** of legitimate "
        f"purchases ({headline['legit_count_wrongly_declined']:,.0f} transactions).\n\n"
        f"**This threshold is NOT fixed** - it should be revisited with the bank's real cost "
        f"figures, and the table above shows it would move if that assumption changes (a "
        f"higher assumed cost of false declines pushes the threshold up, flagging less).\n"
    )
    report.append(f"\nFull threshold-by-threshold numbers: `outputs/stage4_threshold_sweep.csv`. Chart: `outputs/stage4_threshold_chart.png`.\n")

    REPORT_FILE.write_text("\n".join(report))
    print(f"Saved report to {REPORT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Saved sweep CSV to {SWEEP_CSV.relative_to(PROJECT_ROOT)}")
    print(f"Saved chart to {CHART_FILE.relative_to(PROJECT_ROOT)}")
    print(f"\nHeadline recommendation (5% cost assumption): threshold = {headline['threshold']:.2f}")


if __name__ == "__main__":
    main()
