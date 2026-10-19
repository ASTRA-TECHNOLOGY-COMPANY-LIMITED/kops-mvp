-- mart: denormalised tables that feed the dashboard. Every figure is computed from core detail.

CREATE OR REPLACE MACRO mart.rule_int(k) AS (SELECT rule_value::INT FROM stg.rule WHERE rule_key = k);

-- One row per style and season with everything the Control Tower needs
CREATE TEMP TABLE style_360_base AS
WITH ship AS (
  SELECT season, style_no,
         sum(qty) FILTER (WHERE section = 'ORDER') AS order_qty_ship_file,
         sum(qty) FILTER (WHERE section = 'SHIPMENT') AS shipped_qty,
         sum(qty) FILTER (WHERE section = 'SAMPLE') AS sample_qty,
         min(lot_etd) FILTER (WHERE section = 'SHIPMENT' AND qty > 0) AS first_lot_etd,
         max(lot_etd) FILTER (WHERE section = 'SHIPMENT' AND qty > 0) AS last_lot_etd,
         count(DISTINCT label) FILTER (WHERE section = 'SHIPMENT') AS n_lots,
         bool_or(ship_mode = 'AIR') AS has_air
  FROM core.shipment_detail GROUP BY ALL),
moves AS (
  SELECT season, style_no, count(*) FILTER (WHERE action = 'MOVED') AS n_factory_moves,
         string_agg(strftime(event_date, '%y%m%d') || ' ' || action || coalesce(' ' || factory_hint, ''), ' → ' ORDER BY event_date) AS factory_history
  FROM core.factory_event GROUP BY ALL),
chg AS (SELECT season, style_no, count(*) AS n_qty_changes FROM core.qty_change GROUP BY ALL),
iss AS (SELECT entity AS style_no, count(*) AS n_issues FROM etl.data_issue GROUP BY ALL),
base AS (
  SELECT o.season, o.style_no, o.order_no, o.brand, o.status, o.is_active, o.factory_code, o.collection,
         o.description_en, o.name_kr, o.gender, o.item_type, o.fabric_supplier, o.main_fabric,
         o.etd_vn, o.rdd_kr, o.order_qty, o.n_colors,
         s.order_qty_ship_file, coalesce(s.shipped_qty, 0) AS shipped_qty, coalesce(s.sample_qty, 0) AS sample_qty,
         s.first_lot_etd, s.last_lot_etd, coalesce(s.n_lots, 0) AS n_lots, coalesce(s.has_air, FALSE) AS has_air,
         p.as_of, p.order_qty_reported AS order_qty_prod_file, p.daily_output, p.output_qty, p.inspected_qty,
         p.shipped_qty_reported, p.fpp_cfmd, p.cutting_plan, p.input_plan, p.sewing_finish_plan,
         coalesce(m.n_factory_moves, 0) AS n_factory_moves, m.factory_history,
         coalesce(c.n_qty_changes, 0) AS n_qty_changes, coalesce(i.n_issues, 0) AS n_issues,
         o.file_id, o.row_no
  FROM core.style_order o
  LEFT JOIN ship s USING (season, style_no)
  LEFT JOIN core.production_snapshot p USING (season, style_no)
  LEFT JOIN moves m USING (season, style_no)
  LEFT JOIN chg c USING (season, style_no)
  LEFT JOIN iss i USING (style_no))
SELECT *,
  greatest(order_qty - shipped_qty, 0) AS balance_qty,
  CASE WHEN order_qty > 0 THEN round(100.0 * shipped_qty / order_qty, 1) END AS ship_pct,
  CASE WHEN order_qty > 0 AND output_qty IS NOT NULL THEN round(100.0 * output_qty / order_qty, 1) END AS output_pct,
  -- Projected ready date = as_of + remaining / daily output (Sundays off) + buffer   (meeting rule, configurable)
  CASE WHEN as_of IS NOT NULL AND output_qty IS NOT NULL AND output_qty < order_qty THEN
    as_of + CAST(ceil((order_qty - output_qty) / coalesce(nullif(daily_output, 0), mart.rule_int('default_daily_output'))::DOUBLE)
                 + floor(ceil((order_qty - output_qty) / coalesce(nullif(daily_output, 0), mart.rule_int('default_daily_output'))::DOUBLE) / 6)
                 + mart.rule_int('ready_buffer_days') AS INTEGER)
  END AS projected_ready,
  CASE WHEN first_lot_etd IS NOT NULL AND etd_vn IS NOT NULL
       THEN first_lot_etd <= etd_vn + mart.rule_int('ontime_tolerance_days') END AS shipped_on_time
FROM base;

CREATE TABLE mart.style_360 AS
SELECT *,
  CASE WHEN NOT is_active THEN 'CANCELLED'
       WHEN order_qty > 0 AND shipped_qty >= order_qty * (1 - mart.rule_int('qty_tolerance_pct') / 100.0) THEN 'SHIPPED'
       WHEN projected_ready IS NOT NULL AND etd_vn IS NOT NULL AND projected_ready > etd_vn THEN 'AT RISK'
       WHEN as_of IS NOT NULL AND etd_vn IS NOT NULL AND etd_vn < as_of AND shipped_qty < order_qty THEN 'OVERDUE'
       WHEN output_qty IS NOT NULL AND output_qty > 0 THEN 'IN PRODUCTION'
       ELSE 'PRE-PRODUCTION' END AS health,
  CASE WHEN projected_ready IS NOT NULL AND etd_vn IS NOT NULL THEN projected_ready - etd_vn END AS days_late
FROM style_360_base;

CREATE TABLE mart.season_kpi AS
SELECT season,
  count(*) FILTER (WHERE is_active) AS styles_active,
  count(*) FILTER (WHERE NOT is_active) AS styles_cancelled,
  sum(order_qty) FILTER (WHERE is_active) AS order_qty,
  sum(shipped_qty) FILTER (WHERE is_active) AS shipped_qty,
  sum(sample_qty) FILTER (WHERE is_active) AS sample_qty,
  sum(output_qty) FILTER (WHERE is_active) AS output_qty,
  sum(inspected_qty) FILTER (WHERE is_active) AS inspected_qty,
  count(*) FILTER (WHERE health = 'SHIPPED') AS styles_shipped,
  count(*) FILTER (WHERE health IN ('AT RISK', 'OVERDUE')) AS styles_at_risk,
  count(DISTINCT factory_code) FILTER (WHERE is_active) AS factories,
  round(100.0 * count(*) FILTER (WHERE shipped_on_time) / nullif(count(*) FILTER (WHERE shipped_on_time IS NOT NULL), 0), 1) AS ontime_pct,
  count(*) FILTER (WHERE n_factory_moves > 0) AS styles_moved,
  min(etd_vn) AS first_etd, max(etd_vn) AS last_etd, max(as_of) AS as_of
FROM mart.style_360 GROUP BY season;

CREATE TABLE mart.status_mix AS
SELECT season, status, health, count(*) AS styles, sum(order_qty) AS order_qty
FROM mart.style_360 GROUP BY ALL;

CREATE TABLE mart.factory_kpi AS
SELECT season, coalesce(factory_code, '(chưa gán)') AS factory_code,
  count(*) AS styles, sum(order_qty) AS order_qty, sum(output_qty) AS output_qty,
  sum(inspected_qty) AS inspected_qty, sum(shipped_qty) AS shipped_qty,
  round(100.0 * sum(shipped_qty) / nullif(sum(order_qty), 0), 1) AS ship_pct,
  round(100.0 * count(*) FILTER (WHERE shipped_on_time) / nullif(count(*) FILTER (WHERE shipped_on_time IS NOT NULL), 0), 1) AS ontime_pct,
  count(*) FILTER (WHERE health IN ('AT RISK', 'OVERDUE')) AS styles_at_risk,
  count(*) FILTER (WHERE n_factory_moves > 0) AS styles_moved_in,
  sum(daily_output) AS daily_output
FROM mart.style_360 WHERE is_active GROUP BY ALL;

CREATE TABLE mart.supplier_styles AS
SELECT season, coalesce(fabric_supplier, '(không rõ)') AS fabric_supplier, count(*) AS styles, sum(order_qty) AS order_qty,
  string_agg(DISTINCT factory_code, ', ') AS factories,
  string_agg(style_no, ', ' ORDER BY style_no) AS style_list
FROM mart.style_360 WHERE is_active GROUP BY ALL;

CREATE TABLE mart.shipment_lot AS
SELECT season, label AS lot_label, lot_etd, lot_eta, ship_mode, factory_code,
  count(DISTINCT style_no) AS styles, sum(qty) AS qty
FROM core.shipment_detail WHERE section = 'SHIPMENT' GROUP BY ALL;

CREATE TABLE mart.shipment_weekly AS
SELECT season, CAST(date_trunc('week', lot_etd) AS DATE) AS week_start, ship_mode, sum(qty) AS qty, count(DISTINCT style_no) AS styles
FROM core.shipment_detail WHERE section = 'SHIPMENT' AND lot_etd IS NOT NULL GROUP BY ALL;

CREATE TABLE mart.assortment AS
SELECT season, style_no, color, size_code,
  sum(qty) FILTER (WHERE section = 'ORDER') AS ordered,
  sum(qty) FILTER (WHERE section = 'SHIPMENT') AS shipped,
  sum(qty) FILTER (WHERE section = 'SAMPLE') AS sample
FROM core.shipment_detail GROUP BY ALL;

CREATE TABLE mart.lot_detail AS
SELECT season, style_no, label AS lot_label, lot_etd, lot_eta, ship_mode, color, size_code, sum(qty) AS qty,
  min(sheet || '!R' || row_no || 'C' || col_no) AS location
FROM core.shipment_detail WHERE section IN ('SHIPMENT', 'SAMPLE') GROUP BY ALL;

-- Same number, three files: where do they disagree?
CREATE TABLE mart.reconciliation AS
SELECT season, style_no, factory_code, order_qty AS order_recap_qty, order_qty_ship_file AS shipment_file_qty,
  order_qty_prod_file AS production_file_qty, shipped_qty AS shipped_shipment_file,
  shipped_qty_reported AS shipped_production_file,
  CASE WHEN order_qty_ship_file IS NOT NULL AND order_qty_ship_file <> order_qty THEN 'ORDER: Recap ≠ Shipment'
       WHEN order_qty_prod_file IS NOT NULL AND order_qty_prod_file <> order_qty THEN 'ORDER: Recap ≠ Production'
       WHEN shipped_qty_reported IS NOT NULL AND shipped_qty_reported <> shipped_qty + sample_qty
            AND shipped_qty_reported <> shipped_qty THEN 'SHIPPED: Shipment ≠ Production'
  END AS mismatch
FROM mart.style_360 WHERE is_active AND (order_qty_ship_file IS NOT NULL OR order_qty_prod_file IS NOT NULL);

CREATE TABLE mart.change_log AS
SELECT change_date AS event_date, season, style_no, 'QTY' AS change_type, color_raw AS detail,
       qty_before::VARCHAR AS before_value, qty_after::VARCHAR AS after_value, source, 'APPLIED' AS status, location
FROM core.qty_change
UNION ALL
SELECT event_date, season, style_no, 'FACTORY ' || action, coalesce(factory_hint, replace(note_raw, chr(10), ' | ')), NULL, factory_code,
       'ORDER RECAP note', 'APPLIED', location
FROM core.factory_event
UNION ALL
SELECT CAST(sent_at AS DATE), season, style_no, change_type, value_text,
       CASE WHEN change_type LIKE 'QTY%' THEN current_qty::VARCHAR WHEN change_type = 'ETD' THEN current_etd::VARCHAR ELSE color_from END,
       CASE WHEN change_type LIKE 'QTY%' THEN proposed_qty::VARCHAR WHEN change_type = 'ETD' THEN proposed_etd::VARCHAR ELSE color_to END,
       CASE WHEN is_sample THEN 'Email (SAMPLE)' ELSE 'Email' END, review_status, message_id
FROM core.change_proposal;

CREATE TABLE mart.issue_summary AS
SELECT i.severity, i.code, f.file_name, count(*) AS n
FROM etl.data_issue i LEFT JOIN etl.source_file f USING (file_id) GROUP BY ALL;

CREATE TABLE mart.source_lineage AS
SELECT f.file_id, f.file_name, f.source_type, f.parser, f.season, f.report_date, f.status, f.is_current,
       f.is_sample, f.rows_loaded, f.size_bytes, f.message, count(i.code) AS issues
FROM etl.source_file f LEFT JOIN etl.data_issue i USING (file_id) GROUP BY ALL;
