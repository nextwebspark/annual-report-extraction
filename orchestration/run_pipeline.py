#!/usr/bin/env python3
"""Main pipeline orchestrator for corporate annual report extraction.

Execution order:
  1. Fetch markdown from landing_parse_cache              (sequential)
  2. Extract company + financials → upsert companies/facts (sequential)
  3. Extract board directors  ┐
     Extract board committees ┘  (parallel — both need fact_id from step 2)

Usage:
    python orchestration/run_pipeline.py --record-id 84
    python orchestration/run_pipeline.py --record-id 84 --test
"""

import argparse
import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path regardless of where the script is invoked from
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from config.db import get_db
from execution.extract_committees import extract_committees
from execution.extract_company import extract_company
from execution.extract_directors import extract_directors
from execution.fetch_markdown import fetch_markdown


# ---------------------------------------------------------------------------
# Idempotency check
# ---------------------------------------------------------------------------

def _already_processed(workflow_run_id: str, db) -> bool:
    """Return True if company_facts already has a row for this workflow_run_id."""
    result = db.select(settings.TABLE_COMPANY_FACTS, "id",
                       {"extraction_run_id": workflow_run_id}, limit=1)
    return bool(result)


# ---------------------------------------------------------------------------
# Parallel step: directors + committees
# ---------------------------------------------------------------------------

async def _run_parallel(markdown: str, fact_id: int, db) -> dict:
    """Run directors and committees extractions concurrently."""
    directors_task = asyncio.create_task(extract_directors(markdown, fact_id, db=db))
    committees_task = asyncio.create_task(extract_committees(markdown, fact_id, db=db))

    directors_rows, committees_rows = await asyncio.gather(directors_task, committees_task)

    # Name cross-reference: warn if committee member_name not in director names
    director_names = {r["director_name"] for r in directors_rows}
    name_mismatches = [
        c["member_name"] for c in committees_rows
        if c["member_name"] not in director_names
    ]
    if name_mismatches:
        print(
            f"[WARN] {len(name_mismatches)} committee member(s) not found in directors "
            f"(may be outside-board members or name drift):",
            file=sys.stderr,
        )
        for name in name_mismatches:
            print(f"  - {name!r}", file=sys.stderr)

    return {
        "directors_inserted": len(directors_rows),
        "committees_inserted": len(committees_rows),
        "name_mismatches": len(name_mismatches),
        "mismatched_names": name_mismatches,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(record_id: int, force: bool = False, test_mode: bool = False) -> dict:
    """Execute the full extraction pipeline for a single cache record.

    Returns a summary dict with counts and IDs.
    Raises on any unrecoverable error.
    """
    db = get_db(test_mode=test_mode)
    started_at = datetime.now(tz=timezone.utc).isoformat()
    print(f"[Pipeline] Starting record_id={record_id} at {started_at}")
    if test_mode:
        print(f"[Pipeline] TEST MODE — writing to SQLite ({settings.SQLITE_DB_PATH})")

    # Step 1 — fetch markdown (always from Supabase)
    print("[Pipeline] Step 1/3 — Fetching markdown from Supabase...")
    record = fetch_markdown(record_id)
    markdown = record["markdown_llm_clean"]
    document_name = record.get("document_name", f"record_{record_id}")
    workflow_run_id = record.get("workflow_run_id")
    print(f"[Pipeline]   document: {document_name!r}  ({len(markdown):,} chars)")

    # Idempotency check — skip if this workflow_run_id was already processed
    if not force and workflow_run_id and _already_processed(workflow_run_id, db):
        print(f"[Pipeline] Already processed (workflow_run_id={workflow_run_id}). Skipping.")
        return {
            "record_id": record_id,
            "document_name": document_name,
            "workflow_run_id": workflow_run_id,
            "status": "skipped",
            "reason": "already_processed",
        }

    # Step 2 — company extraction (sequential; fact_id needed for step 3)
    print("[Pipeline] Step 2/3 — Extracting company & financials...")
    company_result = await extract_company(markdown, workflow_run_id, db=db)
    company_id = company_result["company_id"]
    fact_id = company_result["fact_id"]
    company_name = company_result["extracted"]["company"]["company_name"]["value"]
    year = company_result["extracted"]["financials"]["year"]
    print(f"[Pipeline]   company_id={company_id}  fact_id={fact_id}  {company_name!r} ({year})")

    # Step 3 — directors + committees in parallel
    print("[Pipeline] Step 3/3 — Extracting directors & committees (parallel)...")
    parallel_result = await _run_parallel(markdown, fact_id, db)
    print(
        f"[Pipeline]   directors={parallel_result['directors_inserted']}  "
        f"committees={parallel_result['committees_inserted']}  "
        f"name_mismatches={parallel_result['name_mismatches']}"
    )

    summary = {
        "record_id": record_id,
        "document_name": document_name,
        "company_id": company_id,
        "fact_id": fact_id,
        "company_name": company_name,
        "year": year,
        "directors_inserted": parallel_result["directors_inserted"],
        "committees_inserted": parallel_result["committees_inserted"],
        "name_mismatches": parallel_result["name_mismatches"],
        "mismatched_names": parallel_result["mismatched_names"],
        "started_at": started_at,
        "finished_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "success",
    }

    print(f"[Pipeline] Done. Summary:\n{json.dumps(summary, indent=2)}")
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the full annual report extraction pipeline for one cache record."
    )
    parser.add_argument(
        "--record-id",
        type=int,
        default=settings.CACHE_RECORD_ID,
        help=f"landing_parse_cache row ID (default: {settings.CACHE_RECORD_ID})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass idempotency check and re-run even if already processed",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use local SQLite instead of Supabase for writes",
    )
    args = parser.parse_args()

    try:
        summary = asyncio.run(run_pipeline(args.record_id, force=args.force, test_mode=args.test))
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n[Pipeline] Interrupted.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[Pipeline] FAILED: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
