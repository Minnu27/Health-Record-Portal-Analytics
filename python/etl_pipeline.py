"""
etl_pipeline.py
----------------
Loads the raw synthetic CSVs (data/raw/) into a local analytical SQLite
database (data/processed/health_portal.db) using a SQLite-compatible
rendering of sql/schema.sql, builds the dim_date spine, and then runs the
query library in sql/queries/*.sql to materialize the processed, BI-ready
extracts that Tableau and Power BI connect to (data/processed/*.csv).

This mirrors, at small scale, the pattern used in production: land raw
data -> conform into a star schema -> publish curated extracts for the
BI layer, rather than pointing dashboards at raw operational tables.
"""
from __future__ import annotations

import glob
import os
import re
import sqlite3

import pandas as pd

BASE = os.path.dirname(__file__)
RAW_DIR = os.path.join(BASE, "..", "data", "raw")
PROCESSED_DIR = os.path.join(BASE, "..", "data", "processed")
SQL_DIR = os.path.join(BASE, "..", "sql")
DB_PATH = os.path.join(PROCESSED_DIR, "health_portal.db")

os.makedirs(PROCESSED_DIR, exist_ok=True)


def sqlite_schema() -> str:
    """Render sql/schema.sql into SQLite-compatible DDL (drop Postgres-only
    types/constructs that SQLite doesn't understand)."""
    with open(os.path.join(SQL_DIR, "schema.sql"), encoding="utf-8") as f:
        ddl = f.read()
    ddl = ddl.replace(" CASCADE", "")
    ddl = re.sub(r"NUMERIC\(\d+,\d+\)", "REAL", ddl)
    ddl = ddl.replace("SMALLINT", "INTEGER")
    return ddl


def build_dim_date(conn: sqlite3.Connection) -> None:
    dates = pd.date_range("2024-01-01", "2026-08-08", freq="D")
    dim_date = pd.DataFrame({
        "date_key": dates.strftime("%Y-%m-%d"),
        "year": dates.year,
        "month": dates.month,
        "month_name": dates.strftime("%B"),
        "year_month": dates.strftime("%Y-%m"),
        "quarter": dates.year.astype(str) + "-Q" + ((dates.quarter)).astype(str),
        "day_of_week": dates.strftime("%A"),
        "is_weekend": dates.dayofweek.isin([5, 6]),
    })
    dim_date.to_sql("dim_date", conn, if_exists="append", index=False)


def load_csv(conn: sqlite3.Connection, table: str, filename: str) -> int:
    df = pd.read_csv(os.path.join(RAW_DIR, filename))
    df.to_sql(table, conn, if_exists="append", index=False)
    return len(df)


def main() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(sqlite_schema())

    build_dim_date(conn)

    load_map = [
        ("dim_departments", "dim_departments.csv"),
        ("dim_providers", "dim_providers.csv"),
        ("dim_patients", "dim_patients.csv"),
        ("dim_campaigns", "dim_campaigns.csv"),
        ("fact_encounters", "fact_encounters.csv"),
        ("fact_portal_engagement", "fact_portal_engagement.csv"),
        ("fact_satisfaction_surveys", "fact_satisfaction_surveys.csv"),
        ("fact_campaign_responses", "fact_campaign_responses.csv"),
    ]
    print("Loading raw CSVs into SQLite warehouse...")
    for table, fname in load_map:
        n = load_csv(conn, table, fname)
        print(f"  {table:<28} {n:>8,} rows")

    conn.commit()

    print("\nRunning query library to materialize BI-ready extracts...")
    query_files = sorted(glob.glob(os.path.join(SQL_DIR, "queries", "*.sql")))
    for qf in query_files:
        name = os.path.splitext(os.path.basename(qf))[0]
        with open(qf, encoding="utf-8") as f:
            sql_text = f.read()
        # strip leading comment header, keep the executable statement
        try:
            df = pd.read_sql_query(sql_text, conn)
        except Exception as exc:  # pragma: no cover - diagnostic aid
            print(f"  [SKIP] {name}: {exc}")
            continue
        out_path = os.path.join(PROCESSED_DIR, f"{name}.csv")
        df.to_csv(out_path, index=False)
        print(f"  {name:<38} -> {len(df):>6,} rows  ({os.path.basename(out_path)})")

    conn.close()
    print(f"\nWarehouse ready at: {os.path.abspath(DB_PATH)}")
    print(f"Processed extracts at: {os.path.abspath(PROCESSED_DIR)}")


if __name__ == "__main__":
    main()
