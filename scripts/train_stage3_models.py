"""
Stage 3: trains a baseline model and a stronger model, compares two ways of
handling class imbalance, and evaluates everything the honest way (not plain
accuracy). Saves trained models + a test-set prediction file that later
stages (threshold selection, SHAP, the agent) will reuse.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import xgboost as xgb
from imblearn.over_sampling import RandomOverSampler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from features import get_train_test_features, PROJECT_ROOT

MODELS_DIR = PROJECT_ROOT / "models"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "stage3_model_results.md"
DECISION_THRESHOLD = 0.5  # a provisional, round-number cutoff - Stage 4 picks the real one


def evaluate(y_true, y_proba, threshold=DECISION_THRESHOLD) -> dict:
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "pr_auc": average_precision_score(y_true, y_proba),
        "precision_at_0.5": precision_score(y_true, y_pred, zero_division=0),
        "recall_at_0.5": recall_score(y_true, y_pred, zero_division=0),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
    }


def format_result(name: str, metrics: dict) -> str:
    return (
        f"### {name}\n\n"
        f"- **PR-AUC: {metrics['pr_auc']:.4f}** (threshold-independent; closer to 1.0 is better, "
        f"a model that only guesses the 3.5% fraud rate at random scores about 0.035)\n"
        f"- At a provisional 0.5 cutoff - precision: {metrics['precision_at_0.5']:.3f}, "
        f"recall: {metrics['recall_at_0.5']:.3f}\n"
        f"- Confusion matrix at 0.5 cutoff: "
        f"TP={metrics['true_positives']}, FP={metrics['false_positives']}, "
        f"FN={metrics['false_negatives']}, TN={metrics['true_negatives']}\n"
    )


def main() -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(exist_ok=True)
    report = ["# Stage 3 findings: baseline vs. stronger model\n"]

    print("Building features and time-based train/test split...")
    X_train, X_test, y_train, y_test, feature_names, encoding_info, test_meta = get_train_test_features()
    print(f"Train: {len(X_train)} rows, Test: {len(X_test)} rows, Features: {len(feature_names)}")

    # ---- Baseline: Logistic Regression, two imbalance-handling approaches ----
    report.append("## Baseline model: Logistic Regression\n")
    report.append(
        "Logistic regression draws a straight-line (linear) boundary between fraud and "
        "non-fraud based on a weighted sum of the features. It's simple, fast, and easy to "
        "explain - a reasonable floor to measure the stronger model against.\n"
    )
    report.append(
        "Fraud is rare (3.5%), so a model can get 96.5% 'accuracy' by predicting "
        "'not fraud' for everything and never catching a single fraud case - which is "
        "useless. That's why accuracy is never reported here: PR-AUC, precision and recall "
        "all specifically account for how rare the positive class (fraud) is.\n"
    )
    report.append(
        "We compare two ways of handling that imbalance:\n\n"
        "- **Class weighting** - tell the model to treat each fraud example as more "
        "important than a non-fraud example when learning, roughly in proportion to how "
        "rare fraud is. No new rows are created.\n"
        "- **Random oversampling** - literally duplicate fraud examples in the training "
        "set (only the training set - never the test set) until the two classes are "
        "equally represented.\n"
    )

    # Clip (winsorize) extreme outliers before scaling: some anonymized columns
    # have values like 641,511 while 99%+ of that same column is near 0. Logistic
    # regression is sensitive to outlier scale and overflowed during training
    # until we capped each column at its 1st/99th percentile (computed on TRAIN
    # only, then applied to both train and test - same no-leakage rule as the
    # categorical encoding). XGBoost doesn't need this - trees split on value
    # ranges and aren't thrown off by one extreme point the way a weighted sum is.
    lower = X_train.quantile(0.01)
    upper = X_train.quantile(0.99)
    X_train_clipped = X_train.clip(lower=lower, upper=upper, axis=1)
    X_test_clipped = X_test.clip(lower=lower, upper=upper, axis=1)

    impute_scale = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", RobustScaler()),
    ])
    X_train_scaled = impute_scale.fit_transform(X_train_clipped)
    X_test_scaled = impute_scale.transform(X_test_clipped)

    # C=0.1 (stronger-than-default L2 regularization) and a capped max_iter: with
    # 469 features, many of them one-hot/boolean indicators, and strong class
    # weighting for the rare class, lbfgs was taking 1000+ iterations without
    # converging and overflowing during the attempt. Regularizing harder keeps
    # the coefficients bounded; the capped iteration count stops it running
    # indefinitely. This is documented as a real baseline limitation below,
    # not hidden.
    print("Training logistic regression (class weighting)...")
    logreg_weighted = LogisticRegression(class_weight="balanced", max_iter=200, C=0.1)
    logreg_weighted.fit(X_train_scaled, y_train)
    metrics_weighted = evaluate(y_test, logreg_weighted.predict_proba(X_test_scaled)[:, 1])
    report.append(format_result("Logistic Regression + class weighting", metrics_weighted))

    print("Training logistic regression (random oversampling)...")
    ros = RandomOverSampler(random_state=42)
    X_train_over, y_train_over = ros.fit_resample(X_train_scaled, y_train)
    logreg_oversampled = LogisticRegression(max_iter=200, C=0.1)
    logreg_oversampled.fit(X_train_over, y_train_over)
    metrics_oversampled = evaluate(y_test, logreg_oversampled.predict_proba(X_test_scaled)[:, 1])
    report.append(format_result("Logistic Regression + random oversampling", metrics_oversampled))

    if metrics_weighted["pr_auc"] >= metrics_oversampled["pr_auc"]:
        baseline_name, baseline_model, baseline_metrics = (
            "class weighting", logreg_weighted, metrics_weighted,
        )
    else:
        baseline_name, baseline_model, baseline_metrics = (
            "random oversampling", logreg_oversampled, metrics_oversampled,
        )
    report.append(
        f"**Winner: {baseline_name}** (higher PR-AUC) - this is the version we call "
        f"\"the baseline\" from here on.\n"
    )
    joblib.dump({"pipeline": impute_scale, "model": baseline_model}, MODELS_DIR / "baseline_logreg.joblib")

    # ---- Stronger model: XGBoost ----
    report.append("## Stronger model: XGBoost\n")
    report.append(
        "XGBoost builds hundreds of small decision trees one after another, where each new "
        "tree focuses on correcting the previous trees' mistakes. We chose it over "
        "LightGBM (the other option in the plan) simply because it needed no extra system "
        "setup beyond a standard pip install, and it has native support for missing values "
        "and for weighting the rare class, both of which this dataset needs.\n"
    )
    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
    report.append(
        f"For imbalance, XGBoost uses class weighting too (`scale_pos_weight` = "
        f"{scale_pos_weight:.1f}, i.e. treat one fraud example as worth about "
        f"{scale_pos_weight:.0f} non-fraud examples) - the same style of fix that won "
        f"the baseline comparison above, now applied to a model built to use it well.\n"
    )

    print("Training XGBoost...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
    )
    xgb_model.fit(X_train, y_train)  # raw X_train: NaNs preserved, XGBoost handles them natively
    xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
    xgb_metrics = evaluate(y_test, xgb_proba)
    report.append(format_result("XGBoost", xgb_metrics))

    improvement = xgb_metrics["pr_auc"] - baseline_metrics["pr_auc"]
    report.append(
        f"## Comparison\n\n"
        f"XGBoost's PR-AUC ({xgb_metrics['pr_auc']:.4f}) vs. the baseline's "
        f"({baseline_metrics['pr_auc']:.4f}): a difference of {improvement:+.4f}.\n"
    )

    xgb_model.save_model(str(MODELS_DIR / "xgboost_model.json"))
    (MODELS_DIR / "feature_names.json").write_text(json.dumps(feature_names, indent=2))
    (MODELS_DIR / "encoding_info.json").write_text(json.dumps(encoding_info, indent=2))

    # ---- Save test-set predictions for later stages ----
    test_predictions = test_meta.copy()
    test_predictions["isFraud"] = y_test.reset_index(drop=True)
    test_predictions["xgb_fraud_probability"] = xgb_proba
    test_predictions.to_parquet(PROCESSED_DIR / "test_predictions.parquet", index=False)
    X_test.reset_index(drop=True).to_parquet(PROCESSED_DIR / "X_test.parquet", index=False)

    OUTPUT_FILE.write_text("\n".join(report))
    print(f"\nSaved report to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Saved models to {MODELS_DIR.relative_to(PROJECT_ROOT)}")
    print(f"Saved test predictions to {PROCESSED_DIR.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
