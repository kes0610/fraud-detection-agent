"""Prints a condensed, side-by-side review sheet of all 25 sample cases:
the key evidence facts + both notes, so each pair can be checked against the
evidence efficiently."""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
cases = json.loads((PROJECT_ROOT / "outputs" / "stage6_sample_cases.json").read_text())

for i, c in enumerate(cases, start=1):
    ev = c["evidence"]
    shap = ev["shap_reasons"]["reasons"]
    hist = ev["recent_same_card_transactions"]
    sim = ev["similar_confirmed_fraud"]
    amt = ev["amount_unusualness"]

    print(f"\n{'='*90}\nCASE {i}/25 - TransactionID {c['TransactionID']} - actually fraud: {c['actually_fraud']} - model prob: {c['model_fraud_probability']:.2f}")
    print(f"{'-'*90}")
    print("EVIDENCE FACTS:")
    print(f"  SHAP top reasons: " + "; ".join(f"{r['feature']} ({r['direction']}, {r['shap_value']:+.2f})" for r in shap))
    print(f"  Recent same-card: {hist['transactions_found']} found, {sum(1 for h in hist['history'] if h['was_confirmed_fraud'])} of those were fraud")
    print(f"  Similar confirmed fraud (separate lookup): {sim['matches_found']} found")
    if amt["prior_transactions_found"] > 0:
        print(f"  Amount check: {amt['assessment']}")
    else:
        print(f"  Amount check: no prior history")
    print(f"{'-'*90}")
    print("TEMPLATE NOTE:")
    print(c["template_note"])
    print(f"{'-'*90}")
    print("AI NOTE:")
    print(c["ai_note"])
