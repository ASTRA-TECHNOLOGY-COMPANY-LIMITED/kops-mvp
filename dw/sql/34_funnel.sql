-- Style funnel per colour x size (M1-07, E-03): order -> cut -> sewn -> inspected -> shipped, real data only.
-- Sources: daily production reports (order / cut / output per colour x size, last-seen values, core.daily_progress),
-- Shipment Status (SHIPMENT lots, no samples, per colour x size), ORDER RECAP (order per colour) and the KLMAS
-- inspection tracker (passed per colour; the tracker has no size). level = 'SIZE' rows carry the size measures,
-- level = 'COLOR' rows the colour totals plus RECAP order and passed inspection.
-- Flags (tolerance qty_tolerance_pct, Q13):
--   CUT_SHORT      cut < order x (1 - tol) while the colour/size is already shipping or the style ETD has passed
--   OUTPUT_GT_CUT  sewn > cut (more pieces sewn than cut)
--   SHIP_GT_ORDER  colour shipped > order x (1 + tol), order = RECAP (daily-report order when the colour is not in RECAP);
--                  per size, factories ship a few pieces over the size breakdown within the order tolerance, so not flagged
CREATE OR REPLACE MACRO mart.norm_cs(x) AS nullif(upper(trim(regexp_replace(CAST(x AS VARCHAR), '\s+', ' ', 'g'))), '');

CREATE TABLE mart.style_funnel AS
WITH s AS (SELECT style_key, customer, season, style_no, brand, factory_code, etd FROM dim.style),
d AS (                               -- daily reports, summed over factories (a moved style has rows in two files)
  SELECT s.style_key, mart.norm_cs(p.color) AS color, mart.norm_cs(p.size_code) AS size_code,
         sum(p.order_qty) AS order_daily, sum(p.cut_ttl) AS cut, sum(p.output_ttl) AS sewn, max(p.last_seen_date) AS last_seen
  FROM core.daily_progress p
  JOIN (SELECT DISTINCT customer, season, style_code, style_key FROM fact.daily_output WHERE style_key IS NOT NULL) k
    ON k.customer = p.customer AND k.season = p.season AND k.style_code = p.style_no     -- DHG file no. -> style (linked model)
  JOIN s ON s.style_key = k.style_key
  GROUP BY ALL),
sh AS (
  SELECT style_key, mart.norm_cs(color) AS color, mart.norm_cs(size_code) AS size_code, sum(qty) AS shipped
  FROM fact.shipment_line WHERE section = 'SHIPMENT' AND style_key IS NOT NULL AND NOT is_synthetic GROUP BY ALL),
sz AS (
  SELECT coalesce(d.style_key, sh.style_key) AS style_key, coalesce(d.color, sh.color) AS color,
         coalesce(d.size_code, sh.size_code) AS size_code, d.order_daily, d.cut, d.sewn, sh.shipped, d.last_seen
  FROM d FULL JOIN sh ON sh.style_key = d.style_key AND sh.color IS NOT DISTINCT FROM d.color
                     AND sh.size_code IS NOT DISTINCT FROM d.size_code),
rc AS (
  SELECT style_key, mart.norm_cs(color) AS color, sum(order_qty) AS order_recap
  FROM fact.order_line WHERE is_active AND style_key IS NOT NULL AND color IS NOT NULL GROUP BY ALL),
ins AS (                             -- sets: the scarcer piece counts (Q11)
  SELECT style_key, color, min(passed) AS passed FROM (
    SELECT style_key, mart.norm_cs(color) AS color, coalesce(piece, '') AS piece, sum(passed_qty) AS passed
    FROM fact.inspection WHERE source = 'KLMAS' AND style_key IS NOT NULL AND NOT is_synthetic GROUP BY ALL)
  GROUP BY ALL),
col AS (
  SELECT coalesce(a.style_key, rc.style_key, ins.style_key) AS style_key, coalesce(a.color, rc.color, ins.color) AS color,
         rc.order_recap, a.order_daily, a.cut, a.sewn, ins.passed, a.shipped, a.last_seen
  FROM (SELECT style_key, color, sum(order_daily) AS order_daily, sum(cut) AS cut, sum(sewn) AS sewn, sum(shipped) AS shipped,
               max(last_seen) AS last_seen FROM sz GROUP BY ALL) a
  FULL JOIN rc ON rc.style_key = a.style_key AND rc.color IS NOT DISTINCT FROM a.color
  FULL JOIN ins ON ins.style_key = coalesce(a.style_key, rc.style_key) AND ins.color IS NOT DISTINCT FROM coalesce(a.color, rc.color)),
u AS (
  SELECT 'SIZE' AS level, style_key, color, size_code, NULL::BIGINT AS order_recap, order_daily, cut, sewn,
         NULL::BIGINT AS passed, shipped, last_seen FROM sz
  UNION ALL
  SELECT 'COLOR', style_key, color, NULL, order_recap, order_daily, cut, sewn, passed, shipped, last_seen FROM col),
f AS (
  SELECT u.*, s.customer, s.season, s.brand, s.style_no, s.factory_code, s.etd,
         coalesce(u.order_recap, u.order_daily) AS order_qty, core.rule_int('qty_tolerance_pct') / 100.0 AS tol
  FROM u JOIN s USING (style_key))
SELECT level, customer, season, brand, style_no, factory_code, etd, color, size_code, order_qty, order_recap, order_daily,
       cut, sewn, passed, shipped, last_seen,
       nullif(concat_ws(',',
         CASE WHEN level = 'SIZE' AND cut IS NOT NULL AND order_qty > 0 AND cut < order_qty * (1 - tol)
                   AND (coalesce(shipped, 0) > 0 OR etd < core.today()) THEN 'CUT_SHORT' END,
         CASE WHEN level = 'SIZE' AND sewn > cut THEN 'OUTPUT_GT_CUT' END,
         CASE WHEN level = 'COLOR' AND shipped > order_qty * (1 + tol) THEN 'SHIP_GT_ORDER' END), '') AS flags,
       false AS is_synthetic
FROM f
WHERE coalesce(order_qty, cut, sewn, passed, shipped) IS NOT NULL;     -- empty size rows left in the report sheet
