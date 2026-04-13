#!/usr/bin/env python3
"""Extract board directors from markdown via OpenRouter, then write to board_directors table.

Flow:
  1. Call LLM with DIRECTORS_SYSTEM_PROMPT + DIRECTORS_USER_PROMPT
  2. Validate response against DIRECTORS_SCHEMA + strict validation
  3. Inject fact_id into every record
  4. Upsert all directors
  5. Return list of inserted rows

Standalone usage:
    python execution/extract_directors.py --record-id 84 --fact-id 12
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
from execution.validate import validate_directors_strict, validate_directors_soft

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Response parsing (directors-specific)
# ---------------------------------------------------------------------------

def _parse_directors_response(text: str) -> list[dict]:
    """Parse directors from LLM response, handling both wrapper and plain array formats."""
    result = parse_json_response(text)
    # Wrapper format: {"directors": [...], "extraction_metadata": {...}}
    if isinstance(result, dict):
        if "directors" in result:
            directors = result["directors"]
            if meta := result.get("extraction_metadata"):
                notes = meta.get("extraction_notes", "")
                if notes:
                    log.info("extraction_notes", task="directors", notes=notes)
                for conflict in meta.get("conflicts", []):
                    log.info("extraction_conflict", task="directors", conflict=conflict)
            if not isinstance(directors, list):
                raise ValueError(f"Expected 'directors' to be a list, got {type(directors).__name__}")
            return directors
        raise ValueError(f"Expected 'directors' key in response object, got keys: {list(result.keys())}")
    # Legacy plain array format
    if isinstance(result, list):
        return result
    raise ValueError(f"Expected JSON object or array from LLM, got {type(result).__name__}")


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def _save_directors(fact_id: int, directors: list[dict], db) -> list[dict]:
    rows = [{**d, "fact_id": fact_id} for d in directors]
    return db.upsert(settings.TABLE_BOARD_DIRECTORS, rows, on_conflict="fact_id,director_name")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def extract_directors(markdown: str, fact_id: int, db=None) -> list[dict]:
    """Run board directors extraction and persist to DB.

    Args:
        markdown: Cleaned markdown text from landing_parse_cache.
        fact_id:  ID of the corresponding company_facts row.
        db:       Database instance (SupabaseDB or SQLiteDB). Auto-created if None.

    Returns:
        List of inserted board_directors rows.
    """
    if db is None:
        db = get_db()

    raw = await call_llm(
        prompts.DIRECTORS_SYSTEM_PROMPT,
        prompts.DIRECTORS_USER_PROMPT.format(markdown=markdown),
        model=settings.DIRECTORS_MODEL,
        temperature=settings.DIRECTORS_TEMPERATURE,
        task="directors",
    )
    directors = _parse_directors_response(raw)

    try:
        jsonschema.validate(directors, schemas.DIRECTORS_SCHEMA)
    except jsonschema.ValidationError as exc:
        log.warning("schema_validation_failed", task="directors", error=exc.message)

    errors = validate_directors_strict(directors)
    if errors:
        log.warning("strict_validation_issues", task="directors", count=len(errors), errors=errors)

    for w in validate_directors_soft(directors):
        log.warning("soft_validation", task="directors", issue=w)

    inserted = _save_directors(fact_id, directors, db)
    return inserted


if __name__ == "__main__":
    from config.logging import configure_logging
    configure_logging()

    parser = argparse.ArgumentParser(description="Extract board directors and write to DB")
    parser.add_argument("--record-id", type=int, default=settings.CACHE_RECORD_ID)
    parser.add_argument("--fact-id", type=int, required=True, help="company_facts row ID")
    parser.add_argument("--test", action="store_true", help="Use local SQLite instead of Supabase")
    args = parser.parse_args()

    try:
        db = get_db(test_mode=args.test)
        record = fetch_markdown(args.record_id)
        rows = asyncio.run(extract_directors(record["markdown_llm_clean"], args.fact_id, db=db))
        print(json.dumps({"directors_inserted": len(rows)}, indent=2))
    except Exception as exc:
        log.error("directors_extraction_failed", error=str(exc))
        sys.exit(1)
