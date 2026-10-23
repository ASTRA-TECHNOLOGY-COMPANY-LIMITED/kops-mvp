-- Cycle coverage (D-04): for every customer x season, which stages of the order cycle have real data.
-- REAL = enough to measure the stage, PARTIAL = some, NONE = nothing. A cycle is complete ('đủ') when it has ORDER,
-- PLAN (or PRODUCTION STATUS), DAILY_OUTPUT (or output in the status), INSPECTION, and SHIPMENT >= 80% of the qty.
CREATE TABLE mart.cycle_coverage AS
WITH cs AS (SELECT DISTINCT customer, season FROM dim.style),
act AS (SELECT customer, season, count(*) AS styles, sum(order_qty) AS qty FROM dim.style WHERE is_active GROUP BY ALL),
st AS (
  SELECT 'ORDER' AS stage, s.customer, s.season, count(*) AS rows, max(fact_date) AS latest,
         count(DISTINCT style_key) AS styles
  FROM fact.order_line s GROUP BY ALL
  UNION ALL
  SELECT 'PLAN', customer, season, count(*), max(as_of), count(DISTINCT style_key) FROM fact.plan GROUP BY ALL
  UNION ALL
  SELECT 'PLAN', customer, season, count(*), max(fact_date), count(DISTINCT style_key) FROM fact.production_status GROUP BY ALL
  UNION ALL
  SELECT 'DAILY_OUTPUT', d.customer, d.season, count(*), max(d.fact_date), count(DISTINCT d.style_key)
  FROM fact.daily_output d GROUP BY ALL
  UNION ALL
  SELECT 'DAILY_OUTPUT', customer, season, count(*), max(fact_date), count(DISTINCT style_key)
  FROM fact.production_status WHERE output_qty > 0 GROUP BY ALL
  UNION ALL
  SELECT 'INSPECTION', s.customer, s.season, count(*), max(i.fact_date), count(DISTINCT i.style_key)
  FROM fact.inspection i JOIN dim.style s USING (style_key) WHERE i.source = 'KLMAS' GROUP BY ALL
  UNION ALL
  SELECT 'INSPECTION', customer, season, count(*), max(fact_date), count(DISTINCT style_key)
  FROM fact.production_status WHERE inspected_qty > 0 GROUP BY ALL
  UNION ALL
  SELECT 'SHIPMENT', customer, season, count(*), max(fact_date), count(DISTINCT style_key) FROM fact.shipment_lot GROUP BY ALL
  UNION ALL
  SELECT 'EMAIL', s.customer, s.season, count(DISTINCT b.msg_key), max(e.sent_at)::DATE, count(DISTINCT b.style_key)
  FROM bridge.email_style b JOIN dim.style s USING (style_key) JOIN fact.email e USING (msg_key) WHERE NOT e.is_sample
  GROUP BY ALL
  UNION ALL
  SELECT 'HISTORY', split_part(family, '|', 1), season, count(*), max(file_date), NULL
  FROM mart.file_version WHERE parser IN ('order_recap', 'order_recap_ext') GROUP BY ALL),
agg AS (SELECT stage, customer, season, sum(rows) AS rows, max(latest) AS latest, max(styles) AS styles FROM st GROUP BY ALL),
shipped AS (SELECT customer, season, sum(qty) AS shipped FROM fact.shipment_lot GROUP BY ALL),
stages AS (SELECT unnest(['ORDER', 'PLAN', 'DAILY_OUTPUT', 'INSPECTION', 'SHIPMENT', 'EMAIL', 'HISTORY']) AS stage)
SELECT cs.customer, cs.season, g.stage, coalesce(a.rows, 0) AS rows, a.latest, a.styles AS styles_covered, act.styles AS active_styles,
       CASE WHEN g.stage = 'SHIPMENT' THEN round(100.0 * sh.shipped / nullif(act.qty, 0), 1)
            WHEN g.stage IN ('PLAN', 'DAILY_OUTPUT', 'INSPECTION') THEN round(100.0 * a.styles / nullif(act.styles, 0), 1) END
         AS pct,
       CASE WHEN coalesce(a.rows, 0) = 0 THEN 'NONE'
            WHEN g.stage = 'SHIPMENT' AND sh.shipped >= 0.8 * act.qty THEN 'REAL'
            WHEN g.stage = 'SHIPMENT' THEN 'PARTIAL'
            WHEN g.stage IN ('PLAN', 'DAILY_OUTPUT', 'INSPECTION') AND a.styles >= 0.5 * act.styles THEN 'REAL'
            WHEN g.stage IN ('PLAN', 'DAILY_OUTPUT', 'INSPECTION') THEN 'PARTIAL'
            WHEN g.stage = 'HISTORY' AND a.rows >= 2 THEN 'REAL'
            WHEN g.stage = 'HISTORY' THEN 'PARTIAL'
            ELSE 'REAL' END AS coverage
FROM cs CROSS JOIN stages g
LEFT JOIN agg a ON a.stage = g.stage AND a.customer = cs.customer AND a.season = cs.season
LEFT JOIN act ON act.customer = cs.customer AND act.season = cs.season
LEFT JOIN shipped sh ON sh.customer = cs.customer AND sh.season = cs.season;

CREATE TABLE mart.cycle_complete AS
SELECT customer, season,
       bool_and(coverage <> 'NONE') FILTER (WHERE stage IN ('ORDER', 'PLAN', 'DAILY_OUTPUT', 'INSPECTION'))
         AND bool_or(coverage = 'REAL') FILTER (WHERE stage = 'SHIPMENT') AS is_complete,
       string_agg(stage || ':' || coverage, ' ' ORDER BY stage) AS stages
FROM mart.cycle_coverage GROUP BY ALL;
