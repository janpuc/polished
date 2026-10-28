-- 010_wipe_printed_codes.sql: Holo Taco's printed P numbers are retired as an identifier
-- (DESIGN 14). The learned P codes and the P number stored on each bottle are deleted.
--
-- DROP COLUMN needs SQLite 3.35; python:3.12-slim ships 3.40 or newer. The column is only
-- indexed (no view, trigger or foreign key uses it), so the index goes first.
-- shade_identifier keeps its check (kind in ('gtin', 'printed')): narrowing it would rebuild a
-- table the app points at, and no code writes 'printed' any more.

delete from shade_identifier where kind = 'printed';

drop index bottle_printed_code;
alter table bottle drop column printed_code;
