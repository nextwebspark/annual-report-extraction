"""Unit tests for execution/extract_company.py.

call_llm is always mocked (returns raw JSON string). DB uses real SQLiteDB(":memory:").
No network calls are made.
"""

import copy
import json

import pytest
from unittest.mock import AsyncMock

from execution.extract_company import extract_company
from tests.fixtures.llm_responses import COMPANY_LLM_RESPONSE, COMPANY_LLM_RESPONSE_V2


def _raw(data) -> str:
    """Serialize data to JSON string (simulating raw LLM output)."""
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_returns_expected_keys(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    result = await extract_company("# Markdown", db=memory_db)
    assert "company_id" in result
    assert "fact_id" in result
    assert "extracted" in result


async def test_company_row_created_in_db(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    await extract_company("# Markdown", db=memory_db)

    from config import settings
    rows = memory_db.select(settings.TABLE_COMPANIES, "*", {})
    assert len(rows) == 1
    assert rows[0]["company_code"] == "acme_corp"


async def test_company_fact_row_created_in_db(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    await extract_company("# Markdown", db=memory_db)

    from config import settings
    rows = memory_db.select(settings.TABLE_COMPANY_FACTS, "*", {})
    assert len(rows) == 1
    assert rows[0]["year"] == 2023


async def test_company_not_duplicated_on_second_call(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    r1 = await extract_company("# Markdown", db=memory_db)
    r2 = await extract_company("# Markdown", db=memory_db)

    from config import settings
    rows = memory_db.select(settings.TABLE_COMPANIES, "*", {})
    assert len(rows) == 1
    assert r1["company_id"] == r2["company_id"]


async def test_company_fact_not_duplicated_on_second_call(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    await extract_company("# Markdown", db=memory_db)
    await extract_company("# Markdown", db=memory_db)

    from config import settings
    rows = memory_db.select(settings.TABLE_COMPANY_FACTS, "*", {})
    assert len(rows) == 1


async def test_company_fact_updated_on_upsert(mocker, memory_db):
    """Second run with different revenue updates the existing company_facts row."""
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        side_effect=[_raw(COMPANY_LLM_RESPONSE), _raw(COMPANY_LLM_RESPONSE_V2)],
    )
    await extract_company("# Markdown", db=memory_db)
    await extract_company("# Markdown", db=memory_db)

    from config import settings
    rows = memory_db.select(settings.TABLE_COMPANY_FACTS, "*", {})
    assert len(rows) == 1
    assert rows[0]["revenue"]["value"] == 6000000


async def test_workflow_run_id_stored(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    await extract_company("# Markdown", workflow_run_id="run-abc-123", db=memory_db)

    from config import settings
    rows = memory_db.select(settings.TABLE_COMPANY_FACTS, "*", {})
    assert rows[0]["extraction_run_id"] == "run-abc-123"


async def test_workflow_run_id_none_accepted(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    result = await extract_company("# Markdown", workflow_run_id=None, db=memory_db)
    assert result["fact_id"] is not None


async def test_returned_company_id_matches_db(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    result = await extract_company("# Markdown", db=memory_db)

    from config import settings
    rows = memory_db.select(settings.TABLE_COMPANIES, "id", {"company_code": "acme_corp"})
    assert rows[0]["id"] == result["company_id"]


# ---------------------------------------------------------------------------
# Pre-seeded company
# ---------------------------------------------------------------------------

async def test_pre_seeded_company_returns_existing_id(mocker, memory_db):
    """If a company with the same code already exists, its ID is returned."""
    from config import settings

    seed = memory_db.insert(settings.TABLE_COMPANIES, {
        "company_name": {"value": "Acme Corp", "confidence": 0.99},
        "exchange": {"value": "NYSE", "confidence": 0.99},
        "country": {"value": "United States", "confidence": 0.99},
        "industry": {"value": "Technology", "confidence": 0.99},
        "source_document_url": "",
        "company_code": "acme_corp",
    })
    seeded_id = seed[0]["id"]

    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMPANY_LLM_RESPONSE),
    )
    result = await extract_company("# Markdown", db=memory_db)
    assert result["company_id"] == seeded_id

    # Still only one companies row
    rows = memory_db.select(settings.TABLE_COMPANIES, "*", {})
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

async def test_llm_json_decode_error_propagates(mocker, memory_db):
    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value="not valid json at all {{{",
    )
    with pytest.raises(json.JSONDecodeError):
        await extract_company("# Markdown", db=memory_db)


async def test_schema_validation_failure_logs_warn_not_raise(mocker, memory_db):
    """Schema validation failure is logged but function still returns."""
    bad_response = copy.deepcopy(COMPANY_LLM_RESPONSE)
    # minLength: 1 violated — triggers jsonschema.ValidationError
    bad_response["company"]["company_name"]["value"] = ""

    mocker.patch(
        "execution.extract_company.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(bad_response),
    )
    result = await extract_company("# Markdown", db=memory_db)
    assert result["fact_id"] is not None
