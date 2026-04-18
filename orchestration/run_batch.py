#!/usr/bin/env python3
"""Batch runner for the annual report extraction pipeline.

Selects candidate records from `landing_parse_cache_KSA-<YEAR>` (or from the
`extraction_runs` ledger when rerunning failures), runs the pipeline on each
with bounded concurrency, and prints a JSON summary.

Usage:
    # Process every pending record for YEAR (from settings):
    python -m orchestration.run_batch

    # Cap the batch size and concurrency:
    python -m orchestration.run_batch --limit 20 --concurrency 4

    # Rerun all failed records since a date:
    python -m orchestration.run_batch --status failed --since 2026-04-01 --force

Exit code: 0 if no records failed, 1 otherwise. Skipped records do not fail the batch.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import structlog
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from config.logging import configure_logging
from orchestration.run_pipeline import run_pipeline

log = structlog.get_logger()

_CONCURRENCY_MAX = 8


def _raw_client():
    """Direct supabase client — needed for queries the DB abstraction doesn't model
    (IS NOT NULL, ordering, NOT IN). Only used by this batch runner."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def _fetch_pending_ids(limit: int | None) -> list[int]:
    """Return landing_parse_cache ids for this YEAR where markdown_llm_clean
    is populated and no successful ledger row exists."""
    client = _raw_client()

    successful_ids = {
        row["landing_cache_record_id"]
        for row in (
            client.table(settings.TABLE_EXTRACTION_RUNS)
            .select("landing_cache_record_id")
            .eq("year", settings.YEAR)
            .eq("status", "success")
            .execute()
            .data
        )
    }

    q = (
        client.table(settings.TABLE_LANDING_CACHE)
        .select("id")
        .not_.is_("markdown_llm_clean", "null")
        .order("id")
    )
    if limit:
        q = q.limit(limit + len(successful_ids))  # extra headroom before filtering

    rows = q.execute().data
    pending = [r["id"] for r in rows if r["id"] not in successful_ids]
    if limit:
        pending = pending[:limit]
    return pending


def _fetch_failed_ids(since: str | None, limit: int | None) -> list[int]:
    """Return distinct landing_cache_record_ids whose most recent run is 'failed'
    for this YEAR. When `since` is provided, restrict to started_at >= since."""
    client = _raw_client()
    q = (
        client.table(settings.TABLE_EXTRACTION_RUNS)
        .select("landing_cache_record_id, status, started_at")
        .eq("year", settings.YEAR)
        .order("started_at", desc=True)
    )
    if since:
        q = q.gte("started_at", since)
    rows = q.execute().data

    # Keep only the latest status per record_id
    latest_status: dict[int, str] = {}
    for r in rows:
        rid = r["landing_cache_record_id"]
        if rid not in latest_status:
            latest_status[rid] = r["status"]

    failed = [rid for rid, status in latest_status.items() if status == "failed"]
    if limit:
        failed = failed[:limit]
    return failed


async def _run_one(record_id: int, sem: asyncio.Semaphore, force: bool, test_mode: bool) -> dict:
    async with sem:
        try:
            return await run_pipeline(record_id, force=force, test_mode=test_mode)
        except Exception as exc:
            # run_pipeline catches and returns; this is a defensive fallback
            log.exception("batch_unexpected_error", record_id=record_id)
            return {"record_id": record_id, "status": "failed",
                    "error_class": type(exc).__name__, "error_message": str(exc)}


async def run_batch(
    *,
    status: str,
    since: str | None,
    limit: int | None,
    concurrency: int,
    force: bool,
    test_mode: bool,
) -> dict:
    # ID queries always hit Supabase (needs IS NOT NULL, ordering, ledger exclusion).
    # test_mode only affects where pipeline writes go (SQLite instead of Supabase).
    if status == "failed":
        ids = _fetch_failed_ids(since, limit)
    elif status == "pending":
        ids = _fetch_pending_ids(limit)
    else:
        raise ValueError(f"Unsupported --status value: {status}")

    log.info("batch_start", candidates=len(ids), concurrency=concurrency,
             status=status, year=settings.YEAR, force=force)

    if not ids:
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "records": []}

    sem = asyncio.Semaphore(min(concurrency, _CONCURRENCY_MAX))
    tasks = [_run_one(rid, sem, force=force, test_mode=test_mode) for rid in ids]
    results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "failed")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    summary = {
        "total": len(results),
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "records": results,
    }
    log.info("batch_done", total=summary["total"],
             success=success, failed=failed, skipped=skipped)
    return summary


def main():
    configure_logging()
    parser = argparse.ArgumentParser(description="Batch-run extraction pipeline across records.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max records to process (default: no limit)")
    parser.add_argument("--concurrency", type=int, default=4,
                        help=f"Parallel records (default 4, capped at {_CONCURRENCY_MAX})")
    parser.add_argument("--status", choices=["pending", "failed"], default="pending",
                        help="Source of record IDs (default: pending)")
    parser.add_argument("--since", type=str, default=None,
                        help="ISO8601 lower bound; only used with --status failed")
    parser.add_argument("--force", action="store_true",
                        help="Bypass per-record idempotency skip")
    parser.add_argument("--test", action="store_true",
                        help="Write output to local SQLite instead of Supabase (IDs still fetched from Supabase)")
    args = parser.parse_args()

    summary = asyncio.run(run_batch(
        status=args.status,
        since=args.since,
        limit=args.limit,
        concurrency=args.concurrency,
        force=args.force,
        test_mode=False,
    ))

    # Compact summary to stdout (records detail is already in logs/ledger)
    print(json.dumps({k: v for k, v in summary.items() if k != "records"}, indent=2))
    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
