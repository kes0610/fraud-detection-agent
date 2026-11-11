"""
Stage 5: explains individual flagged transactions using SHAP.

SHAP (SHapley Additive exPlanations) answers: "for THIS ONE transaction, which
features pushed the model's fraud score up, which pushed it down, and by how
much?" It does this by comparing the model's prediction to what it would have
predicted if each feature were "unknown," averaged over many such comparisons
(the math behind that is from game theory - splitting credit for an outcome
fairly among contributors - but the plain-English reading is simple: every
feature gets a signed number for one transaction; positive numbers pushed the
score toward "fraud," negative numbers pushed it toward "not fraud," and
bigger numbers (positive or negative) mattered more for that one transaction).

Important honesty note: these SHAP numbers are in the model's internal
"log-odds" scoring units, not literal percentage points of probability - we
read them for DIRECTION and RELATIVE SIZE within one transaction (what mattered
most, and which way), not as an exact probability-point number.

We only compute SHAP for FLAGGED transactions (at Stage 4's recommended
threshold, 0.45) - those are the ones an analyst, or Stage 6's investigation
agent, would actually need an explanation for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_data_dictionary import FAMILY_DESCRIPTIONS, NAMED_COLUMNS, family_for  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "stage5_shap_findings.md"
IMPORTANCE_CHART = PROJECT_ROOT / "outputs" / "stage5_shap_importance.png"

THRESHOLD = 0.45  # Stage 4's recommendation under the 5% cost assumption
N_EXAMPLES_CAUGHT = 3   # correctly-flagged fraud, to showcase
N_EXAMPLES_FALSE_POSITIVE = 2  # flagged-but-actually-legit, to showcase honestly
TOP_K_REASONS = 5


def describe_feature(feature_name: str, low_card_cols: list[str]) -> tuple[str, str]:
    """Returns (human_label, plain_english_meaning) for an encoded feature name."""
    for col in low_card_cols:
        prefix = col + "_"
        if feature_name.startswith(prefix):
            category = feature_name[len(prefix):]
            base_meaning = NAMED_COLUMNS.get(col, (None,))[0] or FAMILY_DESCRIPTIONS.get(family_for(col) or "", (None,))[0]
            category_label = "missing/unknown" if category == "nan" else category
            return f"{col} = {category_label}", (base_meaning or "meaning unknown (anonymized)")

    if feature_name in NAMED_COLUMNS:
        return feature_name, NAMED_COLUMNS[feature_name][0]

    fam = family_for(feature_name)
    if fam and fam in FAMILY_DESCRIPTIONS:
        return feature_name, FAMILY_DESCRIPTIONS[fam][0]

    return feature_name, "meaning unknown (anonymized)"


def _is_one_hot_dummy(feature_name: str, low_card_cols: list[str]) -> bool:
    return any(feature_name.startswith(col + "_") for col in low_card_cols)


def top_reasons_for_row(shap_row: pd.Series, feature_values: pd.Series, low_card_cols: list[str], k: int = TOP_K_REASONS):
    ranked = shap_row.reindex(shap_row.abs().sort_values(ascending=False).index).head(k)
    reasons = []
    for feat, shap_val in ranked.items():
        label, meaning = describe_feature(feat, low_card_cols)
        # One-hot dummy columns are 0/1 indicators ("is this card6=debit?"), not the
        # category itself - describe_feature() always phrases the label as if the
        # category is TRUE. If the actual value for THIS transaction is 0, that's
        # false and must be corrected, or we'd be stating an unsupported fact
        # (e.g. labeling a transaction "card6 = debit" when it's actually credit).
        if _is_one_hot_dummy(feat, low_card_cols):
            value = feature_values.get(feat)
            if value is not None and value < 0.5:
                col, _, category = label.partition(" = ")
                label = f"{col} is NOT {category}"
        reasons.append({
            "feature": feat,
            "label": label,
            "shap_value": float(shap_val),
            "feature_value": feature_values.get(feat),
            "direction": "pushed toward FRAUD" if shap_val > 0 else "pushed toward NOT-fraud",
            "meaning": meaning,
        })
    return reasons


def format_example(title: str, meta_row: pd.Series, reasons: list[dict]) -> str:
    lines = [f"### {title}\n"]
    lines.append(
        f"- TransactionID {int(meta_row['TransactionID'])}, amount ${meta_row['TransactionAmt']:.2f}, "
        f"model's fraud probability: {meta_row['xgb_fraud_probability']:.1%}, "
        f"actually fraud: {'yes' if meta_row['isFraud'] == 1 else 'no'}\n"
    )
    lines.append("Top reasons (biggest SHAP contributors):\n")
    for r in reasons:
        val = r["feature_value"]
        val_str = f"{val:.3g}" if isinstance(val, (int, float, np.floating)) else str(val)
        lines.append(
            f"- **{r['label']}** (value: {val_str}) {r['direction']} "
            f"(SHAP {r['shap_value']:+.3f}). {r['meaning']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    print("Loading model and test data...")
    booster = xgb.Booster()
    booster.load_model(str(MODELS_DIR / "xgboost_model.json"))
    feature_names = json.loads((MODELS_DIR / "feature_names.json").read_text())
    encoding_info = json.loads((MODELS_DIR / "encoding_info.json").read_text())
    low_card_cols = encoding_info["low_cardinality_one_hot"]

    X_test = pd.read_parquet(PROCESSED_DIR / "X_test.parquet")
    test_meta = pd.read_parquet(PROCESSED_DIR / "test_predictions.parquet")

    flagged_mask = test_meta["xgb_fraud_probability"] >= THRESHOLD
    flagged_idx = test_meta.index[flagged_mask]
    print(f"{len(flagged_idx):,} of {len(test_meta):,} test transactions are flagged at threshold {THRESHOLD}")

    X_flagged = X_test.loc[flagged_idx]
    meta_flagged = test_meta.loc[flagged_idx].reset_index(drop=True)
    X_flagged = X_flagged.reset_index(drop=True)

    print("Computing SHAP values for flagged transactions (this can take a minute)...")
    explainer = shap.TreeExplainer(booster)
    shap_values = explainer.shap_values(X_flagged)
    shap_df = pd.DataFrame(shap_values, columns=feature_names)

    # ---- Global importance: which features matter most, on average, across all flagged transactions ----
    mean_abs_shap = shap_df.abs().mean().sort_values(ascending=False)
    top20 = mean_abs_shap.head(20)
    labels = [describe_feature(f, low_card_cols)[0] for f in top20.index]
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(range(len(top20)), top20.values[::-1], color="#1565C0")
    ax.set_yticks(range(len(top20)))
    ax.set_yticklabels(labels[::-1], fontsize=8)
    ax.set_xlabel("Mean |SHAP value| across flagged transactions")
    ax.set_title("Top 20 drivers of a fraud flag (averaged across all flagged transactions)")
    fig.tight_layout()
    fig.savefig(IMPORTANCE_CHART, dpi=150)

    # ---- Save per-transaction top reasons for Stage 6 to reuse ----
    all_reasons = []
    for i in range(len(meta_flagged)):
        reasons = top_reasons_for_row(shap_df.iloc[i], X_flagged.iloc[i], low_card_cols)
        for rank, r in enumerate(reasons, start=1):
            all_reasons.append({"TransactionID": int(meta_flagged.loc[i, "TransactionID"]), "rank": rank, **r})
    reasons_df = pd.DataFrame(all_reasons)
    reasons_df.to_parquet(PROCESSED_DIR / "shap_top_reasons_flagged.parquet", index=False)

    # ---- Write report with a handful of worked examples ----
    report = ["# Stage 5 findings: explaining flagged transactions with SHAP\n"]
    report.append(
        f"At Stage 4's recommended threshold ({THRESHOLD}), **{len(flagged_idx):,}** of the "
        f"{len(test_meta):,} test transactions are flagged. SHAP was computed for every one of "
        f"them (not just the examples below); the full per-transaction reasons are saved to "
        f"`data/processed/shap_top_reasons_flagged.parquet` for Stage 6 to use.\n"
    )
    report.append(
        "**How to read a SHAP number:** each one is signed - positive pushed the score toward "
        "fraud, negative pushed it toward not-fraud - and the SIZE shows how much that one "
        "feature mattered for that one transaction, relative to the model's other features. "
        "They're in the model's internal scoring units, not literal probability percentage "
        "points, so read them as \"what mattered, and in which direction,\" not as an exact "
        "dollar or percent figure.\n"
    )
    report.append(f"![Top SHAP drivers](stage5_shap_importance.png)\n")

    report.append("## Worked examples\n")
    report.append(
        "Showing both correctly-caught fraud AND a couple of false positives on purpose - "
        "seeing where the model gets it wrong, and why, is as important as seeing where it's "
        "right.\n"
    )

    caught = meta_flagged[meta_flagged["isFraud"] == 1].sort_values("xgb_fraud_probability", ascending=False)
    false_pos = meta_flagged[meta_flagged["isFraud"] == 0].sort_values("xgb_fraud_probability", ascending=False)

    for rank, (i, row) in enumerate(caught.head(N_EXAMPLES_CAUGHT).iterrows(), start=1):
        reasons = top_reasons_for_row(shap_df.iloc[i], X_flagged.iloc[i], low_card_cols)
        report.append(format_example(f"Correctly caught fraud #{rank}", row, reasons))

    for rank, (i, row) in enumerate(false_pos.head(N_EXAMPLES_FALSE_POSITIVE).iterrows(), start=1):
        reasons = top_reasons_for_row(shap_df.iloc[i], X_flagged.iloc[i], low_card_cols)
        report.append(format_example(f"False positive (flagged, but actually legitimate) #{rank}", row, reasons))

    OUTPUT_FILE.write_text("\n".join(report))
    print(f"\nSaved report to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Saved importance chart to {IMPORTANCE_CHART.relative_to(PROJECT_ROOT)}")
    print(f"Saved per-transaction reasons to data/processed/shap_top_reasons_flagged.parquet")


if __name__ == "__main__":
    main()
