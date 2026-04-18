"""Shared pytest fixtures and configuration.

pytest_configure patches required env vars before any module import occurs,
preventing config.settings._require() from raising RuntimeError during collection.
"""

import copy
import os

import pytest

from tests.fixtures.llm_responses import (
    COMMITTEES_LLM_RESPONSE,
    COMPANY_LLM_RESPONSE,
    DIRECTORS_LLM_RESPONSE,
)
from tests.fixtures.markdown_samples import SAMPLE_MARKDOWN


def pytest_configure(config):
    """Inject required env vars before test collection imports config modules."""
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key-placeholder")
    os.environ.setdefault("SUPABASE_URL", "http://fake-supabase.local")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
    os.environ.setdefault("TEST_MODE", "true")


@pytest.fixture
def memory_db():
    """Fresh in-memory SQLiteDB for each test."""
    from config.db import SQLiteDB
    return SQLiteDB(":memory:")


@pytest.fixture
def seeded_fact_db():
    """In-memory SQLiteDB pre-seeded with one company and one company_facts row.

    Returns (db, company_id, fact_id).
    """
    from config import settings
    from config.db import SQLiteDB

    db = SQLiteDB(":memory:")

    company_row = db.insert(settings.TABLE_COMPANIES, {
        "company_name": {"value": "Seed Co", "confidence": 0.99, "source": "cover"},
        "exchange": {"value": "NYSE", "confidence": 0.99, "source": "cover"},
        "country": {"value": "United States", "confidence": 0.99, "source": "cover"},
        "source_document_url": "",
        "company_code": "seed_co",
    })
    company_id = company_row[0]["id"]

    fact_row = db.upsert(settings.TABLE_COMPANY_FACTS, {
        "company_id": company_id,
        "year": 2023,
        "revenue": {"value": 1000000, "currency": "USD", "confidence": 0.9, "unit_stated": "actual"},
        "profit_net": {"value": 200000, "currency": "USD", "confidence": 0.9, "unit_stated": "actual"},
        "extraction_run_id": None,
    }, on_conflict="company_id,year")
    fact_id = fact_row[0]["id"]

    return db, company_id, fact_id


@pytest.fixture(scope="session")
def sample_markdown():
    return SAMPLE_MARKDOWN


@pytest.fixture(scope="session")
def company_llm_response():
    return copy.deepcopy(COMPANY_LLM_RESPONSE)


@pytest.fixture(scope="session")
def directors_llm_response():
    return copy.deepcopy(DIRECTORS_LLM_RESPONSE)


@pytest.fixture(scope="session")
def committees_llm_response():
    return copy.deepcopy(COMMITTEES_LLM_RESPONSE)
