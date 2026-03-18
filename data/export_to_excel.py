"""Export all tables from test.db to an Excel file with each table as a separate sheet."""

import argparse
import sqlite3
import sys

import pandas as pd


def export(db_path: str, output_path: str) -> None:
    conn = sqlite3.connect(db_path)
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)

    if tables.empty:
        print("No tables found in the database.", file=sys.stderr)
        conn.close()
        sys.exit(1)

    print(f"Found {len(tables)} tables: {list(tables['name'])}")

    with pd.ExcelWriter(output_path) as writer:
        for t in tables["name"]:
            df = pd.read_sql(f"SELECT * FROM [{t}]", conn)
            df.to_excel(writer, sheet_name=t[:31], index=False)
            print(f"  {t}: {len(df)} rows")

    conn.close()
    print(f"\nExported to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export SQLite tables to Excel")
    parser.add_argument("--db", default="data/test.db", help="Path to SQLite database")
    parser.add_argument("--output", default="data/export.xlsx", help="Output Excel file path")
    args = parser.parse_args()

    export(args.db, args.output)
