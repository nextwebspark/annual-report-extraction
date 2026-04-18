"""Run ledger helpers for the extraction pipeline.

The ledger (`extraction_runs` table in Supabase) is the ops view of every
pipeline invocation: which records ran, which failed, token usage, step where
the failure occurred.

Ledger operations are Supabase-only. When running with `--test` (SQLiteDB)
these helpers are no-ops so local/unit-test flows work unchanged.
"""

from datetime import datetime, timezone

from config import settings
from config.db import SupabaseDB


def _is_supabase(db) -> bool:
    return isinstance(db, SupabaseDB)


def start_run(
    db,
    *,
    record_id: int,
    year: int,
    workflow_run_id: str | None,
    attempt: int = 1,
) -> int | None:
    """Insert a `pending` ledger row. Returns ledger id, or None in test mode."""
    if not _is_supabase(db):
        return None
    row = db.insert(
        settings.TABLE_EXTRACTION_RUNS,
        {
            "landing_cache_record_id": record_id,
            "year": year,
            "workflow_run_id": workflow_run_id,
            "status": "pending",
            "attempt": attempt,
        },
    )
    return row[0]["id"]


def finish_run(db, ledger_id: int | None, status: str, **fields) -> None:
    """Update the ledger row to a terminal status. No-op if ledger_id is None."""
    if ledger_id is None or not _is_supabase(db):
        return
    payload = {
        "status": status,
        "finished_at": datetime.now(tz=timezone.utc).isoformat(),
        **fields,
    }
    db.update(settings.TABLE_EXTRACTION_RUNS, payload, {"id": ledger_id})


def has_success(db, record_id: int, year: int) -> bool:
    """True if a `success` ledger row exists for this (record_id, year)."""
    if not _is_supabase(db):
        return False
    rows = db.select(
        settings.TABLE_EXTRACTION_RUNS,
        "id",
        {"landing_cache_record_id": record_id, "year": year, "status": "success"},
        limit=1,
    )
    return bool(rows)


def last_attempt(db, record_id: int, year: int) -> int:
    """Highest attempt number recorded for this (record_id, year). 0 if none."""
    if not _is_supabase(db):
        return 0
    rows = db.select(
        settings.TABLE_EXTRACTION_RUNS,
        "attempt",
        {"landing_cache_record_id": record_id, "year": year},
    )
    return max((r["attempt"] for r in rows), default=0)
