"""
Loads the supplied operational Excel workbook (accounts / orders / tickets)
into SQLite so tools can run real WHERE-clause access control instead of
filtering in Python after the fact.

Usage:
    python -m ingestion.ingest_excel --xlsx data/raw/operational_data.xlsx
"""
import argparse
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "parcelpilot.db"


# Map expected sheet names -> SQL table names.
# Adjust these once you've actually opened the supplied workbook —
# the assessment data pack's real sheet/column names may differ.
SHEET_TABLE_MAP = {
    "accounts": "accounts",
    "orders": "orders",
    "tickets": "tickets",
}


def ingest(xlsx_path: str, db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    xls = pd.ExcelFile(xlsx_path)
    print(f"Sheets found in workbook: {xls.sheet_names}")

    for sheet_name, table_name in SHEET_TABLE_MAP.items():
        if sheet_name not in xls.sheet_names:
            print(f"  [skip] sheet '{sheet_name}' not found — check actual sheet names above")
            continue
        df = pd.read_excel(xls, sheet_name=sheet_name)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"  [ok] loaded {len(df)} rows into '{table_name}'")

    # Helpful indexes for access-control lookups
    cur = conn.cursor()
    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_orders_account ON orders(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_account ON tickets(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_order ON tickets(order_id)",
    ]:
        try:
            cur.execute(stmt)
        except sqlite3.OperationalError as e:
            print(f"  [warn] index skipped: {e}")
    conn.commit()
    conn.close()
    print(f"Done. DB written to {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", required=True, help="Path to the operational data Excel file")
    args = parser.parse_args()
    ingest(args.xlsx)
