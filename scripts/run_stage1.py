"""
Stage 1: runs the setup + exploration .sql files in sql/, prints each query's
result, and writes everything to outputs/stage1_findings.md so there's a saved
record of what we found (not just terminal output that scrolls away).
"""

import re
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "stage1_findings.md"

STAGE1_FILES = [
    "00_setup_tables.sql",
    "01_row_counts_and_join_coverage.sql",
    "02_purchase_amount_overview.sql",
    "03_fraud_vs_nonfraud.sql",
    "04_missing_data_overview.sql",
]


def split_statements(sql_text: str) -> list[str]:
    """Split a .sql file into individual statements on ';'. Good enough here
    because none of our queries put a semicolon inside a string or comment."""
    statements = [s.strip() for s in sql_text.split(";")]
    return [s for s in statements if s and not all(
        line.strip().startswith("--") or not line.strip()
        for line in s.splitlines()
    )]


def leading_comment(statement: str) -> str:
    """Pull the plain-English explanation out of the -- comment lines at the
    top of a statement, so we can print it alongside the result."""
    lines = []
    for line in statement.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            lines.append(stripped.lstrip("-").strip())
        elif stripped:
            break
    return "\n".join(lines)


def main() -> None:
    con = duckdb.connect(str(PROJECT_ROOT / "data" / "warehouse.duckdb"))
    report_lines = ["# Stage 1 findings: exploring the data with SQL\n"]

    for filename in STAGE1_FILES:
        path = SQL_DIR / filename
        sql_text = path.read_text()
        statements = split_statements(sql_text)

        print(f"\n{'=' * 70}\n{filename}\n{'=' * 70}")
        if filename != "00_setup_tables.sql":
            report_lines.append(f"\n## `{filename}`\n")

        for statement in statements:
            comment = leading_comment(statement)
            result = con.execute(statement)
            try:
                df = result.fetchdf()
            except Exception:
                continue  # statement had no tabular result (e.g. CREATE TABLE)

            if comment:
                print(f"\n{comment}\n")
            if not df.empty:
                print(df.to_string(index=False))

            if filename != "00_setup_tables.sql" and not df.empty:
                if comment:
                    report_lines.append(f"{comment}\n")
                report_lines.append(df.to_markdown(index=False) + "\n")

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text("\n".join(report_lines))
    print(f"\nSaved full report to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
