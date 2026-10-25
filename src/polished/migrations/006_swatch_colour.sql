-- 006_swatch_colour.sql: the colour of each shade's polish, for the generated nail tips.

-- swatch_hex / swatch_hex2: "#rrggbb", read by catalog/colour.py from the swatch photo (else the
-- bottle shot); hex2 is a second, clearly different colour (shifts, duochromes), null when there
-- is none. swatch_hex_src is the image URL they were read from, so a new photo is read again.
-- swatch_override_hex is the household's own choice; the sync never writes it.
alter table shade add column swatch_hex text;
alter table shade add column swatch_hex2 text;
alter table shade add column swatch_hex_src text;
alter table shade add column swatch_override_hex text;
