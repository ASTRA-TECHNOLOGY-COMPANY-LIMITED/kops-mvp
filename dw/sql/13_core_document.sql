-- Technical documents known by name only (N-02): style resolved through the style dictionary (file no / alias ->
-- style no); a code that is not a known style is kept as written (style_known = false).
CREATE TABLE core.document AS
WITH cand AS (
  SELECT d.file_id, c.code, c.pos
  FROM stg.document d, unnest(string_split(d.style_candidates, ',')) WITH ORDINALITY AS c(code, pos)
  WHERE d.style_candidates IS NOT NULL),
hit AS (
  SELECT c.file_id, arg_min(k.style_no, c.pos) AS style_no, arg_min(k.customer, c.pos) AS dict_customer,
         arg_min(k.season, c.pos) AS dict_season
  FROM cand c JOIN core.style_dictionary k ON k.key = c.code GROUP BY c.file_id)
SELECT d.file_id, d.path_hash, d.file_name, d.ext, d.size_bytes, d.sha256,
       coalesce(h.dict_customer, d.customer) AS customer,
       coalesce(h.style_no, split_part(d.style_candidates, ',', 1)) AS style_no, h.style_no IS NOT NULL AS style_known,
       d.style_candidates, d.factory, coalesce(d.season, h.dict_season) AS season, d.stage, d.doc_kind, d.doc_date,
       d.meta_source, f.is_sample
FROM stg.document d JOIN etl.source_file f USING (file_id)
LEFT JOIN hit h USING (file_id);
