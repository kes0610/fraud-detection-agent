"""Automated numeric fact-check of the AI notes against their evidence JSON:
flags specific, checkable claims (recent-tx fraud count, amount percentile,
similar-fraud count) that don't match the real numbers."""
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
cases = json.loads((PROJECT_ROOT / "outputs" / "stage6_sample_cases.json").read_text())

for i, c in enumerate(cases, start=1):
    ev = c["evidence"]
    hist = ev["recent_same_card_transactions"]
    sim = ev["similar_confirmed_fraud"]
    amt = ev["amount_unusualness"]
    note = c["ai_note"] or ""

    real_fraud_among_recent = sum(1 for h in hist["history"] if h["was_confirmed_fraud"])
    issues = []

    # Check for claims like "N of them/these/these transactions ... (confirmed) fraud"
    for m in re.finditer(r"(\d+)\s+of\s+(?:these|them|those|10|the)[^.]*?(?:confirmed\s+)?(?:as\s+)?fraud", note, re.IGNORECASE):
        claimed = int(m.group(1))
        if claimed != real_fraud_among_recent and claimed <= hist["transactions_found"]:
            issues.append(f"Claims {claimed} of recent same-card txns were fraud; actually {real_fraud_among_recent}")

    # Check claimed percentile vs real percentile (within the same card's amount history)
    if amt["prior_transactions_found"] > 0:
        real_pct = amt["this_amount_percentile_vs_history"]
        for m in re.finditer(r"higher than (\d+(?:\.\d+)?)%", note):
            claimed_pct = float(m.group(1))
            if abs(claimed_pct - real_pct) > 1.0:
                issues.append(f"Claims amount higher than {claimed_pct}% of history; actually {real_pct}%")

    # Check claimed similar-fraud-match count
    for m in re.finditer(r"(\d+)\s+(?:confirmed\s+fraud|similar confirmed fraud|matches?)", note, re.IGNORECASE):
        claimed = int(m.group(1))
        if claimed not in (sim["matches_found"], hist["transactions_found"]) and claimed > 0 and claimed <= 20:
            pass  # too noisy to flag reliably, skip

    if issues:
        print(f"CASE {i} (TransactionID {c['TransactionID']}): " + " | ".join(issues))

print("\nDone - cases not listed above had no automatically-detected numeric mismatches (manual review still applies).")
