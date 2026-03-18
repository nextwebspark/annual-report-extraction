#!/usr/bin/env python3
"""Extract board committee memberships from markdown via OpenRouter, then write to board_committees.

Flow:
  1. Call Claude Opus with COMMITTEES_EXTRACTION_PROMPT (single pass)
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
import re
import sys

import jsonschema
from openai import AsyncOpenAI

from config import prompts, schemas, settings
from config.db import get_db
from execution.fetch_markdown import fetch_markdown
from execution.validate import validate_committees_strict, validate_committees_soft


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

async def _call_llm(markdown: str, max_retries: int = 3) -> list[dict]:
    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    prompt_text = prompts.COMMITTEES_EXTRACTION_PROMPT.format(markdown=markdown)
    for attempt in range(1, max_retries + 1):
        response = await client.chat.completions.create(
            model=settings.COMMITTEES_MODEL,
            temperature=settings.COMMITTEES_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt_text}],
        )
        raw = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        if raw:
            break
        if attempt < max_retries:
            wait = 2 ** attempt
            print(f"[WARN] Committees LLM returned empty response (attempt {attempt}/{max_retries}, finish_reason={finish_reason}). Retrying in {wait}s...", file=sys.stderr)
            await asyncio.sleep(wait)
        else:
            raise RuntimeError(f"LLM returned empty response after {max_retries} attempts. finish_reason={finish_reason}")
    if finish_reason != "stop":
        print(f"[WARN] Committees LLM response may be truncated (finish_reason={finish_reason}). Last 200 chars: ...{raw[-200:]}", file=sys.stderr)
    print(f"[INFO] Committees LLM response: {len(raw)} chars, finish_reason={finish_reason}", file=sys.stderr)
    return _parse_committees_response(raw)


def _parse_json_response(text: str):
    """Parse JSON from LLM response, extracting from markdown fences if needed."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract JSON from ```json ... ``` fences anywhere in the response
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Last resort: find the last { that starts a valid JSON block
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        # Try from the last occurrence (most likely the actual JSON, not preamble)
        idx = text.rfind(start_char)
        while idx >= 0:
            try:
                return json.loads(text[idx:])
            except json.JSONDecodeError:
                idx = text.rfind(start_char, 0, idx)
    print(f"[WARN] Could not parse LLM response as JSON.\n  First 300 chars: {text[:300]}\n  Last 300 chars: ...{text[-300:]}", file=sys.stderr)
    raise json.JSONDecodeError("No valid JSON found in LLM response", text, 0)


def _parse_committees_response(text: str) -> list[dict]:
    """Parse committees from LLM response, handling both wrapper and plain array formats."""
    result = _parse_json_response(text)
    # New wrapper format: {"committee_memberships": [...], "extraction_metadata": {...}}
    if isinstance(result, dict):
        if "committee_memberships" in result:
            memberships = result["committee_memberships"]
            if meta := result.get("extraction_metadata"):
                notes = meta.get("extraction_notes", "")
                if notes:
                    print(f"[INFO] Committees extraction notes: {notes}", file=sys.stderr)
                for conflict in meta.get("conflicts", []):
                    print(f"[INFO] Committees conflict: {conflict}", file=sys.stderr)
            if not isinstance(memberships, list):
                raise ValueError(f"Expected 'committee_memberships' to be a list, got {type(memberships).__name__}")
            # Strip fields not in the DB schema before returning
            db_fields = {
                "fact_id", "member_name", "nationality", "ethnicity", "local_expat",
                "gender", "age", "committee_name", "committee_role",
                "committee_meetings_attended", "committee_retainer_fee",
                "committee_allowances", "committee_total_fee",
            }
            return [{k: v for k, v in m.items() if k in db_fields} for m in memberships]
        raise ValueError(f"Expected 'committee_memberships' key in response object, got keys: {list(result.keys())}")
    # Legacy plain array format
    if isinstance(result, list):
        return result
    raise ValueError(f"Expected JSON object or array from LLM, got {type(result).__name__}")


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def _save_committees(fact_id: int, committees: list[dict], db) -> list[dict]:
    rows = [{**c, "fact_id": fact_id} for c in committees]
    return db.upsert(settings.TABLE_BOARD_COMMITTEES, rows, on_conflict="fact_id,member_name,committee_name")


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
        List of inserted board_committees rows.
    """
    if db is None:
        db = get_db()

    committees = await _call_llm(markdown)

    try:
        jsonschema.validate(committees, schemas.COMMITTEES_SCHEMA)
    except jsonschema.ValidationError as exc:
        print(f"[WARN] Committees schema validation warning: {exc.message}", file=sys.stderr)

    # Strict validation — log for evaluation but do not block
    errors = validate_committees_strict(committees)
    if errors:
        print(
            f"[EVAL] Committees validation issues ({len(errors)}):\n"
            + "\n".join(f"  {e}" for e in errors),
            file=sys.stderr,
        )

    # Soft validation — log warnings but proceed
    for w in validate_committees_soft(committees):
        print(f"[WARN] {w}", file=sys.stderr)

    inserted = _save_committees(fact_id, committees, db)
    return inserted


if __name__ == "__main__":
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
        rows = asyncio.run(extract_committees(record["markdown_llm_clean"], args.fact_id, db=db))
        print(json.dumps({"committees_inserted": len(rows)}, indent=2))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
