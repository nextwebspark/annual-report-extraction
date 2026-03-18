create table public.board_committees (
  id bigserial not null,
  fact_id bigint not null,
  member_name character varying(255) not null,
  nationality character varying(100) null,
  ethnicity character varying(100) null,
  local_expat character varying(100) null,
  gender character varying(100) null,
  age integer null default 0,
  committee_name character varying(150) null,
  committee_role character varying(150) null,
  committee_meetings_attended integer null default 0,
  committee_retainer_fee numeric(18, 2) null default 0,
  committee_allowances numeric(18, 2) null default 0,
  committee_total_fee numeric(18, 2) null default 0,
  created_at timestamp with time zone null default now(),
  constraint board_committees_pkey primary key (id)
) TABLESPACE pg_default;

create unique INDEX IF not exists ux_board_committees_fact_member_committee on public.board_committees using btree (fact_id, member_name, committee_name) TABLESPACE pg_default;