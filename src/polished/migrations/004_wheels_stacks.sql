-- 004_wheels_stacks.sql

create table wheel (
  id         integer primary key,
  slug       text not null unique,                            -- 6 chars, the NFC/QR URL: /w/<slug>
  name       text not null,
  slot_count integer not null default 20 check (slot_count between 1 and 40),
  archived   integer not null default 0 check (archived in (0, 1)),
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- A stack is an ordered list of layers, owned by exactly one holder (a wheel slot in v1, a mani
-- in v3). Holders never share a stack row; "copy" duplicates the layer rows.
create table stack (
  id         integer primary key,
  name       text,                                            -- optional favourite name
  status     text not null default 'draft' check (status in ('draft', 'saved')),
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

create table stack_layer (
  id       integer primary key,
  stack_id integer not null references stack (id) on delete cascade,
  ord      integer not null check (ord >= 1),                 -- 1 = painted first (base)
  shade_id integer not null references shade (id),
  coats    integer not null default 1 check (coats between 1 and 5),
  unique (stack_id, ord)
);
create index stack_layer_shade on stack_layer (shade_id);     -- "where did I use topper X"

-- A slot row exists once it holds a swatch, a draft or a note; empty slots have no row.
-- stack_id is the saved swatch; draft_stack_id is the working copy while the builder is open
-- (a copy of the saved layers, or empty). Save swaps the draft in and deletes the old stack.
create table wheel_slot (
  wheel_id       integer not null references wheel (id) on delete cascade,
  position       integer not null check (position >= 1),      -- <= wheel.slot_count, checked in code
  stack_id       integer references stack (id) on delete set null,
  draft_stack_id integer references stack (id) on delete set null,
  painted_on     text,
  note           text,
  primary key (wheel_id, position)
) without rowid;
create unique index wheel_slot_stack on wheel_slot (stack_id) where stack_id is not null;
create unique index wheel_slot_draft on wheel_slot (draft_stack_id) where draft_stack_id is not null;
