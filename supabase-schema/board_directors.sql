create table public.board_directors (
  id bigserial not null,
  fact_id bigint not null,
  director_name character varying(255) not null,
  nationality character varying(100) null,
  ethnicity character varying(100) null,
  local_expat character varying(100) null,
  gender character varying(50) null,
  age integer null default 0,
  board_role character varying(100) null,
  director_type character varying(100) null,
  skills text null,
  board_meetings_attended integer null default 0,
  retainer_fee numeric(18, 2) null default 0,
  benefits_in_kind numeric(18, 2) null default 0,
  attendance_allowance numeric(18, 2) null default 0,
  expense_allowance numeric(18, 2) null default 0,
  assembly_fee numeric(18, 2) null default 0,
  director_board_committee_fee numeric(18, 2) null default 0,
  variable_remuneration numeric(18, 2) null default 0,
  variable_remuneration_description text null,
  other_remuneration numeric(18, 2) null default 0,
  other_remuneration_description text null,
  total_fee numeric(18, 2) null default 0,
  created_at timestamp with time zone null default now(),
  constraint board_directors_pkey primary key (id)
) TABLESPACE pg_default;

create unique INDEX IF not exists ux_board_directors_fact_director on public.board_directors using btree (fact_id, director_name) TABLESPACE pg_default;