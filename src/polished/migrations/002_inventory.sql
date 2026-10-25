-- 002_inventory.sql: what is owned and what is wanted.

create table bottle (
  id               integer primary key,
  shade_id         integer not null references shade (id),
  printed_code     text,                                      -- the P number as printed, normalised ("P259")
  state            text not null default 'full' check (state in ('full', 'half', 'low', 'empty')),
  bought_on        text,
  price_paid_cents integer,
  opened_on        text,
  notes            text,
  archived         integer not null default 0 check (archived in (0, 1)),
  created_at       text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at       text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
create index bottle_shade on bottle (shade_id);
create index bottle_printed_code on bottle (printed_code);

create table wishlist_item (
  id       integer primary key,
  shade_id integer not null unique references shade (id),
  priority integer not null default 2 check (priority between 1 and 3),   -- 1 = want most
  note     text,
  added_on text not null default (date('now'))
);

-- Owned = at least one bottle that is not archived and not empty.
create view shade_status as
select s.id as shade_id,
       (select count(*) from bottle b
         where b.shade_id = s.id and b.archived = 0 and b.state <> 'empty') as owned_count,
       (select count(*) from bottle b where b.shade_id = s.id) as bottle_count,
       exists (select 1 from wishlist_item w where w.shade_id = s.id) as wishlisted
from shade s;
