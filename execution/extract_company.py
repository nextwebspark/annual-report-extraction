#!/usr/bin/env python3
"""Extract company identification and financial metrics from markdown via OpenRouter.

Flow:
  1. Call Claude Opus with COMPANY_EXTRACTION_PROMPT
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
from openai import AsyncOpenAI

from config import prompts, schemas, settings
from config.db import get_db
from execution.fetch_markdown import fetch_markdown


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

async def _call_llm(markdown: str, max_retries: int = 3) -> dict:
    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    prompt_text = prompts.COMPANY_EXTRACTION_PROMPT.format(markdown=markdown)
    for attempt in range(1, max_retries + 1):
        response = await client.chat.completions.create(
            model=settings.COMPANY_MODEL,
            temperature=settings.COMPANY_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt_text}],
        )
        raw = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        if raw:
            break
        if attempt < max_retries:
            wait = 2 ** attempt
            print(f"[WARN] Company LLM returned empty response (attempt {attempt}/{max_retries}, finish_reason={finish_reason}). Retrying in {wait}s...", file=sys.stderr)
            await asyncio.sleep(wait)
        else:
            raise RuntimeError(f"LLM returned empty response after {max_retries} attempts. finish_reason={finish_reason}")
    if finish_reason != "stop":
        print(f"[WARN] Company LLM response may be truncated (finish_reason={finish_reason}). Last 200 chars: ...{raw[-200:]}", file=sys.stderr)
    print(f"[INFO] Company LLM response: {len(raw)} chars, finish_reason={finish_reason}", file=sys.stderr)
    return _parse_json(raw)


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM response, extracting from markdown fences if needed."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    for start_char in ['{', '[']:
        idx = text.rfind(start_char)
        while idx >= 0:
            try:
                return json.loads(text[idx:])
            except json.JSONDecodeError:
                idx = text.rfind(start_char, 0, idx)
    print(f"[WARN] Could not parse LLM response as JSON.\n  First 300 chars: {text[:300]}\n  Last 300 chars: ...{text[-300:]}", file=sys.stderr)
    raise json.JSONDecodeError("No valid JSON found in LLM response", text, 0)


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

    extracted = await _call_llm(markdown)

    try:
        jsonschema.validate(extracted, schemas.COMPANY_SCHEMA)
    except jsonschema.ValidationError as exc:
        print(f"[WARN] Company schema validation warning: {exc.message}", file=sys.stderr)

    company_id = _get_or_create_company(extracted, db)
    fact_id = _upsert_company_fact(company_id, extracted, workflow_run_id, db)

    return {"company_id": company_id, "fact_id": fact_id, "extracted": extracted}


if __name__ == "__main__":
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
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
