#!/usr/bin/env python3
"""Extract board committee memberships from markdown via OpenRouter, then write to board_committees.

Flow:
  1. Call LLM with COMMITTEES_SYSTEM_PROMPT + COMMITTEES_USER_PROMPT
  2. Validate response against COMMITTEES_SCHEMA + strict validation
  3. Inject fact_id into every record
  4. Upsert all committee memberships
  5. Return list of inserted rows

Note: one person in two committees = two separate records.

Standalone usage:
    python execution/extract_committees.py --record-id 84 --fact-id 12
"""

import argparse
import asyncio
import json
import sys

import jsonschema
import structlog

from config import prompts, schemas, settings
from config.db import get_db
from execution.fetch_markdown import fetch_markdown
from execution.llm_client import call_llm, parse_json_response
from execution.validate import (
    ExtractionValidationError,
    validate_committees_soft,
    validate_committees_strict,
)

log = structlog.get_logger()

# DB fields to keep from LLM response (strip any extras)
_DB_FIELDS = {
    "fact_id", "member_name", "nationality", "ethnicity", "local_expat",
    "gender", "age", "committee_name", "committee_role",
    "committee_meetings_attended", "committee_retainer_fee",
    "committee_allowances", "committee_total_fee",
}


# ---------------------------------------------------------------------------
# Response parsing (committees-specific)
# ---------------------------------------------------------------------------

def _parse_committees_response(text: str) -> list[dict]:
    """Parse committees from LLM response, handling both wrapper and plain array formats."""
    result = parse_json_response(text)
    # Wrapper format: {"committee_memberships": [...], "extraction_metadata": {...}}
    if isinstance(result, dict):
        if "committee_memberships" in result:
            memberships = result["committee_memberships"]
            if meta := result.get("extraction_metadata"):
                notes = meta.get("extraction_notes", "")
                if notes:
                    log.info("extraction_notes", task="committees", notes=notes)
                for conflict in meta.get("conflicts", []):
                    log.info("extraction_conflict", task="committees", conflict=conflict)
            if not isinstance(memberships, list):
                raise ValueError(f"Expected 'committee_memberships' to be a list, got {type(memberships).__name__}")
            return [{k: v for k, v in m.items() if k in _DB_FIELDS} for m in memberships]
        raise ValueError(f"Expected 'committee_memberships' key in response object, got keys: {list(result.keys())}")
    # Legacy plain array format
    if isinstance(result, list):
        return result
    raise ValueError(f"Expected JSON object or array from LLM, got {type(result).__name__}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def extract_committees(markdown: str, fact_id: int, db=None) -> list[dict]:
    """Run board committees extraction and persist to DB.

    Args:
        markdown: Cleaned markdown text from landing_parse_cache.
        fact_id:  ID of the corresponding company_facts row.
        db:       Database instance (SupabaseDB or SQLiteDB). Auto-created if None.

    Returns:
        {"rows": list[dict], "warnings": list[str]}
    """
    if db is None:
        db = get_db()

    def _validate(raw: str) -> None:
        rows = [{**c, "fact_id": fact_id} for c in _parse_committees_response(raw)]
        try:
            jsonschema.validate(rows, schemas.COMMITTEES_SCHEMA)
        except jsonschema.ValidationError as exc:
            log.error("schema_validation_failed", task="committees", error=exc.message)
            raise

    raw = await call_llm(
        prompts.COMMITTEES_SYSTEM_PROMPT,
        prompts.COMMITTEES_USER_PROMPT.format(markdown=markdown),
        model=settings.COMMITTEES_MODEL,
        temperature=settings.COMMITTEES_TEMPERATURE,
        task="committees",
        validate_fn=_validate,
    )
    committees = _parse_committees_response(raw)
    rows = [{**c, "fact_id": fact_id} for c in committees]

    errors = validate_committees_strict(rows)
    if errors:
        log.error("strict_validation_failed", task="committees", count=len(errors), errors=errors)
        raise ExtractionValidationError("committees", errors)

    soft_warnings = validate_committees_soft(rows)
    for w in soft_warnings:
        log.warning("soft_validation", task="committees", issue=w)

    inserted = db.upsert(settings.TABLE_BOARD_COMMITTEES, rows, on_conflict="fact_id,member_name,committee_name")
    return {"rows": inserted, "warnings": soft_warnings}


if __name__ == "__main__":
    from config.logging import configure_logging
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Extract board committee memberships and write to DB"
    )
    parser.add_argument("--record-id", type=int, default=settings.CACHE_RECORD_ID)
    parser.add_argument("--fact-id", type=int, required=True, help="company_facts row ID")
    parser.add_argument("--test", action="store_true", help="Use local SQLite instead of Supabase")
    args = parser.parse_args()

    try:
        db = get_db(test_mode=args.test)
        record = fetch_markdown(args.record_id)
        result = asyncio.run(extract_committees(record["markdown_llm_clean"], args.fact_id, db=db))
        print(json.dumps({"committees_inserted": len(result["rows"]), "warnings": result["warnings"]}, indent=2))
    except Exception as exc:
        log.error("committees_extraction_failed", error=str(exc))
        sys.exit(1)
