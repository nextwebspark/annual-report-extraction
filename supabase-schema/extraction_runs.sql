-- Ops ledger for the extraction pipeline.
-- Every invocation of run_pipeline (single-record or batch) writes one row here.
-- Primary purpose: find failed records, rerun them, track tokens/cost per attempt.

create table if not exists public.extraction_runs (
  id                       bigserial primary key,
  landing_cache_record_id  integer       not null,
  year                     integer       not null,
  workflow_run_id          text          null,
  status                   text          not null check (status in ('pending','success','failed','skipped')),
  attempt                  integer       not null default 1,
  step                     text          null,
  error_class              text          null,
  error_message            text          null,
  model                    text          null,
  prompt_tokens            integer       null,
  completion_tokens        integer       null,
  total_tokens             integer       null,
  started_at               timestamptz   not null default now(),
  finished_at              timestamptz   null
);

create index if not exists ix_extraction_runs_lookup
  on public.extraction_runs (landing_cache_record_id, year);

create index if not exists ix_extraction_runs_status
  on public.extraction_runs (status, started_at desc);
