"""
Stage 2: automated data-quality checks.

Runs a fixed set of checks against the joined `transactions` view and writes a
plain-English report to outputs/stage2_data_quality_report.md. Nothing here
modifies the data - this stage is about finding and describing problems, not
silently fixing them.

Checks:
  1. Missing values - how much of each column is empty (NULL)?
  2. Duplicate records - is TransactionID really unique? Are any full rows
     exact duplicates?
  3. Unrealistic amounts - any purchase amount that's zero or negative?
  4. Invalid categories - any value in a categorical column that falls
     outside the set of values Kaggle's own documentation says is valid?
  5. Join problems - does every row in train_identity.csv actually match a
     row in train_transaction.csv (it should, since identity is a subset)?
"""

from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "stage2_data_quality_report.md"

# Valid category values per Kaggle's official IEEE-CIS data field descriptions.
# Anything outside these sets (besides NULL, which is handled separately as
# "missing") is worth a human's attention.
VALID_CATEGORIES = {
    "ProductCD": {"W", "C", "R", "H", "S"},
    "card4": {"visa", "mastercard", "american express", "discover"},
    "card6": {"credit", "debit", "debit or credit", "charge card"},
}


def section(title: str) -> str:
    return f"\n## {title}\n"


def main() -> None:
    con = duckdb.connect(str(PROJECT_ROOT / "data" / "warehouse.duckdb"))
    con.execute("SET enable_progress_bar = false")
    report = ["# Stage 2 findings: data quality report\n"]
    print_and_report = lambda text: (print(text), report.append(text))

    # --- 1. Missing values, every column -----------------------------------
    print_and_report(section("1. Missing values"))
    summary = con.execute("SUMMARIZE SELECT * FROM transactions").fetchdf()
    summary = summary[["column_name", "column_type", "null_percentage"]].sort_values(
        "null_percentage", ascending=False
    )
    fully_empty = summary[summary["null_percentage"] == 100.0]
    heavily_missing = summary[
        (summary["null_percentage"] >= 50.0) & (summary["null_percentage"] < 100.0)
    ]
    print_and_report(
        f"- {len(fully_empty)} column(s) are 100% empty (completely unusable as-is).\n"
        f"- {len(heavily_missing)} column(s) are 50-99% missing (usable, but need a "
        f"missing-value strategy before modeling).\n"
        f"- Full missing-value percentage for every column is in "
        f"`outputs/stage2_missingness_by_column.csv`.\n"
    )
    if len(fully_empty):
        print_and_report("Completely empty columns:\n" + ", ".join(fully_empty["column_name"]) + "\n")
    summary.to_csv(PROJECT_ROOT / "outputs" / "stage2_missingness_by_column.csv", index=False)

    # --- 2. Duplicate records ------------------------------------------------
    print_and_report(section("2. Duplicate records"))

    dup_txn_id = con.execute(
        "SELECT COUNT(*) FROM (SELECT TransactionID FROM raw_train_transaction "
        "GROUP BY TransactionID HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    dup_identity_id = con.execute(
        "SELECT COUNT(*) FROM (SELECT TransactionID FROM raw_train_identity "
        "GROUP BY TransactionID HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    full_row_dupes = con.execute(
        "SELECT COUNT(*) FROM (SELECT * FROM raw_train_transaction "
        "GROUP BY ALL HAVING COUNT(*) > 1)"
    ).fetchone()[0]

    print_and_report(
        f"- TransactionID is supposed to be a unique ID (a \"primary key\" - one row per "
        f"transaction). Duplicated TransactionIDs in train_transaction.csv: **{dup_txn_id}**. "
        f"In train_identity.csv: **{dup_identity_id}**.\n"
        f"- Fully duplicate rows (every column identical) in train_transaction.csv: "
        f"**{full_row_dupes}**.\n"
    )

    # --- 3. Unrealistic amounts -----------------------------------------------
    print_and_report(section("3. Unrealistic purchase amounts"))
    bad_amounts = con.execute(
        "SELECT COUNT(*) FROM transactions WHERE TransactionAmt <= 0"
    ).fetchone()[0]
    print_and_report(
        f"- Transactions with a purchase amount of $0 or less (not possible for a real "
        f"purchase): **{bad_amounts}**.\n"
    )

    # --- 4. Invalid categories -------------------------------------------------
    print_and_report(section("4. Invalid category values"))
    for column, valid_values in VALID_CATEGORIES.items():
        placeholders = ", ".join(f"'{v}'" for v in valid_values)
        rows = con.execute(
            f"SELECT {column}, COUNT(*) AS n FROM transactions "
            f"WHERE {column} IS NOT NULL AND {column} NOT IN ({placeholders}) "
            f"GROUP BY {column} ORDER BY n DESC"
        ).fetchdf()
        if rows.empty:
            print_and_report(f"- `{column}`: no values outside the documented valid set. OK.\n")
        else:
            print_and_report(
                f"- `{column}`: found {len(rows)} unexpected value(s) not in the documented "
                f"valid set {sorted(valid_values)}:\n{rows.to_string(index=False)}\n"
            )

    # --- 5. Join problems --------------------------------------------------
    print_and_report(section("5. Join problems"))
    orphan_identity_rows = con.execute(
        "SELECT COUNT(*) FROM raw_train_identity i "
        "LEFT JOIN raw_train_transaction t USING (TransactionID) "
        "WHERE t.TransactionID IS NULL"
    ).fetchone()[0]
    print_and_report(
        f"- Rows in train_identity.csv whose TransactionID has no match in "
        f"train_transaction.csv (would be silently dropped or cause problems): "
        f"**{orphan_identity_rows}**.\n"
    )

    OUTPUT_FILE.write_text("\n".join(report))
    print(f"\nSaved full report to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
