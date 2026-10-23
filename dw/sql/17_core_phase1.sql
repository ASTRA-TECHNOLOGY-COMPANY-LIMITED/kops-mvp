-- Phase-1 sources (D-02, spec analys-docs/mvp_phase1_spec.md §4): daily production reports, KLMAS inspection tracker,
-- third-party inspections. Current file of each source only (one daily file per factory; newest wins).

CREATE OR REPLACE MACRO core.rule_int(k) AS (SELECT rule_value::INT FROM stg.rule WHERE rule_key = k);
CREATE OR REPLACE MACRO core.today() AS (SELECT CAST(rule_value AS DATE) FROM stg.rule WHERE rule_key = 'today');

-- Working days (Monday-Saturday): index to add N working days, count between two dates
CREATE TABLE core.workday AS
SELECT CAST(d AS DATE) AS d, isodow(d) = 7 AS is_sunday,
       count(*) FILTER (WHERE isodow(d) <> 7) OVER (ORDER BY d) AS wd_index
FROM generate_series(DATE '2024-01-01', DATE '2028-12-31', INTERVAL 1 DAY) AS g(d);

-- ---------------------------------------------------------------- daily production
-- Rows of styles from an earlier season left in the sheet (HAGACO keeps LEV-24xxx delivered 08/2024): ETD / RDD before
-- the season's previous year -> carry-over, kept in raw only.
CREATE TABLE core.daily_row AS
SELECT r.* EXCLUDE (style_raw), core.style_key(r.style_raw) AS style_no, r.style_raw,
       r.style_raw <> core.style_key(r.style_raw) AS style_alias_used
FROM raw.daily_prod_row r JOIN core.current_file f USING (file_id)
WHERE coalesce(year(coalesce(r.rdd, r.etd)), 9999) >= 2000 + CAST(left(r.season, 2) AS INT) - 1
  -- DHG file numbers carry the year: LEV-24049 is a 2024 order
  AND coalesce(CAST(nullif(regexp_extract(r.style_raw, '^[A-Z]{3}-(\d{2})\d{3}', 1), '') AS INT), 99)
      >= CAST(left(r.season, 2) AS INT) - 1;

-- Last-seen (§4.1): factories delete finished styles from the day sheet, so progress = the last day a row was there
CREATE TABLE core.daily_progress AS
SELECT customer, brand, season, factory_code, style_no, color, size_code,
       arg_max(order_qty, report_date) AS order_qty, arg_max(cut_ttl, report_date) AS cut_ttl,
       arg_max(input_ttl, report_date) AS input_ttl, arg_max(output_ttl, report_date) AS output_ttl,
       max(report_date) AS last_seen_date
FROM core.daily_row GROUP BY ALL;

-- Output per day: the change of TTL since the previous report of the style; TODAY only when TTL is missing or for the
-- first report. Spec §4.2 reads TODAY first, but factories leave TODAY unchanged after a style is finished
-- (TRUONG PHUC CHF3WVT6708: TODAY 300 every day while TTL stays 300), which counted the same pieces again
-- (DAILY_TODAY_STALE in etl.data_issue via 15_issues).
CREATE TABLE core.daily_output_series AS
WITH d AS (
  SELECT customer, brand, season, factory_code, style_no, report_date, sum(output_today) AS today_sum,
         count(output_today) AS n_today, sum(output_ttl) AS ttl, count(output_ttl) AS n_ttl,
         sum(input_today) AS input_day, sum(cut_today) AS cut_day
  FROM core.daily_row GROUP BY ALL),
l AS (SELECT *, lag(ttl) OVER (PARTITION BY customer, factory_code, style_no ORDER BY report_date) AS prev_ttl FROM d)
SELECT customer, brand, season, factory_code, style_no, report_date,
       CASE WHEN n_ttl > 0 AND prev_ttl IS NOT NULL THEN greatest(ttl - prev_ttl, 0)
            WHEN n_today > 0 THEN today_sum ELSE ttl END AS output_day,
       today_sum AS output_today_reported, ttl AS output_ttl, input_day, cut_day
FROM l;

-- Forecast (§4.3): rolling rate of the last 3 days with output within 10 days before the last report
CREATE TABLE mart.style_forecast AS
WITH last AS (
  SELECT customer, brand, season, style_no, any_value(factory_code) AS factory_code, max(last_seen_date) AS as_of,
         sum(output_ttl) AS output_ttl
  FROM core.daily_progress GROUP BY ALL),
rated AS (
  SELECT l.*, (SELECT avg(output_day) FROM (
                 SELECT s.output_day FROM core.daily_output_series s
                 WHERE s.customer = l.customer AND s.style_no = l.style_no AND s.output_day > 0
                   AND s.report_date <= l.as_of AND s.report_date > l.as_of - core.rule_int('rate_lookback_days')
                 ORDER BY s.report_date DESC LIMIT 3)) AS rate,
         (SELECT count(*) FROM core.daily_output_series s
          WHERE s.customer = l.customer AND s.style_no = l.style_no AND s.output_day > 0
            AND s.report_date <= l.as_of AND s.report_date > l.as_of - core.rule_int('rate_lookback_days')) AS n_days
  FROM last l),
o AS (
  SELECT r.*, p.order_qty, p.etd AS etd_vn, p.is_active,
         coalesce(r.rate, core.rule_int('default_daily_output')) AS rate_used,
         p.order_qty - r.output_ttl AS remaining
  FROM rated r LEFT JOIN core.order_portfolio p ON p.customer = r.customer AND p.season = r.season AND p.style_no = r.style_no),
f AS (
  SELECT o.*, CASE WHEN remaining > 0 THEN (SELECT w2.d FROM core.workday w1 JOIN core.workday w2
                                            ON w2.wd_index = w1.wd_index + CAST(ceil(o.remaining / o.rate_used) AS INT)
                                            AND NOT w2.is_sunday WHERE w1.d = o.as_of) END AS finish_date
  FROM o)
SELECT customer, brand, season, style_no, factory_code, as_of, order_qty, output_ttl, remaining,
       round(rate_used, 1) AS rate, finish_date,
       finish_date + core.rule_int('ready_buffer_days') AS ready_date, etd_vn,
       CASE WHEN finish_date IS NOT NULL AND etd_vn IS NOT NULL
            THEN date_diff('day', etd_vn, finish_date + core.rule_int('ready_buffer_days')) END AS days_late,
       'DAILY_REPORT' AS forecast_source,
       CASE WHEN rate IS NULL THEN 'LOW'
            WHEN n_days >= 3 AND (SELECT count(*) FROM core.workday w WHERE w.d > as_of AND w.d <= core.today() AND NOT w.is_sunday) <= 2
              THEN 'HIGH' ELSE 'MEDIUM' END AS forecast_confidence,
       remaining <= 0 AS sewing_done
FROM f;

-- Freshness (§4.4): weekdays (Mon-Fri) strictly between the factory's last daily report and today (assumption
-- ASM-FRESH-01: reproduces spec G8 and 'TBM / TRUONG PHUC FRESH' on 2026-10-19); KOPS_TODAY fixes 'today'.
CREATE OR REPLACE MACRO mart.weekdays_between(a, b) AS (
  SELECT count(*) FROM core.workday w WHERE w.d > a AND w.d < b AND isodow(w.d) <= 5);
CREATE OR REPLACE MACRO mart.freshness_level(last_report, today) AS (
  CASE WHEN last_report IS NULL THEN 'DARK'
       WHEN mart.weekdays_between(last_report, today) <= 2 THEN 'FRESH'
       WHEN mart.weekdays_between(last_report, today) <= 5 THEN 'STALE'
       ELSE 'DARK' END);

CREATE TABLE mart.factory_freshness AS
WITH running AS (SELECT customer, season, factory_code, count(*) AS styles_running
                 FROM core.order_portfolio WHERE is_active AND factory_code IS NOT NULL GROUP BY ALL),
rep AS (SELECT customer, season, factory_code, max(report_date) AS last_report FROM core.daily_row GROUP BY ALL)
SELECT coalesce(r.customer, p.customer) AS customer, coalesce(r.season, p.season) AS season,
       coalesce(r.factory_code, p.factory_code) AS factory_code, p.last_report, r.styles_running,
       core.today() AS today,
       CASE WHEN p.last_report IS NOT NULL THEN mart.weekdays_between(p.last_report, core.today()) END AS weekdays_since,
       mart.freshness_level(p.last_report, core.today()) AS freshness
FROM running r FULL JOIN rep p ON p.customer = r.customer AND p.season = r.season AND p.factory_code = r.factory_code;
-- note: a factory with running styles and no report at all is DARK (last_report NULL)

CREATE TABLE mart.style_freshness AS
WITH s AS (
  SELECT o.customer, o.season, o.style_no, o.factory_code, o.order_qty,
         (SELECT sum(qty) FROM core.shipment_detail d WHERE d.style_no = o.style_no AND d.section = 'SHIPMENT') AS shipped
  FROM core.order_portfolio o WHERE o.is_active),
p AS (SELECT customer, style_no, max(last_seen_date) AS last_seen, sum(output_ttl) AS output_ttl
      FROM core.daily_progress GROUP BY ALL)
SELECT s.*, p.last_seen, p.output_ttl, f.last_report AS factory_last_report,
       CASE WHEN p.last_seen IS NULL THEN 'NO_REPORT'
            WHEN p.output_ttl < s.order_qty AND f.last_report > p.last_seen THEN 'STOPPED_REPORTING'
            ELSE coalesce(f.freshness, 'DARK') END AS freshness
FROM s LEFT JOIN p ON p.customer = s.customer AND p.style_no = s.style_no
LEFT JOIN mart.factory_freshness f ON f.customer = s.customer AND f.season = s.season AND f.factory_code = s.factory_code
WHERE coalesce(s.shipped, 0) < s.order_qty;

-- ---------------------------------------------------------------- KLMAS inspection tracker
-- Passed qty per style x piece x colour x day; the same cell copied in several sheets counts once (max). Only the
-- sheet of the style's factory in ORDER RECAP counts (INSPECTION_STYLE_FACTORY_MISMATCH otherwise).
CREATE TABLE core.inspection_cell AS
SELECT c.*, core.style_key(c.style_no) AS style_key_no, o.factory_code AS recap_factory,
       o.factory_code IS NOT NULL AND o.factory_code <> c.factory_code AS factory_mismatch
FROM raw.inspection_cell c JOIN core.current_file f USING (file_id)
LEFT JOIN (SELECT style_no, any_value(factory_code) AS factory_code FROM core.order_portfolio GROUP BY style_no) o
  ON o.style_no = core.style_key(c.style_no);

CREATE TABLE core.inspection_passed AS
SELECT style_key_no AS style_no, piece, color, inspect_date, factory_code, max(passed_qty) AS passed_qty,
       any_value(order_qty) AS order_qty
FROM core.inspection_cell WHERE NOT factory_mismatch GROUP BY ALL;

-- Factory x day: passed (A), inspected (C), defects (D, defect points: ASM-QC-01 / Q26), inspectors (F); no names
CREATE TABLE core.inspection_day AS
SELECT factory_code, inspect_date,
       max(value) FILTER (WHERE measure = 'passed_qty') AS passed_qty,
       max(value) FILTER (WHERE measure = 'inspected_qty') AS inspected_qty,
       max(value) FILTER (WHERE measure = 'defect_qty') AS defect_qty,
       max(value) FILTER (WHERE measure = 'n_inspectors') AS n_inspectors
FROM raw.inspection_day d JOIN core.current_file f USING (file_id) GROUP BY ALL;

CREATE TABLE core.inspection_proposal AS        -- 'REQUEST ETD m/d' in the tracker remark: PENDING_REVIEW, never applied
SELECT r.file_id, r.sheet, core.style_key(r.style_no) AS style_no, r.piece, r.color, r.request_etd, r.remark,
       o.etd AS current_etd, 'INSPECTION' AS source, 'PENDING_REVIEW' AS review_status
FROM stg.inspection_remark r JOIN core.current_file f USING (file_id)
LEFT JOIN (SELECT style_no, any_value(etd) AS etd FROM core.order_portfolio GROUP BY style_no) o ON o.style_no = core.style_key(r.style_no);

-- Passed vs ordered per style (and piece): a set counts as many as its scarcer piece (Q10)
CREATE TABLE mart.inspection_style AS
WITH p AS (SELECT style_no, piece, sum(passed_qty) AS passed FROM core.inspection_passed GROUP BY ALL),
o AS (SELECT style_no, sum(order_qty) AS ordered FROM core.order_color WHERE is_active GROUP BY ALL)
SELECT p.style_no, p.piece, p.passed, o.ordered,
       p.passed > o.ordered * (1 + core.rule_int('qty_tolerance_pct') / 100.0) AS passed_gt_order
FROM p LEFT JOIN o USING (style_no);

-- ---------------------------------------------------------------- third-party inspections (M1-12)
CREATE TABLE core.qc_inspection AS
SELECT q.*, core.factory_code(q.factory_raw) AS factory_code,
       round(q.defect_qty / nullif(q.inspected_qty, 0), 4) AS defect_rate     -- ASM-QC-01 (Q26): defects / inspected
FROM raw.qc_inspection q JOIN core.current_file f USING (file_id);
CREATE TABLE core.qc_defect AS
SELECT d.*, c.code_group, c.name_ko FROM raw.qc_defect d JOIN core.current_file f USING (file_id)
LEFT JOIN raw.defect_code c ON c.code = d.code;
CREATE TABLE core.defect_code AS SELECT c.code, c.name_ko, c.code_group FROM raw.defect_code c JOIN core.current_file f USING (file_id);

-- TODAY that does not match the change of TTL (stale TODAY after a style is finished, or typing errors)
INSERT INTO etl.data_issue
SELECT NULL, 'INFO', 'DAILY_TODAY_STALE', factory_code || ' ' || style_no,
       count(*) || ' report day(s) where OUT PUT TODAY differs from the change of TTL; TTL change used', min(report_date)::VARCHAR
FROM core.daily_output_series WHERE output_today_reported IS NOT NULL AND output_today_reported <> output_day GROUP BY ALL;
