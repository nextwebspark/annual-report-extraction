# Directive: Annual Report Information Extraction

> **Source of truth for extraction behaviour.** Update Last Run after every pipeline run.

## Overview

| Extractor | Script | Target Table(s) | Model | Temp |
|-----------|--------|-----------------|-------|------|
| Company + Financials | `execution/extract_company.py` | `companies`, `company_facts` | claude-opus-4-6 | 0.0 |
| Board Directors | `execution/extract_directors.py` | `board_directors` | claude-opus-4-6 | 0.0 |
| Board Committees | `execution/extract_committees.py` | `board_committees` | claude-opus-4-6 | 0.0 |

Single-pass extraction via OpenRouter. DB abstraction layer (`config/db.py`) supports Supabase (production) and SQLite (test mode).

## Pipeline Architecture

```
Step 0  Idempotency check (workflow_run_id vs company_facts.extraction_run_id)
Step 1  fetch_markdown(record_id) → markdown_llm_clean + workflow_run_id
Step 2  extract_company(markdown, workflow_run_id) → company_id, fact_id  [sequential]
Step 3  extract_directors(markdown, fact_id)  ┐  [parallel]
        extract_committees(markdown, fact_id) ┘
```

### Deduplication

| Table | Key | Behaviour |
|-------|-----|-----------|
| `companies` | `company_code` | Lookup first; insert only if absent |
| `company_facts` | `(company_id, year)` | Upsert |
| `board_directors` | `(fact_id, director_name)` | Upsert |
| `board_committees` | `(fact_id, member_name, committee_name)` | Upsert |

## CLI Usage

```bash
# Production
python orchestration/run_pipeline.py --record-id 84
python orchestration/run_pipeline.py --record-id 84 --force

# Test mode (writes to local SQLite)
python orchestration/run_pipeline.py --record-id 84 --test

# Individual scripts
python execution/extract_company.py --record-id 84 [--test]
python execution/extract_directors.py --record-id 84 --fact-id 12 [--test]
python execution/extract_committees.py --record-id 84 --fact-id 12 [--test]
```

## Edge Cases

- **Two-session boards**: Extract most recent (year-end) session values for role/type.
- **Honorific drift**: Board Composition table spelling is authoritative for names.
- **Role changes**: Use year-end role only; never concatenate.
- **Out-of-board committee members**: Copy name from committee table if not a director.
- **Zero fees for mid-year joiners**: Correct if absent from all remuneration tables.
- **Declared but not paid fees**: Extract table amounts as-is; note "not paid" in `other_remuneration_description` (directors) or `extraction_notes` (committees).

## Last Run

- **Timestamp:** 2026-03-18T10:18:40Z
- **Record ID:** 104
- **Document:** Al Sagr Cooperative Insurance Co. - Annual Report - 2023.pdf
- **Mode:** test (SQLite)
- **Status:** success
- **Extracted:** company_id=19, fact_id=23, directors=9, committees=19, name_mismatches=6
- **Notes:** 6 name mismatches (4 external audit committee members + chairman name spelling conflict Al-Arifi vs Al-Oraifi); FY2023 remuneration not disclosed, fees set to 0

## Learnings

- All extraction is single-pass (no verification pass).
- Schema/strict/soft validation is non-blocking — logs warnings, always writes to DB.
- Board Composition table is the authoritative name source.
- Upsert strategy (no delete-then-insert); stale rows need manual cleanup.
- `--force` flag bypasses idempotency check.
- Wrapper JSON format: `{"directors": [...], "extraction_metadata": {...}}`.
