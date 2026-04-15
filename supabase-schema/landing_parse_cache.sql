create table public.landing_parse_cache_KSA-2023 (
  id bigserial not null,
  file_id character varying(255) not null,
  document_name character varying(500) not null,
  file_hash character varying(200) null,
  mime_type character varying(100) null,
  file_size_bytes bigint null,
  job_id character varying(255) null,
  job_status character varying(100) null,
  model_name character varying(200) null,
  parse_mode character varying(50) null,
  page_count integer null,
  markdown text null,
  json_schema_output jsonb null,
  parse_version character varying(50) null,
  credit_used numeric(10, 2) null default 0,
  total_cost numeric(10, 4) null default 0,
  job_duration_ms bigint null,
  source_system character varying(100) null default 'landing.ai'::character varying,
  workflow_run_id character varying(255) null,
  is_valid boolean null default true,
  notes text null,
  uploaded_at timestamp with time zone null default now(),
  failure_reason text null,
  markdown_splits jsonb null,
  markdown_llm_clean text null,
  constraint landing_parse_cache_pkey primary key (id),
  constraint ux_cache_file unique (file_id)
) TABLESPACE pg_default;

create index IF not exists ix_landing_cache_job on public.landing_parse_cache using btree (job_id) TABLESPACE pg_default;

create index IF not exists ix_landing_cache_status on public.landing_parse_cache using btree (job_status) TABLESPACE pg_default;

create index IF not exists ix_landing_cache_hash on public.landing_parse_cache using btree (file_hash) TABLESPACE pg_default;