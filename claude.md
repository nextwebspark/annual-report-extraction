# Corporate Annual Report Extraction Pipeline

## What This Project Does
Fetches parsed markdown from Supabase, runs LLM extractions via OpenRouter, upserts to Supabase (or local SQLite in test mode).

## Key Rules
- **Directives are source of truth** — always read `directives/extract_info.md` before coding or running extractions
- **Update directives after every run** — append Last Run, Edge Cases, Learnings (never delete)
- **Config is centralized** — secrets in `.env`, prompts in `config/prompts.py`, schemas in `config/schemas.py`, settings in `config/settings.py`
- **DB abstraction** — use `config.db.get_db()` for all database writes (supports Supabase + SQLite)
- **No hardcoded credentials** — ever

## Project Structure
```
config/          → settings, prompts, schemas, db abstraction (all centralized)
execution/       → one script per task, each standalone-runnable
orchestration/   → pipeline runner (no business logic, just calls execution/)
directives/      → extract_info.md (living doc, source of truth)
evaluation/      → validation metrics (fee arithmetic, name crossref, nationality format)
supabase-schema/ → SQL table definitions
data/            → local input/output for offline testing
```

## Test Mode
Run with `--test` flag to write to local SQLite (`data/test.db`) instead of Supabase:
```bash
python3 orchestration/run_pipeline.py --record-id 84 --test
```

## For Detailed Guidance
- **Python coding rules** → `.claude/rules/python.md` (auto-applied to all `*.py` files)
- **Skills** → `.claude/skills/`:
  - `/run-pipeline` — run extractions (follows `directives/extract_info.md`)
  - `/supabase` — query, upsert, debug tables
  - `/extract` — work with prompts, schemas, validation
