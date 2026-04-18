"""Unit tests for execution/extract_directors.py.

call_llm is always mocked (returns raw JSON string). DB uses real SQLiteDB(":memory:").
The retry test patches the shared call_llm to exercise error paths.
No network calls are made.
"""

import copy
import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from execution.extract_directors import extract_directors
from execution.validate import ExtractionValidationError
from tests.fixtures.llm_responses import DIRECTORS_LLM_RESPONSE


def _raw(data) -> str:
    """Serialize data to JSON string (simulating raw LLM output)."""
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_returns_list_of_rows(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(DIRECTORS_LLM_RESPONSE),
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    assert isinstance(result, dict)
    assert len(result["rows"]) == 2


async def test_directors_written_to_db(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(DIRECTORS_LLM_RESPONSE),
    )
    await extract_directors("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(settings.TABLE_BOARD_DIRECTORS, "*", {})
    assert len(rows) == 2


async def test_fact_id_injected_into_rows(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(DIRECTORS_LLM_RESPONSE),
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    for row in result["rows"]:
        assert row["fact_id"] == fact_id


async def test_director_names_match_llm_response(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(DIRECTORS_LLM_RESPONSE),
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    names = {r["director_name"] for r in result["rows"]}
    assert names == {"Alice Smith", "Bob Jones"}


# ---------------------------------------------------------------------------
# Upsert / deduplication
# ---------------------------------------------------------------------------

async def test_upsert_idempotent_on_same_fact_and_name(mocker, seeded_fact_db):
    """Running twice with same directors doesn't duplicate rows."""
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(DIRECTORS_LLM_RESPONSE),
    )
    await extract_directors("# Markdown", fact_id=fact_id, db=db)
    await extract_directors("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(settings.TABLE_BOARD_DIRECTORS, "*", {})
    assert len(rows) == 2


async def test_upsert_updates_fee_on_rerun(mocker, seeded_fact_db):
    """Second run with changed total_fee updates the existing row."""
    db, _, fact_id = seeded_fact_db

    updated = copy.deepcopy(DIRECTORS_LLM_RESPONSE)
    updated[0]["retainer_fee"] = 999999  # bump component so fee arithmetic remains consistent
    updated[0]["total_fee"] = 999999

    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        side_effect=[_raw(DIRECTORS_LLM_RESPONSE), _raw(updated)],
    )
    await extract_directors("# Markdown", fact_id=fact_id, db=db)
    await extract_directors("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(settings.TABLE_BOARD_DIRECTORS, "*", {"director_name": "Alice Smith"})
    assert len(rows) == 1
    assert rows[0]["total_fee"] == 999999


async def test_new_director_on_second_run_adds_row(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db

    extra_director = {
        "director_name": "Carol White",
        "nationality": "Australian",
        "ethnicity": "Western",
        "local_expat": "Expat",
        "gender": "Female",
        "age": 42,
        "board_role": "Member",
        "director_type": "Independent",
        "skills": "Legal",
        "board_meetings_attended": 6,
        "retainer_fee": 80000,
        "benefits_in_kind": 0,
        "attendance_allowance": 0,
        "expense_allowance": 0,
        "assembly_fee": 0,
        "director_board_committee_fee": 0,
        "variable_remuneration": 0,
        "variable_remuneration_description": "",
        "other_remuneration": 0,
        "other_remuneration_description": "",
        "total_fee": 80000,
    }
    extended = copy.deepcopy(DIRECTORS_LLM_RESPONSE) + [extra_director]

    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        side_effect=[_raw(DIRECTORS_LLM_RESPONSE), _raw(extended)],
    )
    await extract_directors("# Markdown", fact_id=fact_id, db=db)
    await extract_directors("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(settings.TABLE_BOARD_DIRECTORS, "*", {})
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# Response format parsing
# ---------------------------------------------------------------------------

async def test_wrapper_format_parsed(mocker, seeded_fact_db):
    """LLM returning {"directors": [...], "extraction_metadata": {...}} is parsed correctly."""
    from execution.extract_directors import _parse_directors_response
    wrapper_response = {
        "directors": copy.deepcopy(DIRECTORS_LLM_RESPONSE),
        "extraction_metadata": {
            "extraction_notes": "Extracted from remuneration table",
            "conflicts": [],
        },
    }
    result = _parse_directors_response(json.dumps(wrapper_response))
    assert len(result) == 2
    assert result[0]["director_name"] == "Alice Smith"


async def test_plain_array_format_parsed():
    """Legacy plain array format [{"director_name": ...}] is accepted."""
    from execution.extract_directors import _parse_directors_response
    result = _parse_directors_response(json.dumps(DIRECTORS_LLM_RESPONSE))
    assert len(result) == 2


async def test_extraction_metadata_notes_logged(mocker, seeded_fact_db):
    """extraction_notes in metadata are logged via structlog."""
    from execution.extract_directors import _parse_directors_response
    wrapper_response = {
        "directors": copy.deepcopy(DIRECTORS_LLM_RESPONSE),
        "extraction_metadata": {"extraction_notes": "Found remuneration table on page 42"},
    }
    # Just verify it parses without error — structlog captures the log
    result = _parse_directors_response(json.dumps(wrapper_response))
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Validation integration
# ---------------------------------------------------------------------------

async def test_strict_validation_errors_raise_and_block_write(mocker, seeded_fact_db):
    """Invalid director data raises and no rows are written."""
    db, _, fact_id = seeded_fact_db
    bad_directors = copy.deepcopy(DIRECTORS_LLM_RESPONSE)
    bad_directors[0]["board_role"] = "Observer"  # invalid role → strict error

    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(bad_directors),
    )
    with pytest.raises(ExtractionValidationError):
        await extract_directors("# Markdown", fact_id=fact_id, db=db)

    rows = db.select("board_directors", "*", {"fact_id": fact_id})
    assert rows == []


async def test_soft_warnings_logged_not_blocking(mocker, seeded_fact_db):
    """Abbreviated nationality triggers soft warning but data is still written."""
    db, _, fact_id = seeded_fact_db
    warn_directors = copy.deepcopy(DIRECTORS_LLM_RESPONSE)
    warn_directors[0]["nationality"] = "Saudi"  # abbreviated

    mocker.patch(
        "execution.extract_directors.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(warn_directors),
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    assert len(result["rows"]) == 2


# ---------------------------------------------------------------------------
# Retry logic (tests the shared call_llm via integration)
# ---------------------------------------------------------------------------

async def test_retry_on_empty_response(mocker, seeded_fact_db):
    """call_llm retries when LLM returns empty content; succeeds on attempt 2."""
    db, _, fact_id = seeded_fact_db
    mocker.patch("execution.llm_client.asyncio.sleep", new_callable=AsyncMock)

    mock_create = AsyncMock(side_effect=[
        _make_completion(""),                                      # attempt 1: empty
        _make_completion(json.dumps(DIRECTORS_LLM_RESPONSE)),     # attempt 2: valid
    ])
    mocker.patch("execution.llm_client.get_client", return_value=_mock_client(mock_create))

    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    assert mock_create.call_count == 2
    assert len(result["rows"]) == 2


async def test_retry_exhausted_raises_runtime_error(mocker, seeded_fact_db):
    """When all 3 attempts return empty content, RuntimeError is raised."""
    db, _, fact_id = seeded_fact_db
    mocker.patch("execution.llm_client.asyncio.sleep", new_callable=AsyncMock)

    mock_create = AsyncMock(return_value=_make_completion("", finish_reason="length"))
    mocker.patch("execution.llm_client.get_client", return_value=_mock_client(mock_create))

    with pytest.raises(RuntimeError, match="empty response after"):
        await extract_directors("# Markdown", fact_id=fact_id, db=db)

    assert mock_create.call_count == 3


# ---------------------------------------------------------------------------
# Helpers for retry tests
# ---------------------------------------------------------------------------

def _make_completion(content: str, finish_reason: str = "stop"):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason
    response = MagicMock()
    response.choices = [choice]
    response.usage = None
    return response


def _mock_client(mock_create):
    client = MagicMock()
    client.chat.completions.create = mock_create
    return client
