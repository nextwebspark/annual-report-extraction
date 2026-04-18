#!/usr/bin/env python3
"""Fetch a record from landing_parse_cache by ID.

Standalone usage:
    python execution/fetch_markdown.py --record-id 84
"""

import argparse
import json
import sys

import structlog

from config import settings
from config.db import get_db

log = structlog.get_logger()


def fetch_markdown(record_id: int, db=None) -> dict:
    """Return the full landing_parse_cache row for record_id.

    Args:
        record_id: Primary key in settings.TABLE_LANDING_CACHE.
        db:        Database instance. Auto-created via get_db() if None.

    Raises:
        RuntimeError: if record not found or markdown_llm_clean is empty.
    """
    if db is None:
        db = get_db()
    rows = db.select(settings.TABLE_LANDING_CACHE, "*", {"id": record_id}, limit=1)

    if not rows:
        raise RuntimeError(f"No record found in {settings.TABLE_LANDING_CACHE} for id={record_id}")

    record = rows[0]
    if not record.get("markdown_llm_clean"):
        raise RuntimeError(
            f"Record {record_id} has no markdown_llm_clean. "
            "Ensure the document has been parsed and cleaned before running the pipeline."
        )

    return record


if __name__ == "__main__":
    from config.logging import configure_logging
    configure_logging()

    parser = argparse.ArgumentParser(description="Fetch markdown from landing_parse_cache")
    parser.add_argument("--record-id", type=int, default=settings.CACHE_RECORD_ID)
    args = parser.parse_args()

    try:
        record = fetch_markdown(args.record_id)
        print(
            json.dumps(
                {
                    "record_id": record["id"],
                    "document_name": record.get("document_name"),
                    "page_count": record.get("page_count"),
                    "markdown_length": len(record.get("markdown_llm_clean") or ""),
                },
                indent=2,
            )
        )
    except RuntimeError as exc:
        log.error("fetch_markdown_failed", error=str(exc))
        sys.exit(1)
