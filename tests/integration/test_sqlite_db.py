"""Integration tests for config/db.py SQLiteDB.

Tests the DB layer directly using an in-memory SQLite database.
No mocking, no network, no Supabase.
"""

import pytest

from config.db import SQLiteDB


@pytest.fixture
def db():
    return SQLiteDB(":memory:")


# ---------------------------------------------------------------------------
# Schema initialization
# ---------------------------------------------------------------------------

def test_all_tables_created_on_init(db):
    cursor = db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert {"companies", "company_facts", "board_directors", "board_committees"}.issubset(tables)


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------

def test_insert_returns_row_with_id(db):
    result = db.insert("companies", {
        "company_name": {"value": "Test Co", "confidence": 0.9},
        "exchange": {"value": "NYSE", "confidence": 0.9},
        "country": {"value": "US", "confidence": 0.9},
        "industry": {"value": "Tech", "confidence": 0.9},
        "source_document_url": "",
        "company_code": "test_co",
    })
    assert len(result) == 1
    assert isinstance(result[0]["id"], int)
    assert result[0]["id"] > 0


def test_insert_two_rows_have_different_ids(db):
    r1 = db.insert("companies", {
        "company_name": {"value": "Co A", "confidence": 0.9},
        "exchange": {"value": "NYSE", "confidence": 0.9},
        "country": {"value": "US", "confidence": 0.9},
        "industry": {"value": "Tech", "confidence": 0.9},
        "source_document_url": "",
        "company_code": "co_a",
    })
    r2 = db.insert("companies", {
        "company_name": {"value": "Co B", "confidence": 0.9},
        "exchange": {"value": "NYSE", "confidence": 0.9},
        "country": {"value": "US", "confidence": 0.9},
        "industry": {"value": "Tech", "confidence": 0.9},
        "source_document_url": "",
        "company_code": "co_b",
    })
    assert r1[0]["id"] != r2[0]["id"]


# ---------------------------------------------------------------------------
# select
# ---------------------------------------------------------------------------

def _insert_company(db, code: str) -> int:
    result = db.insert("companies", {
        "company_name": {"value": code, "confidence": 0.9},
        "exchange": {"value": "NYSE", "confidence": 0.9},
        "country": {"value": "US", "confidence": 0.9},
        "industry": {"value": "Tech", "confidence": 0.9},
        "source_document_url": "",
        "company_code": code,
    })
    return result[0]["id"]


def test_select_with_filter_returns_matching_row(db):
    _insert_company(db, "alpha")
    _insert_company(db, "beta")

    rows = db.select("companies", "*", {"company_code": "alpha"})
    assert len(rows) == 1
    assert rows[0]["company_code"] == "alpha"


def test_select_no_match_returns_empty_list(db):
    _insert_company(db, "alpha")
    rows = db.select("companies", "*", {"company_code": "nonexistent"})
    assert rows == []


def test_select_no_filter_returns_all_rows(db):
    _insert_company(db, "x")
    _insert_company(db, "y")
    _insert_company(db, "z")
    rows = db.select("companies", "*", {})
    assert len(rows) == 3


def test_select_with_limit(db):
    for i in range(5):
        _insert_company(db, f"co_{i}")
    rows = db.select("companies", "*", {}, limit=2)
    assert len(rows) == 2


def test_select_specific_column(db):
    cid = _insert_company(db, "solo")
    rows = db.select("companies", "id", {"company_code": "solo"})
    assert rows[0]["id"] == cid
    # Other columns not requested — only 'id' key present
    assert list(rows[0].keys()) == ["id"]


# ---------------------------------------------------------------------------
# upsert — conflict resolution
# ---------------------------------------------------------------------------

def _seed_company_facts(db, company_id: int, year: int = 2023) -> int:
    rows = db.upsert("company_facts", {
        "company_id": company_id,
        "year": year,
        "revenue": {"value": 1000, "currency": "USD", "confidence": 0.9, "unit_stated": "actual"},
        "profit_net": {"value": 200, "currency": "USD", "confidence": 0.9, "unit_stated": "actual"},
    }, on_conflict="company_id,year")
    return rows[0]["id"]


def test_upsert_inserts_new_row(db):
    cid = _insert_company(db, "new_co")
    rows_before = db.select("company_facts", "*", {})
    assert len(rows_before) == 0

    _seed_company_facts(db, cid)
    rows_after = db.select("company_facts", "*", {})
    assert len(rows_after) == 1


def test_upsert_does_not_duplicate_on_conflict_companies(db):
    """Second upsert with same company_code updates, not duplicates."""
    cid = _insert_company(db, "acme")

    db.upsert("company_facts", {
        "company_id": cid, "year": 2023,
        "revenue": {"value": 100, "currency": "USD", "confidence": 0.9, "unit_stated": "actual"},
        "profit_net": {"value": 10, "currency": "USD", "confidence": 0.9, "unit_stated": "actual"},
    }, on_conflict="company_id,year")

    db.upsert("company_facts", {
        "company_id": cid, "year": 2023,
        "revenue": {"value": 200, "currency": "USD", "confidence": 0.9, "unit_stated": "actual"},
        "profit_net": {"value": 20, "currency": "USD", "confidence": 0.9, "unit_stated": "actual"},
    }, on_conflict="company_id,year")

    rows = db.select("company_facts", "*", {"company_id": cid})
    assert len(rows) == 1
    assert rows[0]["revenue"]["value"] == 200


def test_upsert_board_directors_dedup_key(db):
    cid = _insert_company(db, "co_d")
    fid = _seed_company_facts(db, cid)

    director = {
        "fact_id": fid, "director_name": "Alice", "total_fee": 100000,
        "gender": "Female", "board_role": "Member", "director_type": "Independent",
    }
    db.upsert("board_directors", director, on_conflict="fact_id,director_name")
    updated = {**director, "total_fee": 200000}
    db.upsert("board_directors", updated, on_conflict="fact_id,director_name")

    rows = db.select("board_directors", "*", {"fact_id": fid, "director_name": "Alice"})
    assert len(rows) == 1
    assert rows[0]["total_fee"] == 200000


def test_upsert_board_committees_dedup_key(db):
    cid = _insert_company(db, "co_c")
    fid = _seed_company_facts(db, cid)

    membership = {
        "fact_id": fid, "member_name": "Bob", "committee_name": "Audit",
        "committee_total_fee": 50000,
    }
    db.upsert("board_committees", membership, on_conflict="fact_id,member_name,committee_name")
    updated = {**membership, "committee_total_fee": 75000}
    db.upsert("board_committees", updated, on_conflict="fact_id,member_name,committee_name")

    rows = db.select("board_committees", "*", {"fact_id": fid})
    assert len(rows) == 1
    assert rows[0]["committee_total_fee"] == 75000


def test_upsert_multiple_rows(db):
    cid = _insert_company(db, "multi_co")
    fid = _seed_company_facts(db, cid)

    directors = [
        {"fact_id": fid, "director_name": "Alice", "total_fee": 100000},
        {"fact_id": fid, "director_name": "Bob", "total_fee": 80000},
    ]
    result = db.upsert("board_directors", directors, on_conflict="fact_id,director_name")
    assert len(result) == 2

    rows = db.select("board_directors", "*", {})
    assert len(rows) == 2


def test_upsert_single_dict_not_list(db):
    """Passing a single dict (not list) to upsert is accepted."""
    cid = _insert_company(db, "single_co")
    fid = _seed_company_facts(db, cid)

    single = {"fact_id": fid, "director_name": "Eve", "total_fee": 60000}
    result = db.upsert("board_directors", single, on_conflict="fact_id,director_name")
    assert len(result) == 1
    assert result[0]["director_name"] == "Eve"


# ---------------------------------------------------------------------------
# JSON column serialization round-trip
# ---------------------------------------------------------------------------

def test_json_column_dict_round_trips(db):
    """revenue stored as JSON string, deserialized back to dict on select."""
    cid = _insert_company(db, "json_co")
    rev = {"value": 42000, "currency": "SAR", "confidence": 0.95, "unit_stated": "thousands"}

    db.upsert("company_facts", {
        "company_id": cid, "year": 2022,
        "revenue": rev,
        "profit_net": {"value": 5000, "currency": "SAR", "confidence": 0.9, "unit_stated": "thousands"},
    }, on_conflict="company_id,year")

    rows = db.select("company_facts", "*", {"company_id": cid})
    assert isinstance(rows[0]["revenue"], dict)
    assert rows[0]["revenue"]["value"] == 42000
    assert rows[0]["revenue"]["currency"] == "SAR"


def test_non_json_column_passes_through_unchanged(db):
    """Plain string columns like director_name are not JSON-encoded."""
    cid = _insert_company(db, "plain_co")
    fid = _seed_company_facts(db, cid)

    db.upsert("board_directors", {
        "fact_id": fid, "director_name": "Plain Name", "total_fee": 0,
    }, on_conflict="fact_id,director_name")

    rows = db.select("board_directors", "*", {"director_name": "Plain Name"})
    assert rows[0]["director_name"] == "Plain Name"
    assert isinstance(rows[0]["director_name"], str)
