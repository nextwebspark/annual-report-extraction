#!/usr/bin/env python3
"""Fetch a record from landing_parse_cache by ID.

Standalone usage:
    python execution/fetch_markdown.py --record-id 84
"""

import argparse
import json
import sys

from supabase import create_client

from config import settings


def fetch_markdown(record_id: int) -> dict:
    """Return the full landing_parse_cache row for record_id.

    Raises:
        RuntimeError: if record not found or markdown_llm_clean is empty.
    """
    db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    result = (
        db.table(settings.TABLE_LANDING_CACHE)
        .select("*")
        .eq("id", record_id)
        .single()
        .execute()
    )

    if not result.data:
        raise RuntimeError(f"No record found in {settings.TABLE_LANDING_CACHE} for id={record_id}")

    record = result.data
    if not record.get("markdown_llm_clean"):
        raise RuntimeError(
            f"Record {record_id} has no markdown_llm_clean. "
            "Ensure the document has been parsed and cleaned before running the pipeline."
        )

    return record


if __name__ == "__main__":
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
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
