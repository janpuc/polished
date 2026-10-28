-- 011_matte_taco_finish.sql: the shop lists Matte Taco as a "Nail Polish" with only `color:clear`,
-- so the tip renderer never saw a matte finish (DESIGN 14, item 90). Backfills the row synced
-- before catalog/overrides.py; every later sync applies the same override itself.

insert or ignore into shade_tag (shade_id, ns, value)
select id, 'finish', 'matte' from shade where handle = 'matte-taco' and source = 'holotaco';

update shade
   set kind = 'topcoat', is_topper = 1,
       search_text = case when search_text like '% matte%' then search_text else search_text || ' matte' end
 where handle = 'matte-taco' and source = 'holotaco';
