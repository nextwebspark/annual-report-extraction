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
from config.normalization import normalize_exchange
from config.db import get_db
from execution.fetch_markdown import fetch_markdown
from execution.llm_client import call_llm, parse_json_response
from execution.validate import validate_company_warnings

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Band classification
# ---------------------------------------------------------------------------

_REVENUE_BANDS = [
    (1, "Small",      0,                   50_000_000),
    (2, "Mid-Market", 50_000_000,          250_000_000),
    (3, "Large",      250_000_000,         1_000_000_000),
    (4, "Major",      1_000_000_000,       5_000_000_000),
    (5, "Enterprise", 5_000_000_000,       20_000_000_000),
    (6, "Mega",       20_000_000_000,      None),
]

_EMPLOYEE_BANDS = [
    (1, "Small",      0,      250),
    (2, "Mid-Market", 250,    1_000),
    (3, "Large",      1_000,  5_000),
    (4, "Major",      5_000,  20_000),
    (5, "Enterprise", 20_000, None),
]


def _classify_band(value: float | int, bands: list) -> tuple[int, str] | tuple[None, None]:
    """Return (band_number, label) for value, or (None, None) if value is None."""
    if value is None:
        return None, None
    for band, label, low, high in bands:
        if value >= low and (high is None or value < high):
            return band, label
    return None, None


# ---------------------------------------------------------------------------
# Unit normalization
# ---------------------------------------------------------------------------

_UNIT_MULTIPLIERS = {
    "actual": 1,
    "hundred": 100,
    "thousand": 1_000,
    "ten_thousand": 10_000,
    "hundred_thousand": 100_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "trillion": 1_000_000_000_000,
}


def _apply_unit_multipliers(financials: dict) -> None:
    """Multiply value by unit_stated multiplier in-place. Removes unit_stated after conversion."""
    for field in ("revenue", "profit_net", "market_capitalisation"):
        obj = financials.get(field)
        if not obj or not isinstance(obj, dict):
            continue
        unit = obj.pop("unit_stated", "actual") or "actual"
        multiplier = _UNIT_MULTIPLIERS.get(unit, 1)
        if multiplier != 1 and obj.get("value") is not None:
            obj["value"] = obj["value"] * multiplier


# ---------------------------------------------------------------------------
# Company field normalization
# ---------------------------------------------------------------------------

def _normalize_company_fields(extracted: dict) -> None:
    """Normalize exchange → MIC code. Coerce empty objects to null for optional fields."""
    company = extracted["company"]

    exc = company.get("exchange", {})
    if exc and exc.get("value"):
        exc["value"] = normalize_exchange(exc["value"])

    fin = extracted.get("financials", {})
    for field in ("market_capitalisation", "employees"):
        if fin.get(field) == {}:
            fin[field] = None


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

_FUZZY_MATCH_THRESHOLD = 90  # minimum similarity score (0–100) to treat as same company


def _company_code(name: str) -> str:
    """Stable snake_case key used for exact and fuzzy deduplication."""
    return re.sub(r"[^a-z0-9_]", "", name.lower().strip().replace(" ", "_"))


def _get_or_create_company(extracted: dict, db) -> int:
    """Return the ID of the matching company, creating it if absent.

    Lookup order:
      1. Exact match on company_code (fast path — no extra query in normal operation).
      2. Fuzzy match against all existing codes (catches LLM name drift, e.g.
         "Saudi Aramco" vs "Saudi Aramco Co."). Logs a warning so drift is visible.
      3. Insert new company row.
    """
    from rapidfuzz import process, fuzz

    company = extracted["company"]
    name_value = company["company_name"]["value"]
    code = _company_code(name_value)

    # 1. Exact match
    hit = db.select(settings.TABLE_COMPANIES, "id,company_code", {"company_code": code}, limit=1)
    if hit:
        return hit[0]["id"]

    # 2. Fuzzy match (only pays the cost of a full-table fetch on a cache miss)
    all_rows = db.select(settings.TABLE_COMPANIES, "id,company_code", {})
    if all_rows:
        codes = [r["company_code"] for r in all_rows]
        match = process.extractOne(code, codes, scorer=fuzz.partial_ratio)
        if match and match[1] >= _FUZZY_MATCH_THRESHOLD:
            matched_code, score, idx = match
            log.warning(
                "company_fuzzy_matched",
                llm_name=name_value,
                llm_code=code,
                matched_code=matched_code,
                score=score,
            )
            return all_rows[idx]["id"]

    # 3. New company
    row = {
        "company_name": company["company_name"],
        "exchange": company["exchange"],
        "country": company["country"],
        "sector": company["sector"],
        "sub_sector": company["sub_sector"],
        "source_document_url": company.get("source_document_url") or "",
        "company_code": code,
    }
    return db.insert(settings.TABLE_COMPANIES, row)[0]["id"]


def _upsert_company_fact(company_id: int, extracted: dict, workflow_run_id: str | None, db) -> int:
    """Upsert company_facts row for (company_id, year). Returns fact ID."""
    fin = extracted["financials"]

    revenue_val = (fin["revenue"] or {}).get("value")
    revenue_band, revenue_label = _classify_band(revenue_val, _REVENUE_BANDS)

    employees_val = (fin.get("employees") or {}).get("value")
    employee_band, employee_label = _classify_band(employees_val, _EMPLOYEE_BANDS)

    row = {
        "company_id": company_id,
        "year": fin["year"],
        "revenue": fin["revenue"],
        "profit_net": fin["profit_net"],
        "market_capitalisation": fin.get("market_capitalisation"),
        "employees": fin.get("employees"),
        "revenue_band": revenue_band,
        "revenue_band_label": revenue_label,
        "employee_band": employee_band,
        "employee_band_label": employee_label,
        "extraction_run_id": workflow_run_id,
        "data_version": settings.APP_VERSION,
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
        {"company_id": int, "fact_id": int, "extracted": dict, "warnings": list[str]}
    """
    if db is None:
        db = get_db()

    def _validate(raw: str) -> None:
        """Pre-normalization schema check used by call_llm retry loop.
        Coerces {} → null for optional fields before validating so the LLM
        returning an empty object doesn't cause an unnecessary retry."""
        data = parse_json_response(raw)
        fin = data.get("financials", {})
        for field in ("market_capitalisation", "employees"):
            if fin.get(field) == {}:
                fin[field] = None
        try:
            jsonschema.validate(data, schemas.COMPANY_SCHEMA)
        except jsonschema.ValidationError as exc:
            log.error("schema_validation_failed", task="company", error=exc.message)
            raise

    raw = await call_llm(
        prompts.COMPANY_SYSTEM_PROMPT,
        prompts.COMPANY_USER_PROMPT.format(markdown=markdown),
        model=settings.COMPANY_MODEL,
        temperature=settings.COMPANY_TEMPERATURE,
        task="company",
        validate_fn=_validate,
    )
    extracted = parse_json_response(raw)

    _apply_unit_multipliers(extracted["financials"])
    _normalize_company_fields(extracted)

    # Re-validate after normalization (also catches failures when call_llm is mocked in tests)
    try:
        jsonschema.validate(extracted, schemas.COMPANY_SCHEMA)
    except jsonschema.ValidationError as exc:
        log.error("schema_validation_failed", task="company", error=exc.message)
        raise

    warnings = validate_company_warnings(extracted)
    for w in warnings:
        log.warning("company_quality_warning", warning=w)

    company_id = _get_or_create_company(extracted, db)
    fact_id = _upsert_company_fact(company_id, extracted, workflow_run_id, db)

    return {"company_id": company_id, "fact_id": fact_id, "extracted": extracted, "warnings": warnings}


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
