-- 001_catalog.sql: what the feed told us (stage 1).

-- Every product the feed ever listed (526 today). Rows are never deleted.
create table product (
  id                 integer primary key,
  shopify_product_id integer not null unique,
  variant_id         integer not null,            -- variants[0]; every product has exactly one
  handle             text not null,               -- may change; identity is shopify_product_id
  title              text not null,
  product_type       text not null,
  role               text not null check (role in ('shade', 'bundle', 'alias', 'skipped')),
  sku                text,
  price_cents        integer,
  compare_at_cents   integer,                     -- null when absent or 0
  available          integer not null check (available in (0, 1)),
  published_at       text,
  tags_json          text not null,               -- the feed's tag array, as sent
  raw_json           text not null,               -- the product minus body_html, kept when the hash changes
  content_hash       text not null,
  first_seen         text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  last_seen          text not null,
  absent_syncs       integer not null default 0,  -- consecutive successful syncs without it
  missing_since      text                         -- set at absent_syncs >= 3, cleared when it returns
);
create index product_handle on product (handle);
create index product_role on product (role);

-- One row per real single polish, topper or base coat (372 today), plus manual shades.
-- The app-facing copy of the product's facts, so queries need no join.
create table shade (
  id               integer primary key,
  product_id       integer unique references product (id),   -- null for source = 'manual'
  source           text not null default 'holotaco' check (source in ('holotaco', 'manual')),
  kind             text not null check (kind in ('polish', 'topcoat', 'basecoat')),
  title            text not null,
  handle           text,
  sku              text,                                      -- not unique: Shopify does not enforce it
  search_text      text not null,                             -- lowercase, accent-folded title + tag values
  hero_image_url   text,                                      -- images[position = 1].src
  price_cents      integer,
  compare_at_cents integer,
  available        integer check (available in (0, 1)),       -- null for manual shades
  published_at     text,
  is_topper        integer not null default 0,                -- topcoat, or polish tagged color:clear
  retired          integer not null default 0,                -- tag collection:retirement
  retiring         integer not null default 0,                -- tag collection:soon-retiring
  created_at       text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
create index shade_kind on shade (kind);
create index shade_sku on shade (sku);
create index shade_handle on shade (handle);

-- Birthday-gift copies (and renamed or relisted products) pointing at the canonical shade.
create table shade_alias (
  product_id integer primary key references product (id),
  shade_id   integer not null references shade (id),
  source     text not null check (source in ('handle', 'manual'))
);
create index shade_alias_shade on shade_alias (shade_id);

-- finish:x, color:x, collection:x as rows (not a comma string): filters and collection
-- progress query these.
create table shade_tag (
  shade_id integer not null references shade (id) on delete cascade,
  ns       text not null check (ns in ('finish', 'color', 'collection')),
  value    text not null,
  primary key (shade_id, ns, value)
) without rowid;
create index shade_tag_lookup on shade_tag (ns, value);

-- One row per sync attempt: the /sync page, the manual-sync cooldown, startup catch-up.
create table sync_run (
  id                 integer primary key,
  started_at         text not null,
  finished_at        text,
  trigger            text not null check (trigger in ('schedule', 'catchup', 'manual', 'cli')),
  status             text not null check (status in ('running', 'ok', 'error')),
  pages_fetched      integer not null default 0,
  products_seen      integer not null default 0,
  new_shades         integer not null default 0,
  changed_shades     integer not null default 0,
  newly_missing      integer not null default 0,
  returned           integer not null default 0,
  unresolved_aliases integer not null default 0,
  error              text
);
