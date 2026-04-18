create table public.company_facts (
  id bigserial not null,
  company_id bigint not null,
  year integer not null,
  revenue jsonb not null,
  profit_net jsonb not null,
  market_capitalisation jsonb null,
  employees jsonb null,
  revenue_band integer null,
  revenue_band_label text null,
  employee_band integer null,
  employee_band_label text null,
  source_document_url text null,
  source_system text not null default 'landing.ai'::text,
  extraction_run_id text null,
  data_version text not null default 'v1'::text,
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  constraint company_facts_pkey primary key (id),
  constraint company_facts_company_year_uniq unique (company_id, year),
  constraint ux_company_year unique (company_id, year)
) TABLESPACE pg_default;

create unique INDEX IF not exists ux_company_facts_company_year on public.company_facts using btree (company_id, year) TABLESPACE pg_default;