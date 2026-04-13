#!/usr/bin/env python3
"""Extract company identification and financial metrics from markdown via OpenRouter.

Flow:
  1. Call LLM with COMPANY_SYSTEM_PROMPT + COMPANY_USER_PROMPT
  2. Validate response against COMPANY_SCHEMA
  3. Get or create row in `companies` table
  4. Upsert row in `company_facts` table
  5. Return {company_id, fact_id, extracted}

Standalone usage:
    python execution/extract_company.py --record-id 84
"""

import argparse
import asyncio
import json
import re
import sys

import jsonschema
import structlog

from config import prompts, schemas, settings
from config.db import get_db
from execution.fetch_markdown import fetch_markdown
from execution.llm_client import call_llm, parse_json_response

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def _format_company_code(name: str) -> str:
    """Convert display name to a stable snake_case code for deduplication."""
    return re.sub(r"[^a-z0-9_]", "", name.lower().strip().replace(" ", "_"))


def _get_or_create_company(extracted: dict, db) -> int:
    """Return the ID of the matching company, creating it if absent."""
    company = extracted["company"]
    company_name_value = company["company_name"]["value"]
    company_code = _format_company_code(company_name_value)

    existing = db.select(settings.TABLE_COMPANIES, "id", {"company_code": company_code}, limit=1)
    if existing:
        return existing[0]["id"]

    row = {
        "company_name": company["company_name"],
        "exchange": company["exchange"],
        "country": company["country"],
        "industry": company["industry"],
        "source_document_url": company.get("source_document_url") or "",
        "company_code": company_code,
    }
    result = db.insert(settings.TABLE_COMPANIES, row)
    return result[0]["id"]


def _upsert_company_fact(company_id: int, extracted: dict, workflow_run_id: str | None, db) -> int:
    """Upsert company_facts row for (company_id, year). Returns fact ID."""
    fin = extracted["financials"]
    row = {
        "company_id": company_id,
        "year": fin["year"],
        "revenue": fin["revenue"],
        "profit_net": fin["profit_net"],
        "market_capitalisation": fin.get("market_capitalisation"),
        "employees": fin.get("employees"),
        "extraction_run_id": workflow_run_id,
    }
    result = db.upsert(settings.TABLE_COMPANY_FACTS, row, on_conflict="company_id,year")
    return result[0]["id"]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def extract_company(markdown: str, workflow_run_id: str | None = None, db=None) -> dict:
    """Run company extraction and persist to DB.

    Args:
        markdown: The markdown text to extract from.
        workflow_run_id: The workflow_run_id from landing_parse_cache.
        db: Database instance (SupabaseDB or SQLiteDB). Auto-created if None.

    Returns:
        {"company_id": int, "fact_id": int, "extracted": dict}
    """
    if db is None:
        db = get_db()

    raw = await call_llm(
        prompts.COMPANY_SYSTEM_PROMPT,
        prompts.COMPANY_USER_PROMPT.format(markdown=markdown),
        model=settings.COMPANY_MODEL,
        temperature=settings.COMPANY_TEMPERATURE,
        task="company",
    )
    extracted = parse_json_response(raw)

    try:
        jsonschema.validate(extracted, schemas.COMPANY_SCHEMA)
    except jsonschema.ValidationError as exc:
        log.warning("schema_validation_failed", task="company", error=exc.message)

    company_id = _get_or_create_company(extracted, db)
    fact_id = _upsert_company_fact(company_id, extracted, workflow_run_id, db)

    return {"company_id": company_id, "fact_id": fact_id, "extracted": extracted}


if __name__ == "__main__":
    from config.logging import configure_logging
    configure_logging()

    parser = argparse.ArgumentParser(description="Extract company data and write to DB")
    parser.add_argument("--record-id", type=int, default=settings.CACHE_RECORD_ID)
    parser.add_argument("--test", action="store_true", help="Use local SQLite instead of Supabase")
    args = parser.parse_args()

    try:
        db = get_db(test_mode=args.test)
        record = fetch_markdown(args.record_id)
        result = asyncio.run(extract_company(record["markdown_llm_clean"], record.get("workflow_run_id"), db=db))
        print(
            json.dumps(
                {
                    "company_id": result["company_id"],
                    "fact_id": result["fact_id"],
                    "company_name": result["extracted"]["company"]["company_name"]["value"],
                    "year": result["extracted"]["financials"]["year"],
                },
                indent=2,
            )
        )
    except Exception as exc:
        log.error("company_extraction_failed", error=str(exc))
        sys.exit(1)
