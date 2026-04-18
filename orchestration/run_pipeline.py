#!/usr/bin/env python3
"""Main pipeline orchestrator for corporate annual report extraction.

Execution order:
  1. Fetch markdown from landing_parse_cache              (sequential)
  2. Extract company + financials → upsert companies/facts (sequential)
  3. Extract board directors  ┐
     Extract board committees ┘  (parallel — both need fact_id from step 2)

Every invocation writes a row to the `extraction_runs` ledger (Supabase only)
so failed records can be queried and re-run later via `run_batch.py --status failed`.

Usage:
    python orchestration/run_pipeline.py --record-id 84
    python orchestration/run_pipeline.py --record-id 84 --test
"""

import argparse
import asyncio
import sys
from pathlib import Path

import structlog

# Ensure project root is on the path regardless of where the script is invoked from
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from config.db import get_db
from config.logging import configure_logging
from execution import run_ledger
from execution.extract_committees import extract_committees
from execution.extract_company import extract_company
from execution.extract_directors import extract_directors
from execution.fetch_markdown import fetch_markdown
from execution.llm_client import run_token_totals
from execution.validate import ExtractionValidationError

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Parallel step: directors + committees
# ---------------------------------------------------------------------------

async def _run_parallel(markdown: str, fact_id: int, db) -> dict:
    """Run directors and committees extractions concurrently."""
    directors_task = asyncio.create_task(extract_directors(markdown, fact_id, db=db))
    committees_task = asyncio.create_task(extract_committees(markdown, fact_id, db=db))

    directors_result, committees_result = await asyncio.gather(directors_task, committees_task)

    directors_rows = directors_result["rows"]
    committees_rows = committees_result["rows"]
    warnings = directors_result["warnings"] + committees_result["warnings"]

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
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(record_id: int, force: bool = False, test_mode: bool = False) -> dict:
    """Execute the full extraction pipeline for a single cache record.

    Returns a summary dict with counts and IDs. Never raises — every outcome
    (success, skipped, failed) is reflected in the returned dict and in the
    run ledger.
    """
    db = get_db(test_mode=test_mode)
    year = settings.YEAR
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(record_id=record_id, year=year)
    log.info("pipeline_start", version=settings.APP_VERSION, test_mode=test_mode)

    # Idempotency — skip if a successful run already exists for (record_id, year)
    if not force and run_ledger.has_success(db, record_id, year):
        log.info("pipeline_skipped", reason="already_processed")
        return {"record_id": record_id, "status": "skipped", "reason": "already_processed"}

    attempt = run_ledger.last_attempt(db, record_id, year) + 1
    token_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "models": set()}
    token_totals_token = run_token_totals.set(token_totals)

    ledger_id: int | None = None
    step = "start"
    try:
        # Step 1 — fetch markdown
        step = "fetch"
        log.info("pipeline_step", step="1/3", action="fetch_markdown")
        record = fetch_markdown(record_id, db=db)
        markdown = record["markdown_llm_clean"]
        document_name = record.get("document_name", f"record_{record_id}")
        workflow_run_id = record.get("workflow_run_id")
        log.info("markdown_fetched", document=document_name, chars=len(markdown))

        ledger_id = run_ledger.start_run(
            db, record_id=record_id, year=year,
            workflow_run_id=workflow_run_id, attempt=attempt,
        )
        structlog.contextvars.bind_contextvars(ledger_id=ledger_id, attempt=attempt)

        # Step 2 — company extraction (sequential; fact_id needed for step 3)
        step = "company"
        log.info("pipeline_step", step="2/3", action="extract_company")
        company_result = await extract_company(markdown, workflow_run_id, db=db)
        company_id = company_result["company_id"]
        fact_id = company_result["fact_id"]
        company_name = company_result["extracted"]["company"]["company_name"]["value"]
        fact_year = company_result["extracted"]["financials"]["year"]
        log.info("company_extracted", company_id=company_id, fact_id=fact_id,
                 company=company_name, fact_year=fact_year)

        # Step 3 — directors + committees in parallel
        step = "directors_committees"
        log.info("pipeline_step", step="3/3", action="extract_directors_committees")
        parallel_result = await _run_parallel(markdown, fact_id, db)
        log.info("parallel_extracted",
                 directors=parallel_result["directors_inserted"],
                 committees=parallel_result["committees_inserted"],
                 name_mismatches=parallel_result["name_mismatches"])

        # Collect all quality warnings across all three extractions
        all_warnings = (
            company_result["warnings"]
            + parallel_result["warnings"]
        )
        if all_warnings:
            log.warning("pipeline_quality_warnings", count=len(all_warnings))
        warning_message = ("WARNINGS: " + "; ".join(all_warnings[:20])) if all_warnings else None

        # Success → finalize ledger with token totals and any quality warnings
        run_ledger.finish_run(
            db, ledger_id, "success",
            step=None, error_class=None, error_message=warning_message,
            model=",".join(sorted(token_totals["models"])) or None,
            prompt_tokens=token_totals["prompt_tokens"] or None,
            completion_tokens=token_totals["completion_tokens"] or None,
            total_tokens=token_totals["total_tokens"] or None,
        )

        summary = {
            "record_id": record_id,
            "document_name": document_name,
            "company_id": company_id,
            "fact_id": fact_id,
            "company_name": company_name,
            "fact_year": fact_year,
            "directors_inserted": parallel_result["directors_inserted"],
            "committees_inserted": parallel_result["committees_inserted"],
            "name_mismatches": parallel_result["name_mismatches"],
            "quality_warnings": len(all_warnings),
            "total_tokens": token_totals["total_tokens"],
            "status": "success",
        }
        log.info("pipeline_done", **{k: v for k, v in summary.items()})
        return summary

    except ExtractionValidationError as exc:
        log.error("pipeline_failed", step=step,
                  error_class="ExtractionValidationError", error_message=str(exc))
        run_ledger.finish_run(
            db, ledger_id, "failed",
            step=step, error_class="ExtractionValidationError", error_message=str(exc),
        )
        return {"record_id": record_id, "status": "failed", "step": step,
                "error_class": "ExtractionValidationError", "error_message": str(exc)}

    except Exception as exc:
        log.exception("pipeline_failed", step=step,
                      error_class=type(exc).__name__, error_message=str(exc))
        run_ledger.finish_run(
            db, ledger_id, "failed",
            step=step, error_class=type(exc).__name__, error_message=str(exc),
        )
        return {"record_id": record_id, "status": "failed", "step": step,
                "error_class": type(exc).__name__, "error_message": str(exc)}

    finally:
        run_token_totals.reset(token_totals_token)
        structlog.contextvars.clear_contextvars()


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
    except KeyboardInterrupt:
        log.info("pipeline_interrupted")
        sys.exit(130)

    sys.exit(0 if summary.get("status") in ("success", "skipped") else 1)
