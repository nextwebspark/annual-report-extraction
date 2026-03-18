"""Database abstraction layer. SupabaseDB for production, SQLiteDB for test mode."""

import json
import sqlite3
from pathlib import Path

from config import settings


class SupabaseDB:
    """Production database using Supabase."""

    def __init__(self):
        from supabase import create_client
        self._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    def select(self, table: str, columns: str, filters: dict, limit: int | None = None) -> list[dict]:
        q = self._client.table(table).select(columns)
        for col, val in filters.items():
            q = q.eq(col, val)
        if limit:
            q = q.limit(limit)
        return q.execute().data

    def insert(self, table: str, row: dict) -> list[dict]:
        return self._client.table(table).insert(row).execute().data

    def upsert(self, table: str, rows: list[dict] | dict, on_conflict: str) -> list[dict]:
        return self._client.table(table).upsert(rows, on_conflict=on_conflict).execute().data


class SQLiteDB:
    """Local SQLite database for test mode. Mirrors the Supabase schema."""

    # Columns that store JSON objects (dicts/lists) in Supabase as JSONB
    _JSON_COLUMNS = {
        "company_name", "exchange", "country", "industry",
        "revenue", "profit_net", "market_capitalisation", "employees",
    }

    def __init__(self, db_path: str | None = None):
        path = db_path or settings.SQLITE_DB_PATH
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        self._migrate()

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                exchange TEXT NOT NULL,
                country TEXT NOT NULL,
                industry TEXT NOT NULL,
                source_document_url TEXT DEFAULT '',
                company_code TEXT UNIQUE,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS company_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                revenue TEXT NOT NULL,
                profit_net TEXT NOT NULL,
                market_capitalisation TEXT,
                employees TEXT,
                extraction_run_id TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(company_id, year)
            );

            CREATE TABLE IF NOT EXISTS board_directors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_id INTEGER NOT NULL,
                director_name TEXT NOT NULL,
                nationality TEXT,
                ethnicity TEXT,
                local_expat TEXT,
                gender TEXT,
                age INTEGER DEFAULT 0,
                board_role TEXT,
                director_type TEXT,
                skills TEXT,
                board_meetings_attended INTEGER DEFAULT 0,
                retainer_fee REAL DEFAULT 0,
                benefits_in_kind REAL DEFAULT 0,
                attendance_allowance REAL DEFAULT 0,
                expense_allowance REAL DEFAULT 0,
                assembly_fee REAL DEFAULT 0,
                director_board_committee_fee REAL DEFAULT 0,
                variable_remuneration REAL DEFAULT 0,
                variable_remuneration_description TEXT DEFAULT '',
                other_remuneration REAL DEFAULT 0,
                other_remuneration_description TEXT DEFAULT '',
                total_fee REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(fact_id, director_name)
            );

            CREATE TABLE IF NOT EXISTS board_committees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_id INTEGER NOT NULL,
                member_name TEXT NOT NULL,
                nationality TEXT,
                ethnicity TEXT,
                local_expat TEXT,
                gender TEXT,
                age INTEGER DEFAULT 0,
                committee_name TEXT,
                committee_role TEXT,
                committee_meetings_attended INTEGER DEFAULT 0,
                committee_retainer_fee REAL DEFAULT 0,
                committee_allowances REAL DEFAULT 0,
                committee_total_fee REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(fact_id, member_name, committee_name)
            );
        """)

    def _migrate(self):
        """Add columns introduced after initial schema. Idempotent."""
        migrations = [
            "ALTER TABLE board_directors ADD COLUMN assembly_fee REAL DEFAULT 0",
        ]
        for sql in migrations:
            try:
                self._conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists

    def _serialize_row(self, row: dict) -> dict:
        """Serialize dict/list values to JSON strings for storage."""
        out = {}
        for k, v in row.items():
            if k in self._JSON_COLUMNS and isinstance(v, (dict, list)):
                out[k] = json.dumps(v)
            else:
                out[k] = v
        return out

    def _deserialize_row(self, row: sqlite3.Row) -> dict:
        """Deserialize JSON string columns back to dicts/lists."""
        d = dict(row)
        for k in self._JSON_COLUMNS:
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    def select(self, table: str, columns: str, filters: dict, limit: int | None = None) -> list[dict]:
        cols = columns if columns != "*" else "*"
        where_parts = [f"{col} = ?" for col in filters]
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        sql = f"SELECT {cols} FROM {table} WHERE {where_clause}"
        if limit:
            sql += f" LIMIT {limit}"
        cursor = self._conn.execute(sql, list(filters.values()))
        return [self._deserialize_row(r) for r in cursor.fetchall()]

    def insert(self, table: str, row: dict) -> list[dict]:
        row = self._serialize_row(row)
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        cursor = self._conn.execute(sql, list(row.values()))
        self._conn.commit()
        row_id = cursor.lastrowid
        return [{"id": row_id, **row}]

    def upsert(self, table: str, rows: list[dict] | dict, on_conflict: str) -> list[dict]:
        if isinstance(rows, dict):
            rows = [rows]
        results = []
        conflict_cols = on_conflict.split(",")
        for row in rows:
            row = self._serialize_row(row)
            cols = list(row.keys())
            placeholders = ", ".join("?" for _ in cols)
            update_parts = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in conflict_cols)
            sql = (
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
                f" ON CONFLICT({on_conflict}) DO UPDATE SET {update_parts}"
            )
            cursor = self._conn.execute(sql, list(row.values()))
            self._conn.commit()
            # Fetch the upserted row
            where = " AND ".join(f"{c} = ?" for c in conflict_cols)
            vals = [row[c] for c in conflict_cols]
            fetched = self._conn.execute(f"SELECT * FROM {table} WHERE {where}", vals).fetchone()
            if fetched:
                results.append(self._deserialize_row(fetched))
            else:
                results.append({"id": cursor.lastrowid, **row})
        return results


def get_db(test_mode: bool | None = None) -> SupabaseDB | SQLiteDB:
    """Factory: return SQLiteDB in test mode, SupabaseDB otherwise."""
    if test_mode is None:
        test_mode = settings.TEST_MODE
    return SQLiteDB() if test_mode else SupabaseDB()
