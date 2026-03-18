"""Unit tests for execution/extract_committees.py.

_call_llm is always mocked. DB uses real SQLiteDB(":memory:").
The retry test patches AsyncOpenAI directly to exercise the retry loop.
No network calls are made.
"""

import copy
import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from execution.extract_committees import extract_committees
from tests.fixtures.llm_responses import COMMITTEES_LLM_RESPONSE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_completion(content: str, finish_reason: str = "stop"):
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
        "execution.extract_committees._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(COMMITTEES_LLM_RESPONSE),
    )
    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)
    assert isinstance(result, list)
    assert len(result) == 2


async def test_committees_written_to_db(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_committees._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(COMMITTEES_LLM_RESPONSE),
    )
    await extract_committees("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(settings.TABLE_BOARD_COMMITTEES, "*", {})
    assert len(rows) == 2


async def test_fact_id_injected_into_rows(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_committees._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(COMMITTEES_LLM_RESPONSE),
    )
    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)
    for row in result:
        assert row["fact_id"] == fact_id


# ---------------------------------------------------------------------------
# Upsert / deduplication
# ---------------------------------------------------------------------------

async def test_upsert_idempotent_on_same_triple(mocker, seeded_fact_db):
    """Same (fact_id, member_name, committee_name) → no duplicate rows."""
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_committees._call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(COMMITTEES_LLM_RESPONSE),
    )
    await extract_committees("# Markdown", fact_id=fact_id, db=db)
    await extract_committees("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(settings.TABLE_BOARD_COMMITTEES, "*", {})
    assert len(rows) == 2


async def test_upsert_updates_fee_on_rerun(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    updated = copy.deepcopy(COMMITTEES_LLM_RESPONSE)
    updated[0]["committee_total_fee"] = 99999

    mocker.patch(
        "execution.extract_committees._call_llm",
        new_callable=AsyncMock,
        side_effect=[copy.deepcopy(COMMITTEES_LLM_RESPONSE), updated],
    )
    await extract_committees("# Markdown", fact_id=fact_id, db=db)
    await extract_committees("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(
        settings.TABLE_BOARD_COMMITTEES, "*",
        {"member_name": "Alice Smith", "committee_name": "Audit Committee"},
    )
    assert len(rows) == 1
    assert rows[0]["committee_total_fee"] == 99999


async def test_same_member_two_committees_creates_two_rows(mocker, seeded_fact_db):
    """Alice in Audit + Alice in Remuneration = 2 separate rows."""
    db, _, fact_id = seeded_fact_db
    two_committees = [
        {**copy.deepcopy(COMMITTEES_LLM_RESPONSE[0])},  # Alice in Audit
        {
            **copy.deepcopy(COMMITTEES_LLM_RESPONSE[0]),
            "committee_name": "Remuneration Committee",
            "committee_total_fee": 40000,
        },
    ]
    mocker.patch(
        "execution.extract_committees._call_llm",
        new_callable=AsyncMock,
        return_value=two_committees,
    )
    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)
    assert len(result) == 2

    from config import settings
    rows = db.select(settings.TABLE_BOARD_COMMITTEES, "*", {"member_name": "Alice Smith"})
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Response format parsing
# ---------------------------------------------------------------------------

async def test_wrapper_format_committee_memberships_key_parsed():
    """{"committee_memberships": [...], "extraction_metadata": {...}} is parsed correctly."""
    from execution.extract_committees import _parse_committees_response
    wrapper = {
        "committee_memberships": copy.deepcopy(COMMITTEES_LLM_RESPONSE),
        "extraction_metadata": {"extraction_notes": "From remuneration table"},
    }
    result = _parse_committees_response(json.dumps(wrapper))
    assert len(result) == 2
    assert result[0]["member_name"] == "Alice Smith"


async def test_plain_array_legacy_format_parsed():
    from execution.extract_committees import _parse_committees_response
    result = _parse_committees_response(json.dumps(COMMITTEES_LLM_RESPONSE))
    assert len(result) == 2


async def test_wrapper_format_strips_extra_fields():
    """Fields not in db_fields are stripped by _parse_committees_response."""
    from execution.extract_committees import _parse_committees_response
    membership_with_extra = {
        **copy.deepcopy(COMMITTEES_LLM_RESPONSE[0]),
        "director_type": "Non-Executive",  # not a committee DB field
        "board_role": "Chairman",           # not a committee DB field
    }
    wrapper = {"committee_memberships": [membership_with_extra]}
    result = _parse_committees_response(json.dumps(wrapper))
    assert "director_type" not in result[0]
    assert "board_role" not in result[0]
    assert "member_name" in result[0]


# ---------------------------------------------------------------------------
# Validation integration
# ---------------------------------------------------------------------------

async def test_strict_validation_errors_logged_not_blocking(mocker, seeded_fact_db, capsys):
    db, _, fact_id = seeded_fact_db
    bad = copy.deepcopy(COMMITTEES_LLM_RESPONSE)
    bad[0]["committee_retainer_fee"] = -100  # negative → strict error

    mocker.patch(
        "execution.extract_committees._call_llm",
        new_callable=AsyncMock,
        return_value=bad,
    )
    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)

    captured = capsys.readouterr()
    assert "[EVAL]" in captured.err
    assert len(result) == 2


async def test_soft_warnings_logged_not_blocking(mocker, seeded_fact_db, capsys):
    db, _, fact_id = seeded_fact_db
    warn = copy.deepcopy(COMMITTEES_LLM_RESPONSE)
    warn[0]["nationality"] = "UAE"  # abbreviated

    mocker.patch(
        "execution.extract_committees._call_llm",
        new_callable=AsyncMock,
        return_value=warn,
    )
    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)

    captured = capsys.readouterr()
    assert "[WARN]" in captured.err
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

async def test_retry_on_empty_response(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    mock_create = AsyncMock(side_effect=[
        make_completion(""),                                       # attempt 1: empty
        make_completion(json.dumps(COMMITTEES_LLM_RESPONSE)),     # attempt 2: valid
    ])
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    mocker.patch("execution.extract_committees.AsyncOpenAI", return_value=mock_client)

    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)
    assert mock_create.call_count == 2
    assert len(result) == 2


async def test_retry_exhausted_raises_runtime_error(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    mock_create = AsyncMock(return_value=make_completion("", finish_reason="length"))
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    mocker.patch("execution.extract_committees.AsyncOpenAI", return_value=mock_client)

    with pytest.raises(RuntimeError, match="empty response after"):
        await extract_committees("# Markdown", fact_id=fact_id, db=db)

    assert mock_create.call_count == 3
