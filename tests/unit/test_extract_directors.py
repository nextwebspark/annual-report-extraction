"""Unit tests for execution/extract_directors.py.

_call_llm is always mocked. DB uses real SQLiteDB(":memory:").
The retry test patches AsyncOpenAI directly to exercise the retry loop inside _call_llm.
No network calls are made.
"""

import copy
import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from execution.extract_directors import extract_directors
from tests.fixtures.llm_responses import DIRECTORS_LLM_RESPONSE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_completion(content: str, finish_reason: str = "stop"):
    """Build a fake OpenAI completion response object."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_returns_list_of_rows(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(DIRECTORS_LLM_RESPONSE),
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    assert isinstance(result, list)
    assert len(result) == 2


async def test_directors_written_to_db(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(DIRECTORS_LLM_RESPONSE),
    )
    await extract_directors("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(settings.TABLE_BOARD_DIRECTORS, "*", {})
    assert len(rows) == 2


async def test_fact_id_injected_into_rows(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(DIRECTORS_LLM_RESPONSE),
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    for row in result:
        assert row["fact_id"] == fact_id


async def test_director_names_match_llm_response(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(DIRECTORS_LLM_RESPONSE),
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    names = {r["director_name"] for r in result}
    assert names == {"Alice Smith", "Bob Jones"}


# ---------------------------------------------------------------------------
# Upsert / deduplication
# ---------------------------------------------------------------------------

async def test_upsert_idempotent_on_same_fact_and_name(mocker, seeded_fact_db):
    """Running twice with same directors doesn't duplicate rows."""
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(DIRECTORS_LLM_RESPONSE),
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
    updated[0]["total_fee"] = 999999

    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        side_effect=[
            copy.deepcopy(DIRECTORS_LLM_RESPONSE),
            updated,
        ],
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
        "ethnicity": "White",
        "local_expat": "expat",
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
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        side_effect=[
            copy.deepcopy(DIRECTORS_LLM_RESPONSE),
            extended,
        ],
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
    db, _, fact_id = seeded_fact_db
    wrapper_response = {
        "directors": copy.deepcopy(DIRECTORS_LLM_RESPONSE),
        "extraction_metadata": {
            "extraction_notes": "Extracted from remuneration table",
            "conflicts": [],
        },
    }
    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(DIRECTORS_LLM_RESPONSE),
    )
    # The mock returns the list directly (post-parse), so test that extract_directors
    # correctly handles both list and wrapper — test wrapper via _parse_directors_response
    from execution.extract_directors import _parse_directors_response
    result = _parse_directors_response(json.dumps(wrapper_response))
    assert len(result) == 2
    assert result[0]["director_name"] == "Alice Smith"


async def test_plain_array_format_parsed():
    """Legacy plain array format [{"director_name": ...}] is accepted."""
    from execution.extract_directors import _parse_directors_response
    result = _parse_directors_response(json.dumps(DIRECTORS_LLM_RESPONSE))
    assert len(result) == 2


async def test_extraction_metadata_notes_logged(mocker, seeded_fact_db, capsys):
    """extraction_notes in metadata are logged as [INFO] to stderr."""
    db, _, fact_id = seeded_fact_db
    wrapper_response = {
        "directors": copy.deepcopy(DIRECTORS_LLM_RESPONSE),
        "extraction_metadata": {"extraction_notes": "Found remuneration table on page 42"},
    }

    # Patch _parse_directors_response indirectly by making _call_llm return the list,
    # but test the logging via _parse_directors_response directly
    from execution.extract_directors import _parse_directors_response
    import sys
    from io import StringIO
    old_err = sys.stderr
    sys.stderr = StringIO()
    try:
        _parse_directors_response(json.dumps(wrapper_response))
        output = sys.stderr.getvalue()
    finally:
        sys.stderr = old_err
    assert "[INFO]" in output
    assert "Found remuneration table on page 42" in output


# ---------------------------------------------------------------------------
# Validation integration
# ---------------------------------------------------------------------------

async def test_strict_validation_errors_logged_not_blocking(mocker, seeded_fact_db, capsys):
    """Invalid director data emits [EVAL] to stderr but data is still written."""
    db, _, fact_id = seeded_fact_db
    bad_directors = copy.deepcopy(DIRECTORS_LLM_RESPONSE)
    bad_directors[0]["board_role"] = "Observer"  # invalid role → strict error

    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        return_value=bad_directors,
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)

    captured = capsys.readouterr()
    assert "[EVAL]" in captured.err
    assert len(result) == 2  # data written despite error


async def test_soft_warnings_logged_not_blocking(mocker, seeded_fact_db, capsys):
    """Abbreviated nationality emits [WARN] to stderr but data is still written."""
    db, _, fact_id = seeded_fact_db
    warn_directors = copy.deepcopy(DIRECTORS_LLM_RESPONSE)
    warn_directors[0]["nationality"] = "Saudi"  # abbreviated

    mocker.patch(
        "execution.extract_directors._call_llm",
        new_callable=AsyncMock,
        return_value=warn_directors,
    )
    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)

    captured = capsys.readouterr()
    assert "[WARN]" in captured.err
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

async def test_retry_on_empty_response(mocker, seeded_fact_db):
    """_call_llm retries when LLM returns empty content; succeeds on attempt 2."""
    db, _, fact_id = seeded_fact_db

    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    mock_create = AsyncMock(side_effect=[
        make_completion(""),                                      # attempt 1: empty
        make_completion(json.dumps(DIRECTORS_LLM_RESPONSE)),     # attempt 2: valid
    ])
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    mocker.patch("execution.extract_directors.AsyncOpenAI", return_value=mock_client)

    result = await extract_directors("# Markdown", fact_id=fact_id, db=db)
    assert mock_create.call_count == 2
    assert len(result) == 2


async def test_retry_exhausted_raises_runtime_error(mocker, seeded_fact_db):
    """When all 3 attempts return empty content, RuntimeError is raised."""
    db, _, fact_id = seeded_fact_db

    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    mock_create = AsyncMock(return_value=make_completion("", finish_reason="length"))
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    mocker.patch("execution.extract_directors.AsyncOpenAI", return_value=mock_client)

    with pytest.raises(RuntimeError, match="empty response after"):
        await extract_directors("# Markdown", fact_id=fact_id, db=db)

    assert mock_create.call_count == 3
