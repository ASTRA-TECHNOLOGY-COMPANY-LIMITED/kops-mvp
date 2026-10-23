-- Action list for the running season (E-04, page "Việc cần xử lý"): one row per thing a manager should act on,
-- real data only. The reason is stored as a type + arguments (d1, d2, n1, txt) so the page can word it in VI or KO.
-- severity: 1 = critical, 2 = high, 3 = medium. owner stays NULL: KLMAS has no assignment table yet (Q50).
-- Types:
--   PLAN_LATE         production plan: BAL < 0, or finish + ready buffer + transit (rdd_offset_days, Q26) > RDD
--   FORECAST_LATE     daily-report forecast ready + transit > RDD, or ETD passed and not shipped (mgr_style.risk_reason)
--   MATERIAL_LATE     material for the factory arrives after the planned cut date (inbound_material events in e-mail;
--                     arrival = ETA, else ETD + 7 days, assumption ASM-MAT-01)
--   APPROVAL_MISSING  cut planned from 7 days ago to 21 days ahead, nothing shipped, and no FPP CFMD / DM approval milestone
--                     on or before the cut date in e-mails or documents
--   DAILY_STALE       factory with running styles has sent no daily report for more than 1 weekday (Q32, ASM-FRESH-01)
--   PROPOSAL_PENDING  change read from an e-mail waiting for review (PENDING_REVIEW)
--   FILE_MISMATCH     numbers differ between files / a total cell is wrong (priority 1 findings), or the ETD / cut date
--                     lies more than 120 days before the season starts (year typed wrong, Q46: txt ETD_YEAR); actions that
--                     rely on the suspect date are not raised (ETD -> FORECAST_LATE, cut date -> plan / material / approval)
CREATE TABLE mart.mgr_action AS
WITH st AS (
  SELECT s.style_key, s.customer, s.season, s.brand, s.style_no, s.style_nk, s.factory_code, s.etd, s.rdd, s.order_qty,
         m.shipped, m.risk_reason, m.ready_date,
         coalesce(s.etd < n.start_date - 120, false) AS etd_suspect, coalesce(p.cut_plan < n.start_date - 120, false) AS cut_suspect,
         n.start_date
  FROM dim.style s LEFT JOIN mart.mgr_style m USING (style_key) LEFT JOIN dim.season n ON n.season = s.season
  LEFT JOIN (SELECT style_key, min(cut_plan) AS cut_plan FROM fact.plan GROUP BY 1) p USING (style_key)
  WHERE s.is_active AND NOT coalesce(m.style_syn, false)),
open_st AS (     -- not shipped in full yet (tolerance Q13)
  SELECT * FROM st WHERE coalesce(shipped, 0) < order_qty * (1 - core.rule_int('qty_tolerance_pct') / 100.0)),
pl AS (
  SELECT p.*, f.file_name FROM fact.plan p LEFT JOIN etl.source_file f ON f.file_id = p.source_file_id
  WHERE p.style_key IS NOT NULL AND NOT p.is_synthetic),
plan_late AS (
  SELECT 'PLAN_LATE' AS action_type,
         CASE WHEN coalesce(p.cut_plan, s.etd) <= core.today() + 14 THEN 1 ELSE 2 END AS severity,
         greatest(coalesce(p.cut_plan, s.etd), core.today()) AS due_date, s.style_key, s.factory_code,
         p.finish_plan AS d1, coalesce(p.rdd, s.rdd) AS d2, p.bal_calc AS n1,
         CASE WHEN p.bal_calc < 0 THEN 'BAL' ELSE 'TRANSIT' END AS txt,
         p.file_name || coalesce(' · ' || p.source_ref, '') AS source
  FROM pl p JOIN open_st s USING (style_key)
  WHERE NOT s.cut_suspect AND (p.bal_calc < 0
     OR p.finish_plan + core.rule_int('ready_buffer_days') + core.rule_int('rdd_offset_days') > coalesce(p.rdd, s.rdd))),
forecast_late AS (
  SELECT 'FORECAST_LATE', 1, core.today(), style_key, factory_code, ready_date, CASE WHEN risk_reason = 'ETD_PASSED_NOT_SHIPPED' THEN etd ELSE rdd END,
         NULL::BIGINT, risk_reason, 'ORDER RECAP · Shipment Status · DAILY PRODUCTION REPORT'
  FROM open_st WHERE risk_reason IN ('FORECAST_AFTER_RDD', 'ETD_PASSED_NOT_SHIPPED') AND NOT etd_suspect),
mat AS (
  SELECT e.*, f.factory_code AS ev_factory, coalesce(e.eta, e.etd_new + 7) AS arrival
  FROM fact.shipment_event e JOIN dim.factory f USING (factory_key)
  WHERE e.direction = 'inbound_material' AND NOT e.is_sample),
material_late AS (
  SELECT 'MATERIAL_LATE', CASE WHEN p.cut_plan <= core.today() + 7 THEN 1 ELSE 2 END, greatest(p.cut_plan, core.today()),
         s.style_key, s.factory_code, m.arrival, p.cut_plan, date_diff('day', p.cut_plan, m.arrival), m.booking,
         'Email: ' || m.subject
  FROM pl p JOIN open_st s USING (style_key)
  JOIN mat m ON m.ev_factory = s.factory_code AND (m.customer IS NULL OR m.customer = s.customer)
  WHERE NOT s.cut_suspect AND p.cut_plan >= core.today() - 7 AND m.arrival > p.cut_plan AND m.etd_new >= p.cut_plan - 45),
appr AS (
  SELECT style_key, max(event_date) FILTER (WHERE milestone = 'FPP_CFMD') AS fpp, max(event_date) FILTER (WHERE milestone = 'DM_APPROVAL') AS dm
  FROM fact.milestone WHERE NOT is_sample AND style_key IS NOT NULL GROUP BY 1),
approval_missing AS (
  SELECT 'APPROVAL_MISSING', CASE WHEN p.cut_plan <= core.today() + 7 THEN 1 ELSE 2 END, greatest(p.cut_plan, core.today()),
         s.style_key, s.factory_code, p.cut_plan, NULL::DATE, NULL::BIGINT,
         concat_ws(',', CASE WHEN a.fpp IS NULL OR a.fpp > p.cut_plan THEN 'FPP_CFMD' END,
                        CASE WHEN a.dm IS NULL OR a.dm > p.cut_plan THEN 'DM_APPROVAL' END),
         p.file_name || ' (CUT) · e-mail / documents (FPP CFMD, DM)'
  FROM pl p JOIN open_st s USING (style_key) LEFT JOIN appr a USING (style_key)
  WHERE NOT s.cut_suspect AND p.cut_plan BETWEEN core.today() - 7 AND core.today() + 21 AND coalesce(s.shipped, 0) = 0
    AND (a.fpp IS NULL OR a.fpp > p.cut_plan OR a.dm IS NULL OR a.dm > p.cut_plan)),
running AS (     -- factory x customer x season with styles on the line: cut planned / reported, not shipped, ETD not long past
  SELECT s.customer, s.season, s.factory_code, count(*) AS n
  FROM open_st s LEFT JOIN (SELECT style_key, min(cut_plan) AS cut_plan FROM pl GROUP BY 1) p USING (style_key)
  WHERE s.factory_code IS NOT NULL AND s.etd >= core.today() - 30
    AND (p.cut_plan <= core.today() OR s.style_key IN (SELECT style_key FROM fact.daily_output WHERE NOT is_synthetic))
  GROUP BY ALL),
last_rep AS (SELECT customer, factory_code, max(report_date) AS last_report FROM core.daily_row GROUP BY ALL),
daily_stale AS (
  SELECT 'DAILY_STALE', CASE WHEN l.last_report IS NULL OR mart.weekdays_between(l.last_report, core.today()) > 5 THEN 2 ELSE 3 END,
         core.today(), NULL::BIGINT, r.factory_code, l.last_report, NULL::DATE,
         CASE WHEN l.last_report IS NOT NULL THEN mart.weekdays_between(l.last_report, core.today()) END, r.n::VARCHAR,
         coalesce('DAILY PRODUCTION REPORT ' || strftime(l.last_report, '%d/%m'), 'DAILY PRODUCTION REPORT: –'),
         r.customer, r.season
  FROM running r LEFT JOIN last_rep l USING (customer, factory_code)
  WHERE l.last_report IS NULL OR mart.weekdays_between(l.last_report, core.today()) > 1),
proposal AS (
  SELECT 'PROPOSAL_PENDING', 3, greatest(coalesce(s.etd, core.today()), core.today()), c.style_key, coalesce(c.factory_code, s.factory_code),
         c.fact_date, NULL::DATE, NULL::BIGINT, c.change_type || ': ' || coalesce(c.before_v || ' → ', '') || coalesce(c.after_v, ''),
         coalesce('Email: ' || e.subject, c.source)
  FROM (SELECT DISTINCT style_key, factory_code, change_type, fact_date, before_v, after_v, source, source_ref
        FROM fact.change WHERE review_status = 'PENDING_REVIEW') c
  JOIN st s USING (style_key)
  LEFT JOIN (SELECT msg_key, any_value(subject) AS subject FROM fact.email GROUP BY 1) e ON e.msg_key = c.source_ref),
mismatch AS (
  SELECT 'FILE_MISMATCH', 2, core.today(), s.style_key, s.factory_code, NULL::DATE, NULL::DATE, NULL::BIGINT, r.detail,
         r.check_name || coalesce(': ' || f.file_name, ''), coalesce(s.customer, split_part(f.family, '|', 1)), coalesce(r.season, s.season, f.season)
  FROM mart.mgr_recon r
  LEFT JOIN st s ON s.style_no = r.ref AND s.season = r.season
  LEFT JOIN etl.source_file f ON f.file_name = r.ref
  WHERE r.check_name IN ('Recap vs Shipment / Production', 'File total cell')
  UNION ALL
  SELECT 'FILE_MISMATCH', 2, core.today(), s.style_key, s.factory_code, CASE WHEN s.etd_suspect THEN s.etd ELSE p.cut_plan END,
         s.start_date, NULL::BIGINT, 'ETD_YEAR',
         CASE WHEN s.etd_suspect THEN 'ORDER RECAP (ETD)' ELSE 'PRODUCTION PLAN (CUT)' END, s.customer, s.season
  FROM st s LEFT JOIN (SELECT style_key, min(cut_plan) AS cut_plan FROM fact.plan GROUP BY 1) p USING (style_key)
  WHERE s.etd_suspect OR s.cut_suspect),
styled AS (
  SELECT * FROM plan_late UNION ALL SELECT * FROM forecast_late UNION ALL SELECT * FROM material_late
  UNION ALL SELECT * FROM approval_missing UNION ALL SELECT * FROM proposal),
a AS (
  SELECT y.*, s.customer, s.season FROM styled y JOIN st s USING (style_key)
  UNION ALL SELECT * FROM daily_stale
  UNION ALL SELECT * FROM mismatch)
SELECT row_number() OVER (ORDER BY a.severity, a.due_date, a.action_type, s.style_no, a.factory_code) AS action_id,
       a.action_type, a.severity, a.due_date, a.customer, a.season, s.brand, s.style_nk, s.style_no, a.factory_code,
       a.d1, a.d2, a.n1, a.txt, a.source, NULL::VARCHAR AS owner, false AS is_synthetic
FROM a LEFT JOIN st s USING (style_key);
