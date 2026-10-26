-- 007_release_sheet.sql: Holo Taco's official release list (the Google Sheet).

-- shade.source gains 'sheet' (a shade the sheet lists and the shop feed does not), and four columns
-- take what the sheet knows. A CHECK cannot be altered in SQLite, so the table is rebuilt the way
-- sqlite.org/lang_altertable.html (section 7) says to: migrate.py runs with foreign keys off, so
-- dropping the old table deletes nothing in bottle, wishlist_item, stack_layer, shade_alias,
-- shade_identifier or shade_tag, which keep pointing at the same ids. The view that reads the
-- table goes first and comes back last, because the rename refuses a view over a missing table.
-- Every row keeps its id and every column its value.

drop view shade_status;

create table shade_new (
  id               integer primary key,
  product_id       integer unique references product (id),   -- null for source = 'manual' and 'sheet'
  source           text not null default 'holotaco' check (source in ('holotaco', 'manual', 'sheet')),
  kind             text not null check (kind in ('polish', 'topcoat', 'basecoat')),
  title            text not null,
  handle           text,
  sku              text,                                      -- not unique: Shopify does not enforce it
  search_text      text not null,                             -- lowercase, accent-folded title + tag values
  hero_image_url   text,                                      -- images[position = 1].src
  price_cents      integer,
  compare_at_cents integer,
  available        integer check (available in (0, 1)),       -- null for manual and sheet shades
  published_at     text,
  is_topper        integer not null default 0,                -- topcoat, or polish tagged toppers or color:clear
  retired          integer not null default 0,                -- tag collection:retirement, or sheet_retired
  retiring         integer not null default 0,                -- tag collection:soon-retiring
  created_at       text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  swatch_image_url text,
  swatch_hex       text,
  swatch_hex2      text,
  swatch_hex_src   text,
  swatch_override_hex text,
  -- From the release sheet (catalog/sheet.py), written by the sync, never by the household:
  released_on         text,                                   -- "2019-07-06", the official release date
  official_collection text,                                   -- "Holo Taco Unicorn Skin Collection"
  sheet_retired       integer not null default 0 check (sheet_retired in (0, 1)),
  sheet_key           text                                    -- the normalised sheet name this shade matched
);

insert into shade_new (
  id, product_id, source, kind, title, handle, sku, search_text, hero_image_url, price_cents,
  compare_at_cents, available, published_at, is_topper, retired, retiring, created_at,
  swatch_image_url, swatch_hex, swatch_hex2, swatch_hex_src, swatch_override_hex
)
select
  id, product_id, source, kind, title, handle, sku, search_text, hero_image_url, price_cents,
  compare_at_cents, available, published_at, is_topper, retired, retiring, created_at,
  swatch_image_url, swatch_hex, swatch_hex2, swatch_hex_src, swatch_override_hex
from shade;

drop table shade;
alter table shade_new rename to shade;

create index shade_kind on shade (kind);
create index shade_sku on shade (sku);
create index shade_handle on shade (handle);
create unique index shade_sheet_key on shade (sheet_key) where source = 'sheet';

create view shade_status as
select s.id as shade_id,
       (select count(*) from bottle b
         where b.shade_id = s.id and b.archived = 0 and b.state <> 'empty') as owned_count,
       (select count(*) from bottle b where b.shade_id = s.id) as bottle_count,
       exists (select 1 from wishlist_item w where w.shade_id = s.id) as wishlisted
from shade s;
