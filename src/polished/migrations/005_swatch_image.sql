-- 005_swatch_image.sql: the photo that shows the polish on a nail (visual polish pass).

-- Picked at sync time by catalog/parse.py swatch_image_url (a filename heuristic); null when no
-- photo qualifies, and the app then crops hero_image_url. Existing rows are filled by the next sync.
alter table shade add column swatch_image_url text;
