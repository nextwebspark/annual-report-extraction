"""Unit tests for execution/extract_committees.py.

call_llm is always mocked (returns raw JSON string). DB uses real SQLiteDB(":memory:").
The retry test patches the shared call_llm to exercise error paths.
No network calls are made.
"""

import copy
import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from execution.extract_committees import extract_committees
from tests.fixtures.llm_responses import COMMITTEES_LLM_RESPONSE


def _raw(data) -> str:
    """Serialize data to JSON string (simulating raw LLM output)."""
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_returns_list_of_rows(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_committees.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMMITTEES_LLM_RESPONSE),
    )
    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)
    assert isinstance(result, list)
    assert len(result) == 2


async def test_committees_written_to_db(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_committees.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMMITTEES_LLM_RESPONSE),
    )
    await extract_committees("# Markdown", fact_id=fact_id, db=db)

    from config import settings
    rows = db.select(settings.TABLE_BOARD_COMMITTEES, "*", {})
    assert len(rows) == 2


async def test_fact_id_injected_into_rows(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch(
        "execution.extract_committees.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMMITTEES_LLM_RESPONSE),
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
        "execution.extract_committees.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(COMMITTEES_LLM_RESPONSE),
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
        "execution.extract_committees.call_llm",
        new_callable=AsyncMock,
        side_effect=[_raw(COMMITTEES_LLM_RESPONSE), _raw(updated)],
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
        "execution.extract_committees.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(two_committees),
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
    """Fields not in _DB_FIELDS are stripped by _parse_committees_response."""
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

async def test_strict_validation_errors_logged_not_blocking(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    bad = copy.deepcopy(COMMITTEES_LLM_RESPONSE)
    bad[0]["committee_retainer_fee"] = -100  # negative → strict error

    mocker.patch(
        "execution.extract_committees.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(bad),
    )
    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)
    # Data written despite validation error
    assert len(result) == 2


async def test_soft_warnings_logged_not_blocking(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    warn = copy.deepcopy(COMMITTEES_LLM_RESPONSE)
    warn[0]["nationality"] = "UAE"  # abbreviated

    mocker.patch(
        "execution.extract_committees.call_llm",
        new_callable=AsyncMock,
        return_value=_raw(warn),
    )
    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)
    # Data written despite warning
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Retry logic (tests the shared call_llm via integration)
# ---------------------------------------------------------------------------

async def test_retry_on_empty_response(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch("execution.llm_client.asyncio.sleep", new_callable=AsyncMock)

    mock_create = AsyncMock(side_effect=[
        _make_completion(""),                                       # attempt 1: empty
        _make_completion(json.dumps(COMMITTEES_LLM_RESPONSE)),     # attempt 2: valid
    ])
    mocker.patch("execution.llm_client.get_client", return_value=_mock_client(mock_create))

    result = await extract_committees("# Markdown", fact_id=fact_id, db=db)
    assert mock_create.call_count == 2
    assert len(result) == 2


async def test_retry_exhausted_raises_runtime_error(mocker, seeded_fact_db):
    db, _, fact_id = seeded_fact_db
    mocker.patch("execution.llm_client.asyncio.sleep", new_callable=AsyncMock)

    mock_create = AsyncMock(return_value=_make_completion("", finish_reason="length"))
    mocker.patch("execution.llm_client.get_client", return_value=_mock_client(mock_create))

    with pytest.raises(RuntimeError, match="empty response after"):
        await extract_committees("# Markdown", fact_id=fact_id, db=db)

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
