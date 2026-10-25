-- 003_identifiers.sql: learned codes. SKUs are not here: shade.sku already holds them.

create table shade_identifier (
  id           integer primary key,
  kind         text not null check (kind in ('gtin', 'printed')),
  value        text not null,                                 -- gtin: 13 digits; printed: "P259"
  shade_id     integer not null references shade (id) on delete cascade,
  source       text not null default 'learned',               -- v1 writes only 'learned'
  use_count    integer not null default 0,
  created_at   text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  last_used_at text,
  unique (kind, value)
);
create index shade_identifier_shade on shade_identifier (shade_id);
