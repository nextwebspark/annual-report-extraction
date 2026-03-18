create table public.companies (
  id bigserial not null,
  company_name jsonb not null,
  exchange jsonb not null,
  country jsonb not null,
  industry jsonb not null,
  source_document_url text null,
  source_system text not null default 'landing.ai'::text,
  extraction_run_id uuid null,
  data_version text null default 'v1'::text,
  company_name_value text GENERATED ALWAYS as ((company_name ->> 'value'::text)) STORED not null,
  exchange_value text GENERATED ALWAYS as ((exchange ->> 'value'::text)) STORED null,
  country_value text GENERATED ALWAYS as ((country ->> 'value'::text)) STORED not null,
  industry_value text GENERATED ALWAYS as ((industry ->> 'value'::text)) STORED null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  company_code character varying null,
  constraint companies_pkey primary key (id),
  constraint companies_name_country_value_uniq unique (company_name_value, country_value),
  constraint ux_companies_identity unique (company_name_value, exchange_value, country_value)
) TABLESPACE pg_default;

create trigger trg_companies_updated_at BEFORE
update on companies for EACH row
execute FUNCTION set_updated_at ();