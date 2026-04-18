-- Reference table: Middle East markets — country, currency, and exchange metadata.
-- Apply once against the Supabase project. Safe to re-run (DROP IF EXISTS guard).

create table if not exists public.ref_markets (
  id          smallserial primary key,
  country     text not null unique,   -- full country name, e.g. "Saudi Arabia"
  currency    text not null,          -- ISO 4217 code, e.g. "SAR"
  mic         text null,              -- ISO 10383 MIC code, e.g. "XSAU"
  exchange    text null               -- human-readable exchange name, e.g. "Tadawul"
);

-- UAE has multiple exchanges; primary (DFM) is recorded here.
-- ADX (XADS) and Nasdaq Dubai (XNDQ) are aliases handled in application code.

insert into public.ref_markets (country, currency, mic, exchange) values
  ('Afghanistan',   'AFN', null,   null),
  ('Armenia',       'AMD', null,   null),
  ('Azerbaijan',    'AZN', null,   null),
  ('Bahrain',       'BHD', 'XBAH', 'Bahrain Bourse'),
  ('Cyprus',        'EUR', null,   null),
  ('Egypt',         'EGP', 'XCAI', 'Egyptian Exchange'),
  ('Georgia',       'GEL', null,   null),
  ('Iran',          'IRR', null,   null),
  ('Iraq',          'IQD', null,   null),
  ('Israel',        'ILS', 'XTAE', 'Tel Aviv Stock Exchange'),
  ('Jordan',        'JOD', 'XASE', 'Amman Stock Exchange'),
  ('Kuwait',        'KWD', 'XKUW', 'Boursa Kuwait'),
  ('Lebanon',       'LBP', 'XBES', 'Beirut Stock Exchange'),
  ('Oman',          'OMR', 'XMSM', 'Muscat Securities Market'),
  ('Palestine',     'ILS', null,   null),
  ('Qatar',         'QAR', 'XDSM', 'Qatar Stock Exchange'),
  ('Saudi Arabia',  'SAR', 'XSAU', 'Tadawul'),
  ('Syria',         'SYP', null,   null),
  ('Turkey',        'TRY', 'XIST', 'Borsa Istanbul'),
  ('UAE',           'AED', 'XDFM', 'Dubai Financial Market'),
  ('Yemen',         'YER', null,   null)
on conflict (country) do nothing;
