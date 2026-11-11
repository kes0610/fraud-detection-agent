"""
Stage 6: the NON-AI baseline. Turns the exact same tool evidence the AI agent
gets into a case note using fixed sentence templates and simple if/else rules -
no language model involved at all. This exists purely to compare against the
AI agent: is the AI actually adding value, or could basic string templates do
just as well?
"""

from __future__ import annotations

from agent_tools import gather_all_evidence


def generate_template_note(evidence: dict) -> str:
    tid = evidence["TransactionID"]
    shap = evidence["shap_reasons"]["reasons"]
    history = evidence["recent_same_card_transactions"]
    similar_fraud = evidence["similar_confirmed_fraud"]
    amount_info = evidence["amount_unusualness"]

    lines = [f"CASE NOTE (template-generated, no AI) - TransactionID {tid}", ""]

    lines.append("Why flagged (top model factors):")
    if shap:
        for r in shap[:3]:
            lines.append(f"  - {r['feature']}: {r['direction']} (SHAP {r['shap_value']:+.3f})")
    else:
        lines.append("  - No SHAP reasons available.")

    lines.append("")
    lines.append("Evidence found:")
    lines.append(
        f"  - {history['transactions_found']} prior transaction(s) found for this card "
        f"({history['match_type']})."
    )
    if amount_info["prior_transactions_found"] > 0:
        lines.append(f"  - {amount_info['assessment']}")
    else:
        lines.append("  - No prior transaction history found for this card - amount could not be compared.")
    lines.append(
        f"  - {similar_fraud['matches_found']} similar past confirmed-fraud case(s) found "
        f"({similar_fraud['similarity_criteria']})."
    )

    lines.append("")
    lines.append("Suggested next step:")
    if similar_fraud["matches_found"] >= 2:
        lines.append("  - Multiple similar confirmed-fraud cases found: recommend holding the transaction and contacting the cardholder to verify.")
    elif amount_info.get("this_amount_percentile_vs_history", 0) >= 90:
        lines.append("  - Amount is unusually high for this card's history: recommend verifying with the cardholder before releasing funds.")
    elif history["transactions_found"] == 0:
        lines.append("  - No prior history for this card: recommend standard manual review, since there's no baseline to compare against.")
    else:
        lines.append("  - Recommend standard manual review of the flagged factors before deciding.")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    tid = int(sys.argv[1])
    evidence = gather_all_evidence(tid)
    print(generate_template_note(evidence))
