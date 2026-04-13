"""Centralised configuration. All env vars, model names, table names, and folder IDs live here."""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


# --- Credentials ---
OPENROUTER_API_KEY: str = _require("OPENROUTER_API_KEY")
SUPABASE_URL: str = _require("SUPABASE_URL")
SUPABASE_SERVICE_KEY: str = _require("SUPABASE_SERVICE_KEY")
# --- Pipeline defaults ---
CACHE_RECORD_ID: int = int(os.environ.get("CACHE_RECORD_ID", 84))

# --- OpenRouter ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# --- LLM models and temperatures ---
COMPANY_MODEL = "google/gemini-2.5-pro"
COMPANY_TEMPERATURE = 0.0

DIRECTORS_MODEL = "google/gemini-2.5-pro"
DIRECTORS_TEMPERATURE = 0.0

COMMITTEES_MODEL = "google/gemini-2.5-pro"
COMMITTEES_TEMPERATURE = 0.0

# --- LLM output limits ---
LLM_MAX_TOKENS = 65536

# --- LLM retry / timeout ---
LLM_MAX_RETRIES: int = int(os.environ.get("LLM_MAX_RETRIES", 3))
LLM_BACKOFF_BASE: int = int(os.environ.get("LLM_BACKOFF_BASE", 2))
LLM_REQUEST_TIMEOUT: int = int(os.environ.get("LLM_REQUEST_TIMEOUT", 300))

# --- Supabase table names ---
TABLE_LANDING_CACHE = "landing_parse_cache"
TABLE_COMPANIES = "companies"
TABLE_COMPANY_FACTS = "company_facts"
TABLE_BOARD_DIRECTORS = "board_directors"
TABLE_BOARD_COMMITTEES = "board_committees"

# --- Test mode ---
TEST_MODE: bool = os.environ.get("TEST_MODE", "").lower() in ("1", "true", "yes")
SQLITE_DB_PATH: str = os.environ.get("SQLITE_DB_PATH", "data/test.db")
