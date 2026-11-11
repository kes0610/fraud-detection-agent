"""
Stage 6: the four "tools" the investigation agent can call. Each one answers
one factual question about a flagged transaction, by querying the real data -
nothing here is written or guessed by a language model. The agent (and the
non-AI template baseline) both call these same functions; they only differ in
how they turn the results into written sentences.

IMPORTANT LIMITATION - read this before trusting tool (a) or (c): this dataset
has no real card number. "Same card" is APPROXIMATED by matching 8 columns
that together describe the card and billing address (card1-card6, addr1,
addr2). Kaggle's top public solutions for this exact competition use this
same approximation, because it's the best available with anonymized data -
but it is not exact in either direction:
  - Two different real cards COULD share all 8 values by coincidence (we'd
    wrongly treat them as the same card).
  - The same real card could show up with a different addr1/addr2 if the
    cardholder's billing info changed (we'd wrongly treat it as a different
    card).
Every tool result below is labeled "(approximate match)" for this reason, and
this same caveat is repeated in the README.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CARD_PROXY_COLUMNS = ["card1", "card2", "card3", "card4", "card5", "card6", "addr1", "addr2"]

_con = None
_shap_reasons_df = None


def _get_con():
    global _con
    if _con is None:
        _con = duckdb.connect(str(PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
        _con.execute("SET enable_progress_bar = false")
    return _con


def _get_shap_reasons_df():
    global _shap_reasons_df
    if _shap_reasons_df is None:
        path = PROJECT_ROOT / "data" / "processed" / "shap_top_reasons_flagged.parquet"
        _shap_reasons_df = pd.read_parquet(path)
    return _shap_reasons_df


def _proxy_match_clause(alias: str) -> str:
    """Null-safe equality on all 8 card-proxy columns, comparing table `alias`
    against the current transaction's values (bound as DuckDB query params)."""
    return " AND ".join(f"{alias}.{c} IS NOT DISTINCT FROM ?" for c in CARD_PROXY_COLUMNS)


def _get_transaction_row(transaction_id: int) -> dict:
    con = _get_con()
    cols = ", ".join(["TransactionID", "TransactionDT", "TransactionAmt", "ProductCD", "card4", "card6"] + CARD_PROXY_COLUMNS)
    row = con.execute(f"SELECT {cols} FROM transactions WHERE TransactionID = ?", [transaction_id]).fetchdf()
    if row.empty:
        raise ValueError(f"TransactionID {transaction_id} not found")
    return row.iloc[0].to_dict()


def _max_known_transaction_dt() -> int:
    con = _get_con()
    return int(con.execute("SELECT MAX(TransactionDT) FROM transactions").fetchone()[0])


def build_new_transaction_context(row: dict) -> dict:
    """Builds the same lookup context the tools use, for a transaction that is
    NOT in the historical database (e.g. one row from an uploaded file). It's
    treated as happening after every known historical transaction - "recent"
    and "similar past" searches look across the FULL history, same as for a
    real flagged transaction, just with no TransactionID to exclude."""
    ctx = {c: row.get(c) for c in CARD_PROXY_COLUMNS}
    ctx["ProductCD"] = row.get("ProductCD")
    ctx["TransactionAmt"] = row.get("TransactionAmt")
    ctx["TransactionDT"] = _max_known_transaction_dt() + 1
    ctx["TransactionID"] = -1  # sentinel: never matches a real historical row
    return ctx


def _resolve_context(transaction_id: int | None, context: dict | None) -> dict:
    if context is not None:
        return context
    if transaction_id is not None:
        return _get_transaction_row(transaction_id)
    raise ValueError("Must provide either transaction_id or context")


def get_recent_transactions_same_card(transaction_id: int = None, limit: int = 10, context: dict = None) -> dict:
    """Tool (a): recent transactions from the same approximated card, before this one.
    Pass either transaction_id (an existing, already-flagged transaction) or
    context (from build_new_transaction_context, for a brand-new upload)."""
    txn = _resolve_context(transaction_id, context)
    con = _get_con()
    proxy_values = [txn[c] for c in CARD_PROXY_COLUMNS]
    clause = _proxy_match_clause("t")
    query = f"""
        SELECT TransactionID, TransactionDT, TransactionAmt, ProductCD, isFraud
        FROM transactions t
        WHERE {clause}
          AND t.TransactionID != ?
          AND t.TransactionDT < ?
        ORDER BY t.TransactionDT DESC
        LIMIT {int(limit)}
    """
    result = con.execute(query, proxy_values + [txn["TransactionID"], txn["TransactionDT"]]).fetchdf()
    history = []
    for _, r in result.iterrows():
        days_before = round((txn["TransactionDT"] - r["TransactionDT"]) / 86400, 1)
        history.append({
            "TransactionID": int(r["TransactionID"]),
            "days_before_this_transaction": days_before,
            "amount": round(float(r["TransactionAmt"]), 2),
            "product_code": r["ProductCD"],
            "was_confirmed_fraud": bool(r["isFraud"]),
        })
    return {
        "tool": "get_recent_transactions_same_card",
        "match_type": "approximate (8-column card/address proxy, see README limitation)",
        "transactions_found": len(history),
        "history": history,
    }


def find_similar_confirmed_fraud(transaction_id: int = None, limit: int = 5, amount_tolerance: float = 0.3, context: dict = None) -> dict:
    """Tool (b): past CONFIRMED fraud (before this transaction's time) with a similar
    product code, card network/type, and a dollar amount within +/- amount_tolerance."""
    txn = _resolve_context(transaction_id, context)
    con = _get_con()
    low, high = txn["TransactionAmt"] * (1 - amount_tolerance), txn["TransactionAmt"] * (1 + amount_tolerance)
    query = """
        SELECT TransactionID, TransactionDT, TransactionAmt, ProductCD, card4, card6
        FROM transactions
        WHERE isFraud = 1
          AND TransactionDT < ?
          AND ProductCD = ?
          AND card4 IS NOT DISTINCT FROM ?
          AND card6 IS NOT DISTINCT FROM ?
          AND TransactionAmt BETWEEN ? AND ?
        ORDER BY TransactionDT DESC
        LIMIT ?
    """
    result = con.execute(query, [
        txn["TransactionDT"], txn["ProductCD"], txn["card4"], txn["card6"], low, high, limit,
    ]).fetchdf()
    matches = []
    for _, r in result.iterrows():
        matches.append({
            "TransactionID": int(r["TransactionID"]),
            "amount": round(float(r["TransactionAmt"]), 2),
            "product_code": r["ProductCD"],
            "card_network": r["card4"],
            "card_type": r["card6"],
        })
    return {
        "tool": "find_similar_confirmed_fraud",
        "similarity_criteria": f"same product code, same card network/type, amount within {amount_tolerance:.0%}, confirmed fraud before this transaction's time",
        "matches_found": len(matches),
        "matches": matches,
    }


def check_amount_unusualness(transaction_id: int = None, context: dict = None) -> dict:
    """Tool (c): how this amount compares to the SAME approximated card's own past amounts."""
    txn = _resolve_context(transaction_id, context)
    con = _get_con()
    proxy_values = [txn[c] for c in CARD_PROXY_COLUMNS]
    clause = _proxy_match_clause("t")
    query = f"""
        SELECT TransactionAmt
        FROM transactions t
        WHERE {clause}
          AND t.TransactionID != ?
          AND t.TransactionDT < ?
    """
    history = con.execute(query, proxy_values + [txn["TransactionID"], txn["TransactionDT"]]).fetchdf()

    if history.empty:
        return {
            "tool": "check_amount_unusualness",
            "match_type": "approximate (8-column card/address proxy, see README limitation)",
            "prior_transactions_found": 0,
            "this_amount": round(float(txn["TransactionAmt"]), 2),
            "assessment": "No prior transaction history found for this approximated card - cannot assess whether this amount is unusual.",
        }

    amounts = history["TransactionAmt"]
    this_amt = txn["TransactionAmt"]
    percentile = (amounts < this_amt).mean() * 100
    return {
        "tool": "check_amount_unusualness",
        "match_type": "approximate (8-column card/address proxy, see README limitation)",
        "prior_transactions_found": len(amounts),
        "this_amount": round(float(this_amt), 2),
        "prior_median_amount": round(float(amounts.median()), 2),
        "prior_mean_amount": round(float(amounts.mean()), 2),
        "prior_max_amount": round(float(amounts.max()), 2),
        "this_amount_percentile_vs_history": round(float(percentile), 1),
        "assessment": (
            f"This ${this_amt:,.2f} transaction is higher than {percentile:.0f}% of this "
            f"card's {len(amounts)} prior transactions (median was ${amounts.median():,.2f})."
        ),
    }


def get_top_shap_reasons(transaction_id: int, k: int = 5) -> dict:
    """Tool (d): the top-k SHAP reasons already computed in Stage 5 for this transaction.
    Only works for transactions in this project's own flagged test set - a brand-new
    upload has no precomputed SHAP, see get_top_shap_reasons_live() instead."""
    df = _get_shap_reasons_df()
    rows = df[df["TransactionID"] == transaction_id].sort_values("rank").head(k)
    if rows.empty:
        return {"tool": "get_top_shap_reasons", "reasons_found": 0, "reasons": []}
    reasons = []
    for _, r in rows.iterrows():
        reasons.append({
            "feature": r["label"],
            "direction": r["direction"],
            "shap_value": round(float(r["shap_value"]), 3),
            "meaning": r["meaning"],
        })
    return {"tool": "get_top_shap_reasons", "reasons_found": len(reasons), "reasons": reasons}


def get_top_shap_reasons_live(encoded_row: pd.Series, explainer, low_card_cols: list, k: int = 5) -> dict:
    """Same as get_top_shap_reasons, but computes SHAP on the spot for a row
    that has no precomputed value (a brand-new upload), using the same
    plain-English feature descriptions as Stage 5."""
    from stage5_shap_explain import describe_feature, _is_one_hot_dummy  # reuse Stage 5's logic

    # astype("float32") matters: converting a Series back into a one-row
    # DataFrame via to_frame().T otherwise collapses every column to generic
    # "object" dtype, which XGBoost/SHAP refuse to accept as numeric input.
    single_row_df = encoded_row.to_frame().T.astype("float32")
    shap_values = explainer.shap_values(single_row_df)[0]
    shap_series = pd.Series(shap_values, index=encoded_row.index)
    ranked = shap_series.reindex(shap_series.abs().sort_values(ascending=False).index).head(k)

    reasons = []
    for feat, shap_val in ranked.items():
        label, meaning = describe_feature(feat, low_card_cols)
        if _is_one_hot_dummy(feat, low_card_cols):
            value = encoded_row.get(feat)
            if value is not None and value < 0.5:
                col, _, category = label.partition(" = ")
                label = f"{col} is NOT {category}"
        reasons.append({
            "feature": label,
            "direction": "pushed toward FRAUD" if shap_val > 0 else "pushed toward NOT-fraud",
            "shap_value": round(float(shap_val), 3),
            "meaning": meaning,
        })
    return {"tool": "get_top_shap_reasons", "reasons_found": len(reasons), "reasons": reasons}


def gather_all_evidence(transaction_id: int) -> dict:
    """Calls all four tools and returns everything together - what both the
    AI agent and the template baseline work from. For an EXISTING flagged
    transaction only; see gather_all_evidence_for_new_row() for an upload."""
    return {
        "TransactionID": transaction_id,
        "recent_same_card_transactions": get_recent_transactions_same_card(transaction_id),
        "similar_confirmed_fraud": find_similar_confirmed_fraud(transaction_id),
        "amount_unusualness": check_amount_unusualness(transaction_id),
        "shap_reasons": get_top_shap_reasons(transaction_id),
    }


def gather_all_evidence_for_new_row(raw_row: dict, encoded_row: pd.Series, explainer, low_card_cols: list) -> dict:
    """Same as gather_all_evidence, but for a brand-new transaction not in the
    historical database (e.g. one row from an uploaded file). raw_row has the
    original column values (for the DB lookups); encoded_row is that same row
    already transformed into the model's feature space (for live SHAP)."""
    context = build_new_transaction_context(raw_row)
    return {
        "TransactionID": "NEW (uploaded, not in historical data)",
        "recent_same_card_transactions": get_recent_transactions_same_card(context=context),
        "similar_confirmed_fraud": find_similar_confirmed_fraud(context=context),
        "amount_unusualness": check_amount_unusualness(context=context),
        "shap_reasons": get_top_shap_reasons_live(encoded_row, explainer, low_card_cols),
    }


if __name__ == "__main__":
    import sys
    tid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if tid is None:
        df = _get_shap_reasons_df()
        tid = int(df["TransactionID"].iloc[0])
    print(json.dumps(gather_all_evidence(tid), indent=2, default=str))
