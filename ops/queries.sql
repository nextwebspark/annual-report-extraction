-- Ops queries against the extraction_runs ledger.
-- Parameterise :year where your SQL client supports it, or replace inline.

-- 1. Current failure list for a year (most recent attempt per record only)
select distinct on (landing_cache_record_id)
  landing_cache_record_id,
  status,
  attempt,
  step,
  error_class,
  error_message,
  started_at,
  finished_at
from extraction_runs
where year = 2023
  and status = 'failed'
order by landing_cache_record_id, started_at desc;

-- 2. Attempt history for a specific record
select
  id, status, attempt, step, error_class, error_message,
  prompt_tokens, completion_tokens, total_tokens,
  started_at, finished_at
from extraction_runs
where landing_cache_record_id = 84
  and year = 2023
order by started_at desc;

-- 3. Daily throughput + failure rate
select
  date_trunc('day', started_at) as day,
  count(*) filter (where status = 'success') as success,
  count(*) filter (where status = 'failed')  as failed,
  count(*) filter (where status = 'skipped') as skipped,
  round(100.0 *
    count(*) filter (where status = 'failed')::numeric
    / nullif(count(*) filter (where status in ('success','failed')), 0),
    2
  ) as failure_pct
from extraction_runs
where year = 2023
group by day
order by day desc;

-- 4. Token usage roll-up for a year
select
  model,
  count(*) as runs,
  sum(prompt_tokens)     as prompt_tokens,
  sum(completion_tokens) as completion_tokens,
  sum(total_tokens)      as total_tokens
from extraction_runs
where year = 2023
  and status = 'success'
group by model
order by total_tokens desc nulls last;

-- 5. Records never attempted (in source table but not in ledger)
-- Replace the year-templated table name as needed.
select lpc.id
from "landing_parse_cache_KSA-2023" lpc
where lpc.markdown_llm_clean is not null
  and not exists (
    select 1 from extraction_runs er
    where er.landing_cache_record_id = lpc.id
      and er.year = 2023
  )
order by lpc.id;

-- 6. Which step is failing most often this week?
select step, count(*) as failures
from extraction_runs
where year = 2023
  and status = 'failed'
  and started_at >= now() - interval '7 days'
group by step
order by failures desc;
