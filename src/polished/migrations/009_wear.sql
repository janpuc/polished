-- 009_wear.sql: the wear log behind "Wear today" (docs/NATIVE.md 3, POST /api/v1/wear/{shade_id}).
--
-- Only a new table; nothing existing is touched, so it is safe on the live database.

-- One row per shade per day it was worn: tapping "I wore this" twice the same day is one row.
-- worn_on is the household's local date (YYYY-MM-DD), not UTC.
create table wear (
  id         integer primary key,
  shade_id   integer not null references shade (id),
  worn_on    text not null check (worn_on glob '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  unique (shade_id, worn_on)
);
create index wear_worn_on on wear (worn_on);
