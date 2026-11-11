"""
Stage 2: generates data_dictionary.md - one row per column, every column in
the dataset, pulled straight from the real schema (not hand-typed) so it
can't drift out of sync with the actual data.

For columns Kaggle names and documents (TransactionAmt, ProductCD, etc.) we
write the real, publicly documented meaning. For anonymized columns (the
V/C/D/M/id_ families), we only state what Kaggle's own documentation says
about the FAMILY as a whole (e.g. "V columns are Vesta's engineered risk
features") - we never guess what one specific column like V37 means. Kaggle
does not disclose that, and neither do we.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data_dictionary.md"

# Individually documented columns: name -> (meaning, source table, sensitive?)
NAMED_COLUMNS = {
    "TransactionID": ("Unique ID for one transaction. The join key between train_transaction.csv and train_identity.csv.", "train_transaction.csv", "No"),
    "isFraud": ("The target label: 1 = confirmed fraud, 0 = not fraud. This is what the model predicts.", "train_transaction.csv", "No"),
    "TransactionDT": ("A time delta in seconds from a fixed, undisclosed reference point - NOT a real calendar date/time. Useful only for ordering transactions and measuring time *between* events.", "train_transaction.csv", "No"),
    "TransactionAmt": ("The transaction's payment amount, in US dollars.", "train_transaction.csv", "Yes (financial amount)"),
    "ProductCD": ("A code for the product/service category purchased (values: W, C, R, H, S). Kaggle does not disclose what each letter stands for.", "train_transaction.csv", "No"),
    "addr1": ("Address information associated with the transaction (region-level). Exact definition not disclosed by Kaggle.", "train_transaction.csv", "Yes (location-related)"),
    "addr2": ("Address information associated with the transaction (region-level). Exact definition not disclosed by Kaggle.", "train_transaction.csv", "Yes (location-related)"),
    "dist1": ("A distance value (e.g. between billing/shipping address or similar). Exact definition not disclosed by Kaggle.", "train_transaction.csv", "Yes (location-related)"),
    "dist2": ("A distance value (e.g. between billing/shipping address or similar). Exact definition not disclosed by Kaggle.", "train_transaction.csv", "Yes (location-related)"),
    "P_emaildomain": ("Purchaser's email domain (e.g. gmail.com).", "train_transaction.csv", "Yes (personal contact info)"),
    "R_emaildomain": ("Recipient's email domain (e.g. gmail.com), when the purchase has a separate recipient.", "train_transaction.csv", "Yes (personal contact info)"),
    "DeviceType": ("The purchaser's device category: desktop or mobile.", "train_identity.csv", "Yes (device info)"),
    "DeviceInfo": ("A free-text description of the purchaser's device/browser (e.g. a phone model or OS name).", "train_identity.csv", "Yes (device info)"),
}

# Anonymized column families: prefix -> (family meaning per Kaggle's public
# documentation, source table, sensitive?)
FAMILY_DESCRIPTIONS = {
    "card": ("Payment card information - card type, category, issuing bank, country, etc. Kaggle discloses that card4 is the card network (visa/mastercard/amex/discover) and card6 is credit vs. debit; the rest (card1, card2, card3, card5) are not individually documented.", "train_transaction.csv", "Yes (payment card info)"),
    "C": ("A \"counting\" feature - e.g. how many addresses are associated with the payment card. The actual real-world meaning of each individual C column is masked by Vesta.", "train_transaction.csv", "No"),
    "D": ("A \"timedelta\" feature - e.g. days since a previous transaction. The actual real-world meaning of each individual D column is masked by Vesta.", "train_transaction.csv", "No"),
    "M": ("A \"match\" feature - e.g. whether the name on the card matches the name on the address. The actual real-world meaning of each individual M column is masked by Vesta.", "train_transaction.csv", "No"),
    "V": ("A Vesta-engineered risk feature (ranking, counting, or entity-relationship signal, per Vesta's fraud models). The actual real-world meaning of each individual V column is masked by Vesta - meaning unknown (anonymized).", "train_transaction.csv", "No"),
    "id_": ("Network/device fingerprint information (e.g. IP-related signals, browser/OS info, screen resolution) collected by Vesta's fraud system and digital security partners. The actual real-world meaning of each individual id_ column is masked - meaning unknown (anonymized).", "train_identity.csv", "Yes (device/network fingerprint)"),
}


def family_for(column_name: str) -> str | None:
    if re.fullmatch(r"card\d", column_name):
        return "card"
    if re.fullmatch(r"id_\d+", column_name):
        return "id_"
    if re.fullmatch(r"[CDMV]\d+", column_name):
        return column_name[0]
    return None


def main() -> None:
    con = duckdb.connect(str(PROJECT_ROOT / "data" / "warehouse.duckdb"))
    con.execute("SET enable_progress_bar = false")
    schema = con.execute("SUMMARIZE SELECT * FROM transactions").fetchdf()

    rows = []
    for _, r in schema.iterrows():
        col, dtype, null_pct = r["column_name"], r["column_type"], round(r["null_percentage"], 2)

        if col in NAMED_COLUMNS:
            meaning, source, sensitive = NAMED_COLUMNS[col]
        else:
            fam = family_for(col)
            if fam and fam in FAMILY_DESCRIPTIONS:
                meaning, source, sensitive = FAMILY_DESCRIPTIONS[fam]
            else:
                meaning, source, sensitive = ("meaning unknown (anonymized)", "unknown", "Unknown")

        rows.append((col, dtype, f"{null_pct}%", source, sensitive, meaning))

    lines = [
        "# Data dictionary\n",
        "Generated from the real dataset schema - not hand-typed - so column names and "
        "types can't drift out of date. For the anonymized column families (`C`, `D`, `M`, "
        "`V`, `id_`), only Kaggle's own public documentation about what the FAMILY "
        "represents is included; no individual column's specific real-world meaning is "
        "guessed at anywhere in this file.\n",
        f"Total columns: {len(rows)}\n",
        "| Column | Type | % Missing | Source file | Sensitive? | Meaning |",
        "|---|---|---|---|---|---|",
    ]
    for col, dtype, null_pct, source, sensitive, meaning in rows:
        lines.append(f"| `{col}` | {dtype} | {null_pct} | {source} | {sensitive} | {meaning} |")

    OUTPUT_FILE.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(rows)} columns to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
