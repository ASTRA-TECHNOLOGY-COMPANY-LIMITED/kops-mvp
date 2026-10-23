-- Marts for the manager charts added in F-05 (definitions: dw/docs/metrics.md). Real data only, except where a column says
-- *_syn. One row per style where possible, so the page filters by customer / season / brand / factory itself.

-- Milestones and stage dates per style: milestone funnel (how far each style got) and lead time of each stage
CREATE TABLE mart.mgr_style_stage AS
WITH ms AS (
  SELECT style_key, min(event_date) FILTER (WHERE milestone = 'FPP_REQUEST') AS fpp_request,
         min(event_date) FILTER (WHERE milestone = 'FPP_CFMD') AS fpp_cfmd, min(event_date) FILTER (WHERE milestone = 'DM_APPROVAL') AS dm_approval
  FROM fact.milestone WHERE NOT is_sample AND style_key IS NOT NULL GROUP BY 1)
SELECT m.style_nk, m.customer, m.season, m.brand, m.style_no, m.factory_code, m.order_qty, m.is_active,
       ms.fpp_request, ms.fpp_cfmd, ms.dm_approval, m.cut_plan, m.first_lot_etd,
       ms.fpp_request IS NOT NULL AS st_fpp, ms.fpp_cfmd IS NOT NULL AS st_cfmd, ms.dm_approval IS NOT NULL AS st_dm,
       -- a later stage implies the earlier ones (a shipped style was cut, sewn and inspected even when a file is missing)
       (m.cut_plan <= core.today() OR coalesce(m.output_qty, 0) > 0 OR coalesce(m.passed, m.inspected, 0) > 0 OR coalesce(m.shipped, 0) > 0) AS st_cut,
       (coalesce(m.output_qty, 0) > 0 OR coalesce(m.passed, m.inspected, 0) > 0 OR coalesce(m.shipped, 0) > 0) AS st_sewn,
       (coalesce(m.passed, m.inspected, 0) > 0 OR coalesce(m.shipped, 0) > 0) AS st_inspected, coalesce(m.shipped, 0) > 0 AS st_shipped,
       date_diff('day', ms.fpp_request, ms.fpp_cfmd) AS days_fpp_cfmd,
       date_diff('day', ms.fpp_cfmd, m.cut_plan) AS days_cfmd_cut,
       date_diff('day', m.cut_plan, m.first_lot_etd) AS days_cut_ship,
       m.out_syn OR m.insp_syn OR m.ship_syn AS stage_syn
FROM mart.mgr_style m LEFT JOIN ms USING (style_key)
WHERE NOT m.style_syn;

-- Quantity bridge per customer x season (waterfall): order at the first RECAP version -> decreases / increases noted in
-- RECAP (QTY_NOTE) or between versions (VERSION_QTY) -> current order -> cut -> sewn -> shipped (real only).
-- Cut: daily reports (last-seen CUTTING TTL); styles without daily reports count their sewn qty (cut >= sewn).
CREATE TABLE mart.mgr_qty_bridge AS
WITH d AS (
  SELECT c.customer, c.season, sum(try_cast(c.after_v AS INT) - try_cast(c.before_v AS INT)) FILTER (WHERE try_cast(c.after_v AS INT) < try_cast(c.before_v AS INT)) AS decreases,
         sum(try_cast(c.after_v AS INT) - try_cast(c.before_v AS INT)) FILTER (WHERE try_cast(c.after_v AS INT) > try_cast(c.before_v AS INT)) AS increases
  FROM fact.change c WHERE c.change_type IN ('QTY_NOTE', 'VERSION_QTY') GROUP BY ALL),
cut AS (SELECT customer, season, style_no, sum(cut) AS cut FROM mart.style_funnel WHERE level = 'SIZE' GROUP BY ALL),
s AS (
  SELECT m.customer, m.season, sum(m.order_qty) AS order_now,
         sum(coalesce(c.cut, CASE WHEN NOT m.out_syn THEN m.output_qty END, 0)) AS cut,
         sum(CASE WHEN NOT m.out_syn THEN coalesce(m.output_qty, 0) END) AS sewn,
         sum(CASE WHEN NOT m.ship_syn THEN coalesce(m.shipped, 0) END) AS shipped,
         count(*) FILTER (WHERE c.cut IS NOT NULL) AS styles_with_cut, count(*) AS styles
  FROM mart.mgr_style m LEFT JOIN cut c ON c.customer = m.customer AND c.season = m.season AND c.style_no = m.style_no
  WHERE m.is_active AND NOT m.style_syn GROUP BY ALL)
SELECT s.customer, s.season, s.order_now - coalesce(d.decreases, 0) - coalesce(d.increases, 0) AS order_initial,
       coalesce(d.decreases, 0) AS decreases, coalesce(d.increases, 0) AS increases, s.order_now, s.cut, s.sewn, s.shipped,
       s.styles_with_cut, s.styles
FROM s LEFT JOIN d USING (customer, season);
