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
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

# Ensure project root is on the path regardless of where the script is invoked from
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from config.db import get_db
from config.logging import configure_logging
from execution.extract_committees import extract_committees
from execution.extract_company import extract_company
from execution.extract_directors import extract_directors
from execution.fetch_markdown import fetch_markdown

log = structlog.get_logger()


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
        log.warning("name_crossref_mismatch",
                    count=len(name_mismatches), names=name_mismatches)

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
    log.info("pipeline_start", record_id=record_id, test_mode=test_mode)

    # Step 1 — fetch markdown (always from Supabase)
    log.info("pipeline_step", step="1/3", action="fetch_markdown")
    record = fetch_markdown(record_id)
    markdown = record["markdown_llm_clean"]
    document_name = record.get("document_name", f"record_{record_id}")
    workflow_run_id = record.get("workflow_run_id")
    log.info("markdown_fetched", document=document_name, chars=len(markdown))

    # Idempotency check — skip if this workflow_run_id was already processed
    if not force and workflow_run_id and _already_processed(workflow_run_id, db):
        log.info("pipeline_skipped", reason="already_processed",
                 workflow_run_id=workflow_run_id)
        return {
            "record_id": record_id,
            "document_name": document_name,
            "workflow_run_id": workflow_run_id,
            "status": "skipped",
            "reason": "already_processed",
        }

    # Step 2 — company extraction (sequential; fact_id needed for step 3)
    log.info("pipeline_step", step="2/3", action="extract_company")
    company_result = await extract_company(markdown, workflow_run_id, db=db)
    company_id = company_result["company_id"]
    fact_id = company_result["fact_id"]
    company_name = company_result["extracted"]["company"]["company_name"]["value"]
    year = company_result["extracted"]["financials"]["year"]
    log.info("company_extracted", company_id=company_id, fact_id=fact_id,
             company=company_name, year=year)

    # Step 3 — directors + committees in parallel
    log.info("pipeline_step", step="3/3", action="extract_directors_committees")
    parallel_result = await _run_parallel(markdown, fact_id, db)
    log.info("parallel_extracted",
             directors=parallel_result["directors_inserted"],
             committees=parallel_result["committees_inserted"],
             name_mismatches=parallel_result["name_mismatches"])

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

    log.info("pipeline_done", **{k: v for k, v in summary.items() if k != "mismatched_names"})
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    configure_logging()

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
        log.info("pipeline_interrupted")
        sys.exit(1)
    except Exception:
        log.exception("pipeline_failed")
        sys.exit(1)
