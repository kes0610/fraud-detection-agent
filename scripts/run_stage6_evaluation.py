"""
Stage 6: picks a random sample of flagged transactions, gathers evidence for
each, and generates both a template note and an AI note - saving everything
to one file so it can be evaluated afterward (by a human, or by Claude acting
as a reviewer) against what the tools actually found.

Run this AFTER GEMINI_API_KEY is set in .env. It prints progress as it goes
since the AI calls are deliberately slow (see ai_agent.py for why).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from agent_tools import gather_all_evidence
from template_baseline import generate_template_note
from ai_agent import generate_ai_note

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "stage6_sample_cases.json"

SAMPLE_SIZE = 25
RANDOM_SEED = 42


def main() -> None:
    shap_df = pd.read_parquet(PROCESSED_DIR / "shap_top_reasons_flagged.parquet")
    predictions_df = pd.read_parquet(PROCESSED_DIR / "test_predictions.parquet")

    flagged_ids = shap_df["TransactionID"].unique()
    sample_ids = pd.Series(flagged_ids).sample(n=SAMPLE_SIZE, random_state=RANDOM_SEED).tolist()
    print(f"Sampled {len(sample_ids)} of {len(flagged_ids):,} flagged transactions (seed={RANDOM_SEED}).")

    cases = []
    for i, tid in enumerate(sample_ids, start=1):
        print(f"[{i}/{len(sample_ids)}] TransactionID {tid}...")
        evidence = gather_all_evidence(int(tid))
        template_note = generate_template_note(evidence)
        try:
            ai_note = generate_ai_note(int(tid), evidence=evidence)
            ai_error = None
        except Exception as e:  # noqa: BLE001 - we want to record the failure and keep going
            ai_note = None
            ai_error = str(e)
            print(f"  AI note failed: {ai_error}")

        actual_row = predictions_df[predictions_df["TransactionID"] == tid].iloc[0]
        cases.append({
            "TransactionID": int(tid),
            "actually_fraud": bool(actual_row["isFraud"]),
            "model_fraud_probability": float(actual_row["xgb_fraud_probability"]),
            "evidence": evidence,
            "template_note": template_note,
            "ai_note": ai_note,
            "ai_error": ai_error,
        })

    OUTPUT_FILE.write_text(json.dumps(cases, indent=2, default=str))
    n_failed = sum(1 for c in cases if c["ai_error"] is not None)
    print(f"\nSaved {len(cases)} cases to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    if n_failed:
        print(f"Note: {n_failed} AI note(s) failed to generate (see ai_error in the saved file).")


if __name__ == "__main__":
    main()
