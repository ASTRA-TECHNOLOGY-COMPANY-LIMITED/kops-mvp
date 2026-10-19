-- core: one clean, conformed model built only from the CURRENT version of each source.
-- Rule: totals are never taken from a file; they are computed from detail rows.

CREATE OR REPLACE MACRO core.factory_code(raw_txt) AS (
  SELECT factory_code FROM stg.factory_alias
  WHERE alias_key = upper(trim(regexp_replace(strip_accents(replace(replace(coalesce(raw_txt, ''), 'Đ', 'D'), 'đ', 'd')), '\s+', ' ', 'g')))
);

CREATE OR REPLACE MACRO core.style_key(s) AS (
  coalesce((SELECT style_no FROM stg.style_alias WHERE alias_style = s), s)
);

CREATE OR REPLACE VIEW core.current_file AS
SELECT file_id, season AS file_season FROM etl.source_file WHERE is_current;

-- Style master (ORDER RECAP is the system of record for style / colour / qty / factory)
CREATE TABLE core.order_color AS
SELECT c.season, c.style_no, upper(trim(c.color_raw)) AS color, c.color_note, c.change_note,
       c.qty_raw, c.order_qty, c.is_active, c.file_id, c.row_no
FROM raw.order_recap_color c JOIN core.current_file f USING (file_id);

CREATE TEMP TABLE style_order_base AS
WITH q AS (
  SELECT season, style_no, sum(order_qty) FILTER (WHERE is_active) AS order_qty,
         count(*) FILTER (WHERE is_active) AS n_colors,
         sum(order_qty) FILTER (WHERE NOT is_active) AS qty_excluded
  FROM core.order_color GROUP BY ALL)
SELECT s.season, s.style_no, s.order_no, s.brand,
       CASE WHEN s.status_label = 'CANCEL' THEN NULL ELSE core.factory_code(s.factory_raw) END AS factory_code,
       s.factory_raw, s.status_label AS status, s.status_label <> 'CANCEL' AS is_active,
       s.etd_vn, coalesce(s.rdd_kr, s.etd_vn + (SELECT rule_value::INT FROM stg.rule WHERE rule_key = 'rdd_offset_days')) AS rdd_kr,
       s.etd_raw, s.line_raw, s.collection_raw AS collection, s.description_en, s.name_kr, s.main_fabric,
       nullif(trim(split_part(s.main_fabric, ')', 1)), '') AS fabric_supplier_raw,
       CASE WHEN length(s.style_no) = 11 THEN substr(s.style_no, 5, 1) END AS gender,
       CASE WHEN length(s.style_no) = 11 THEN substr(s.style_no, 6, 2) END AS item_type,
       coalesce(q.order_qty, 0) AS order_qty, coalesce(q.n_colors, 0) AS n_colors, q.qty_excluded,
       s.grand_ttl_reported, s.progress_notes, s.file_id, s.row_no
FROM raw.order_recap_style s JOIN core.current_file f USING (file_id)
LEFT JOIN q USING (season, style_no);

-- Supplier = text before ')' in the main fabric cell; '=>' marks a replacement, keep the newest.
CREATE TABLE core.style_order AS
SELECT *, CASE WHEN fab_last LIKE '%)%'
               THEN nullif(trim(regexp_replace(split_part(fab_last, ')', 1), '\(.*$', '')), '') END AS fabric_supplier
FROM (SELECT *, trim(list_last(string_split(coalesce(main_fabric, ''), '=>'))) AS fab_last
FROM style_order_base);

-- Shipment Status detail (system of record for colour x size and shipped lots)
CREATE TABLE core.shipment_detail AS
SELECT f.file_season AS season, coalesce(o.style_no, c.style_no_raw) AS style_no, c.style_no_raw, c.factory AS factory_code,
       c.section, c.label, upper(trim(c.color_raw)) AS color, c.size_code, c.qty, c.lot_etd, c.lot_eta,
       coalesce(c.ship_mode, CASE WHEN c.section = 'SHIPMENT' THEN 'UNKNOWN' END) AS ship_mode,
       CASE WHEN c.section = 'SAMPLE' THEN
         CASE WHEN upper(c.label) LIKE '%PHOTO%' THEN 'PHOTO'
              WHEN upper(c.label) LIKE '%DOWN TEST%' THEN 'DOWN TEST'
              WHEN upper(c.label) LIKE '%SHIPPING S%' THEN 'SHIPPING'
              ELSE 'OTHER' END END AS sample_type,
       c.file_id, c.sheet, c.row_no, c.col_no
FROM raw.shipment_cell c JOIN core.current_file f USING (file_id)
LEFT JOIN core.style_order o ON o.season = f.file_season AND o.style_no = core.style_key(c.style_no_raw);

-- Production & Shipping Status snapshot (system of record for output / inspection / plans)
CREATE TABLE core.production_snapshot AS
SELECT p.season, core.style_key(p.style_no) AS style_no, p.style_no AS style_no_raw, p.as_of, p.order_no, core.factory_code(p.factory_raw) AS factory_code, p.factory_raw,
       p.type AS collection, p.etd_vn, p.rdd, p.fpp_cfmd, p.inline_raw, p.top_smpl,
       p.order_qty AS order_qty_reported, p.one_day AS daily_output, p.output_qty, p.inspected_qty,
       p.shipped_qty AS shipped_qty_reported, p.cutting_plan, p.input_plan, p.sewing_finish_plan,
       p.exfact_est, coalesce(p.etd_est::VARCHAR, p.etd_est_txt) AS etd_est, p.file_id, p.row_no
FROM raw.production_status p JOIN core.current_file f USING (file_id);

-- History extracted from free-text notes
CREATE TABLE core.qty_change AS
SELECT q.*, 'ORDER RECAP note' AS source FROM stg.qty_change q JOIN core.current_file f USING (file_id);

CREATE TABLE core.factory_event AS
SELECT e.*, core.factory_code(e.factory_hint) AS factory_code
FROM stg.factory_event e JOIN core.current_file f USING (file_id);

-- Emails and proposed changes (never applied automatically)
CREATE TABLE core.email AS
SELECT e.* EXCLUDE (body), left(e.body, 4000) AS body FROM raw.email e JOIN core.current_file f USING (file_id);

CREATE TABLE core.change_proposal AS
SELECT c.message_id, e.sent_at, e.subject, e.is_sample, c.style_no, o.season, o.factory_code,
       c.change_type, c.value_text, o.order_qty AS current_qty,
       CASE WHEN c.change_type = 'QTY_PCT' THEN round(o.order_qty * (1 + c.pct / 100.0))::INT
            WHEN c.change_type = 'QTY' THEN c.qty_after END AS proposed_qty,
       o.etd_vn AS current_etd, c.new_date AS proposed_etd, c.color_from, c.color_to,
       (o.style_no IS NOT NULL) AS style_known, o.status AS style_status,
       CASE WHEN c.change_type = 'COLOR' THEN EXISTS (
              SELECT 1 FROM core.order_color oc WHERE oc.style_no = c.style_no AND oc.color = c.color_from)
       END AS color_from_exists,
       -- The % change may already be in ORDER RECAP while other files still show the old qty (Q4)
       CASE WHEN c.change_type = 'QTY_PCT' THEN p.order_qty_reported END AS qty_in_other_file,
       (c.change_type = 'QTY_PCT' AND p.order_qty_reported IS NOT NULL
        AND abs(round(p.order_qty_reported * (1 + c.pct / 100.0)) - o.order_qty) <= 1) AS possibly_applied,
       c.confidence, c.evidence, c.review_status
FROM stg.email_change c JOIN core.current_file f USING (file_id)
LEFT JOIN core.email e USING (message_id)
LEFT JOIN core.style_order o ON o.style_no = c.style_no
LEFT JOIN core.production_snapshot p ON p.style_no = c.style_no;

-- Meeting notes
CREATE TABLE core.meeting AS SELECT m.* FROM stg.meeting m JOIN core.current_file USING (file_id);
CREATE TABLE core.requirement AS
SELECT r.*, coalesce(v.mvp_status, 'TODO') AS mvp_status, v.where_in_mvp, v.next_step
FROM stg.requirement r JOIN core.current_file USING (file_id)
LEFT JOIN stg.requirement_coverage v USING (req_no);
CREATE TABLE core.action_item AS SELECT a.* FROM stg.action_item a JOIN core.current_file USING (file_id);
CREATE TABLE core.decision AS SELECT d.* FROM stg.decision d JOIN core.current_file USING (file_id);
