-- Manager metrics (D-05, definitions in dw/docs/metrics.md). Built on the linked model (fact / dim) plus the synthetic
-- data (schema sim). Every table keeps real and synthetic apart (is_synthetic or *_syn columns) and carries additive
-- measures (sums, counts) so the dashboard can recompute every ratio with or without the synthetic part.

-- ---------------------------------------------------------------- style grain (real + synthetic seasons)
CREATE TEMP TABLE m_style AS
SELECT s.style_key, s.style_nk, s.customer, s.brand, s.season, s.style_no, s.factory_code, s.order_qty, s.etd, s.rdd,
       s.is_active, false AS style_syn, NULL::VARCHAR AS style_asm
FROM dim.style s
UNION ALL
SELECT NULL, x.style_nk, x.customer, x.brand, x.season, x.style_code, x.factory_code, x.order_qty, x.etd, x.rdd, x.is_active,
       true, x.assumption_id
FROM sim.style x;

CREATE TEMP TABLE m_lot AS                -- first-quality shipments (no samples), real + synthetic
SELECT s.style_nk, l.lot_label, l.lot_etd, l.qty, l.ship_mode, false AS is_synthetic, NULL::VARCHAR AS assumption_id
FROM fact.shipment_lot l JOIN dim.style s USING (style_key)
UNION ALL
SELECT coalesce(d.style_nk, 'SIM|' || x.customer || '|' || x.season || '|' || x.style_code), x.lot_label, x.lot_etd, x.qty,
       x.ship_mode, true, x.assumption_id
FROM sim.shipment_lot x LEFT JOIN dim.style d ON d.style_key = x.style_key;

CREATE TEMP TABLE m_output AS             -- daily output (real daily reports + synthetic)
SELECT s.style_nk, o.factory_code, o.fact_date, o.output_day, o.output_ttl, false AS is_synthetic
FROM fact.daily_output o JOIN dim.style s USING (style_key)
UNION ALL
SELECT d.style_nk, x.factory_code, x.fact_date, x.output_day, x.output_ttl, true
FROM sim.daily_output x JOIN dim.style d ON d.style_key = x.style_key;

CREATE TEMP TABLE m_insp AS               -- inspections of KLMAS order styles: per style (real tracker / status, synthetic)
SELECT s.style_nk, max(i.fact_date) AS last_date, NULL::INTEGER AS inspected, sum(i.passed_qty) AS passed,
       NULL::INTEGER AS defects, 0 AS rejects, false AS is_synthetic
FROM fact.inspection i JOIN dim.style s USING (style_key) WHERE i.source = 'KLMAS' GROUP BY s.style_nk
UNION ALL
SELECT coalesce(d.style_nk, 'SIM|' || x.customer || '|' || x.season || '|' || x.style_code), max(x.fact_date),
       sum(x.inspected_qty), sum(x.passed_qty), sum(x.defect_qty), count(*) FILTER (WHERE x.result = 'REJECT'), true
FROM sim.inspection x LEFT JOIN dim.style d ON d.style_key = x.style_key GROUP BY 1;

CREATE TABLE mart.mgr_style AS
WITH ship AS (
  SELECT style_nk, sum(qty) AS shipped, min(lot_etd) AS first_lot_etd, max(lot_etd) AS last_lot_etd, count(*) AS n_lots,
         bool_or(is_synthetic) AS ship_syn, any_value(assumption_id) AS ship_asm
  FROM m_lot GROUP BY style_nk),
outp AS (
  SELECT style_nk, max(fact_date) AS out_last, arg_max(output_ttl, fact_date) AS output_ttl, bool_or(is_synthetic) AS out_syn
  FROM m_output GROUP BY style_nk),
ps AS (SELECT s.style_nk, p.output_qty, p.inspected_qty, p.fact_date AS ps_as_of
       FROM fact.production_status p JOIN dim.style s USING (style_key)),
plan AS (SELECT s.style_nk, min(p.bal_days) AS plan_bal, min(p.cut_plan) AS cut_plan, max(p.finish_plan) AS finish_plan
         FROM fact.plan p JOIN dim.style s USING (style_key) GROUP BY s.style_nk),
fc AS (SELECT s.style_nk, f.ready_date, f.days_late, f.forecast_confidence
       FROM mart.style_forecast f JOIN dim.style s ON s.customer = f.customer AND s.season = f.season AND s.style_no = f.style_no),
s360 AS (SELECT 'CHALLENGER|' || season || '|' || style_no AS style_nk, projected_ready FROM mart.style_360),
ins AS (SELECT style_nk, sum(inspected) AS inspected, sum(passed) AS passed, sum(defects) AS defects, sum(rejects) AS rejects,
               bool_or(is_synthetic) AS insp_syn FROM m_insp GROUP BY style_nk),
chg AS (SELECT s.style_nk, count(*) FILTER (WHERE c.change_type IN ('QTY_NOTE', 'VERSION_QTY')) AS n_qty_changes,
               count(*) FILTER (WHERE c.change_type IN ('FACTORY_MOVE', 'VERSION_FACTORY')) AS n_factory_changes,
               count(*) FILTER (WHERE c.change_type = 'VERSION_ETD') AS n_etd_changes,
               count(*) FILTER (WHERE c.change_type LIKE 'EMAIL_%' AND c.review_status = 'PENDING_REVIEW') AS pending_proposals
        FROM fact.change c JOIN dim.style s USING (style_key) GROUP BY s.style_nk),
asrt AS (SELECT s.style_nk, count(*) AS n_assort_changes FROM fact.milestone m JOIN dim.style s USING (style_key)
         WHERE m.milestone = 'ASSORT_CHANGE' GROUP BY s.style_nk),
eml AS (SELECT s.style_nk, count(DISTINCT b.msg_key) AS n_emails FROM bridge.email_style b JOIN dim.style s USING (style_key)
        GROUP BY s.style_nk)
SELECT m.*, coalesce(sh.shipped, 0) AS shipped, sh.first_lot_etd, sh.last_lot_etd, coalesce(sh.n_lots, 0) AS n_lots,
       coalesce(sh.ship_syn, false) AS ship_syn, sh.ship_asm,
       CASE WHEN sh.first_lot_etd IS NOT NULL AND m.etd IS NOT NULL THEN date_diff('day', m.etd, sh.first_lot_etd) END AS delay_days,
       CASE WHEN sh.first_lot_etd IS NOT NULL AND m.etd IS NOT NULL THEN sh.first_lot_etd <= m.etd END AS on_time,
       CASE WHEN sh.first_lot_etd IS NOT NULL AND m.etd IS NOT NULL
            THEN sh.first_lot_etd <= m.etd + mart.rule_int('ontime_tolerance_days') END AS on_time_tol,
       coalesce(o.output_ttl, ps.output_qty) AS output_qty, coalesce(o.out_syn, false) AS out_syn, o.out_last,
       pl.plan_bal, pl.cut_plan, pl.finish_plan, coalesce(fc.ready_date, s360.projected_ready) AS ready_date,
       fc.forecast_confidence,
       coalesce(i.inspected, ps.inspected_qty) AS inspected, i.passed, i.defects, coalesce(i.rejects, 0) AS rejects,
       coalesce(i.insp_syn, false) AS insp_syn,
       coalesce(c.n_qty_changes, 0) AS n_qty_changes, coalesce(c.n_factory_changes, 0) AS n_factory_changes,
       coalesce(c.n_etd_changes, 0) AS n_etd_changes, coalesce(a.n_assort_changes, 0) AS n_assort_changes,
       coalesce(c.pending_proposals, 0) AS pending_proposals, coalesce(e.n_emails, 0) AS n_emails
FROM m_style m
LEFT JOIN ship sh USING (style_nk) LEFT JOIN outp o USING (style_nk) LEFT JOIN ps USING (style_nk)
LEFT JOIN plan pl USING (style_nk) LEFT JOIN fc USING (style_nk) LEFT JOIN s360 USING (style_nk)
LEFT JOIN ins i USING (style_nk) LEFT JOIN chg c USING (style_nk) LEFT JOIN asrt a USING (style_nk) LEFT JOIN eml e USING (style_nk);

-- Risk (metrics.md): active, not shipped in full, and (forecast ready + transit > RDD, or plan BAL < 0, or ETD passed)
ALTER TABLE mart.mgr_style ADD COLUMN risk_reason VARCHAR;
UPDATE mart.mgr_style SET risk_reason = CASE
    WHEN NOT is_active OR order_qty IS NULL OR shipped >= order_qty * (1 - mart.rule_int('qty_tolerance_pct') / 100.0) THEN NULL
    WHEN ready_date IS NOT NULL AND rdd IS NOT NULL AND ready_date + mart.rule_int('rdd_offset_days') > rdd THEN 'FORECAST_AFTER_RDD'
    WHEN plan_bal < 0 THEN 'PLAN_BAL_NEGATIVE'
    WHEN etd IS NOT NULL AND etd < core.today() THEN 'ETD_PASSED_NOT_SHIPPED' END;

-- ---------------------------------------------------------------- weekly: ETD plan vs shipped vs output
-- ETDs far outside the season window (typed year) are left out of the weekly view; they stay in mgr_style.
CREATE TABLE mart.mgr_weekly AS
SELECT customer, season, factory_code, CAST(date_trunc('week', etd) AS DATE) AS week_start, 'ETD_PLAN' AS measure,
       sum(order_qty) AS qty, style_syn AS is_synthetic FROM mart.mgr_style m
WHERE is_active AND etd IS NOT NULL
  AND etd BETWEEN make_date(2000 + CAST(left(season, 2) AS INT) - 1, 6, 1) AND make_date(2001 + CAST(left(season, 2) AS INT), 3, 31)
GROUP BY ALL
UNION ALL
SELECT s.customer, s.season, s.factory_code, CAST(date_trunc('week', l.lot_etd) AS DATE), 'SHIPPED', sum(l.qty), l.is_synthetic
FROM m_lot l JOIN m_style s USING (style_nk) WHERE l.lot_etd IS NOT NULL GROUP BY ALL
UNION ALL
SELECT s.customer, s.season, o.factory_code, CAST(date_trunc('week', o.fact_date) AS DATE), 'OUTPUT', sum(o.output_day),
       o.is_synthetic
FROM m_output o JOIN m_style s USING (style_nk) GROUP BY ALL;

-- ---------------------------------------------------------------- S-curve: planned vs actual cumulative output
-- Plan: each style's qty spread evenly over the working days input_plan .. finish_plan of the current plan.
CREATE TABLE mart.mgr_scurve AS
WITH p AS (
  SELECT s.customer, s.season, p.factory_code, p.qty, coalesce(p.input_plan, p.cut_plan) AS d0, p.finish_plan AS d1
  FROM fact.plan p JOIN dim.style s USING (style_key)
  WHERE p.qty > 0 AND p.finish_plan IS NOT NULL AND coalesce(p.input_plan, p.cut_plan) IS NOT NULL
    AND p.finish_plan >= coalesce(p.input_plan, p.cut_plan)),
pd AS (
  SELECT p.customer, p.season, p.factory_code, w.d,
         p.qty / count(*) OVER (PARTITION BY p.customer, p.season, p.factory_code, p.d0, p.d1, p.qty) AS q
  FROM p JOIN core.workday w ON w.d BETWEEN p.d0 AND p.d1 AND NOT w.is_sunday),
daily AS (
  SELECT customer, season, factory_code, d AS day, sum(q) AS planned, 0 AS actual, false AS is_synthetic FROM pd GROUP BY ALL
  UNION ALL
  SELECT s.customer, s.season, o.factory_code, o.fact_date, 0, sum(o.output_day), o.is_synthetic
  FROM m_output o JOIN m_style s USING (style_nk) GROUP BY ALL)
SELECT customer, season, factory_code, day, is_synthetic, round(sum(planned)) AS planned, sum(actual) AS actual
FROM daily GROUP BY ALL;

-- ---------------------------------------------------------------- quality
CREATE TABLE mart.mgr_quality AS             -- factory x month: inspected / passed / defects / rejects (KLMAS orders)
SELECT factory_code, CAST(date_trunc('month', inspect_date) AS DATE) AS month, 'KLMAS' AS source, sum(inspected_qty) AS inspected,
       sum(passed_qty) AS passed, sum(defect_qty) AS defects, 0 AS rejects, count(*) AS inspections, false AS is_synthetic,
       -- the tracker has no season: the customer / season most of its inspected styles belong to
       (SELECT mode(s.customer) FROM fact.inspection i JOIN dim.style s USING (style_key) WHERE i.source = 'KLMAS') AS customer,
       (SELECT mode(s.season) FROM fact.inspection i JOIN dim.style s USING (style_key) WHERE i.source = 'KLMAS') AS season
FROM fact.inspection_day GROUP BY ALL
UNION ALL
SELECT factory_code, CAST(date_trunc('month', fact_date) AS DATE), 'KLMAS', sum(inspected_qty), sum(passed_qty), sum(defect_qty),
       count(*) FILTER (WHERE result = 'REJECT'), count(*), true, customer, season
FROM sim.inspection GROUP BY ALL
UNION ALL                                     -- third-party inspection business (other brands), kept apart by source
SELECT coalesce(factory_code, upper(factory_raw)), CAST(date_trunc('month', fact_date) AS DATE), 'THIRD_PARTY',
       sum(inspected_qty), sum(passed_qty), sum(defect_qty), count(*) FILTER (WHERE result = 'REJECT'), count(*), false,
       NULL, NULL
FROM fact.inspection WHERE source = 'THIRD_PARTY' GROUP BY ALL;

CREATE TABLE mart.mgr_defect_pareto AS
SELECT d.code, any_value(d.code_group) AS code_group, any_value(c.name_ko) AS name_ko, d.source, false AS is_synthetic, sum(d.points) AS points
FROM fact.defect d LEFT JOIN core.defect_code c USING (code) GROUP BY d.code, d.source
UNION ALL
SELECT x.code, any_value(x.code_group), any_value(c.name_ko), 'KLMAS', true, sum(x.points)
FROM sim.defect x LEFT JOIN core.defect_code c USING (code) GROUP BY x.code;

CREATE TABLE mart.mgr_buyer_complaint AS     -- quality complaints from buyers in e-mail (subject words), real only
SELECT e.msg_key, e.sent_at, e.subject, p.party_type, (SELECT string_agg(DISTINCT s.style_no, ', ') FROM bridge.email_style b
       JOIN dim.style s USING (style_key) WHERE b.msg_key = e.msg_key) AS styles,
       (SELECT mode(s.customer) FROM bridge.email_style b JOIN dim.style s USING (style_key) WHERE b.msg_key = e.msg_key) AS customer
FROM fact.email e LEFT JOIN bridge.email_party bp ON bp.msg_key = e.msg_key AND bp.role = 'FROM'
LEFT JOIN dim.party p USING (party_key)
WHERE NOT e.is_sample AND (e.category = 'QUALITY' OR upper(e.subject) LIKE '%QUALITY%' OR e.subject LIKE '%품질%'
                           OR e.subject LIKE '%불량%');

-- ---------------------------------------------------------------- factory scorecard
CREATE TABLE mart.mgr_factory AS
WITH s AS (
  SELECT customer, season, factory_code, count(*) FILTER (WHERE is_active) AS styles, sum(order_qty) FILTER (WHERE is_active) AS qty,
         sum(shipped) AS shipped,
         count(*) FILTER (WHERE on_time IS NOT NULL AND NOT style_syn AND NOT ship_syn) AS lots_real,
         count(*) FILTER (WHERE on_time AND NOT style_syn AND NOT ship_syn) AS on_time_real,
         count(*) FILTER (WHERE on_time IS NOT NULL AND (style_syn OR ship_syn)) AS lots_syn,
         count(*) FILTER (WHERE on_time AND (style_syn OR ship_syn)) AS on_time_syn,
         sum(n_qty_changes + n_factory_changes + n_etd_changes + n_assort_changes) AS changes,
         count(*) FILTER (WHERE risk_reason IS NOT NULL) AS risk_styles
  FROM mart.mgr_style WHERE factory_code IS NOT NULL GROUP BY ALL),
q AS (SELECT customer, season, factory_code, sum(inspected) FILTER (WHERE NOT is_synthetic) AS insp_real,
             sum(defects) FILTER (WHERE NOT is_synthetic) AS def_real,
             sum(inspected) FILTER (WHERE is_synthetic) AS insp_syn, sum(defects) FILTER (WHERE is_synthetic) AS def_syn
      FROM mart.mgr_quality WHERE source = 'KLMAS' GROUP BY ALL),
f AS (SELECT customer, season, factory_code, max(last_report) AS last_report, any_value(freshness) AS freshness
      FROM mart.factory_freshness GROUP BY ALL)
SELECT s.*, q.insp_real, q.def_real, q.insp_syn, q.def_syn, f.last_report, f.freshness
FROM s LEFT JOIN q USING (customer, season, factory_code) LEFT JOIN f USING (customer, season, factory_code);

-- ---------------------------------------------------------------- changes, e-mail, data health
CREATE TABLE mart.mgr_changes AS
SELECT s.customer, s.season, s.factory_code, CAST(date_trunc('month', c.fact_date) AS DATE) AS month,
       CASE WHEN c.change_type IN ('QTY_NOTE', 'VERSION_QTY') THEN 'QTY'
            WHEN c.change_type IN ('FACTORY_MOVE', 'VERSION_FACTORY') THEN 'FACTORY'
            WHEN c.change_type IN ('VERSION_ETD', 'VERSION_RDD') THEN 'ETD'
            WHEN c.change_type LIKE 'EMAIL_%' THEN 'EMAIL_PROPOSAL' ELSE c.change_type END AS change_kind,
       c.review_status, count(*) AS n
FROM fact.change c JOIN dim.style s USING (style_key) WHERE c.change_type <> 'FACTORY_FIXED' GROUP BY ALL
UNION ALL
SELECT s.customer, s.season, s.factory_code, CAST(date_trunc('month', m.event_date) AS DATE), 'ASSORT', m.review_status, count(*)
FROM fact.milestone m JOIN dim.style s USING (style_key) WHERE m.milestone = 'ASSORT_CHANGE' GROUP BY ALL;

CREATE TABLE mart.mgr_email_response AS
SELECT CAST(date_trunc('month', e.sent_at) AS DATE) AS month, coalesce(p.party_type, 'UNKNOWN') AS sender_party,
       count(*) AS replies, round(median(e.reply_hours), 1) AS median_reply_hours,
       count(*) FILTER (WHERE e.reply_hours <= 24) AS within_24h
FROM fact.email e LEFT JOIN bridge.email_party bp ON bp.msg_key = e.msg_key AND bp.role = 'FROM'
LEFT JOIN dim.party p USING (party_key)
WHERE e.reply_hours IS NOT NULL AND NOT e.is_sample GROUP BY ALL;

CREATE TABLE mart.mgr_recon AS               -- differences between files (Ưu tiên 1 findings + reconciliation)
SELECT 'Recap vs Shipment / Production' AS check_name, season, style_no AS ref, mismatch AS detail FROM mart.reconciliation
WHERE mismatch IS NOT NULL
UNION ALL
SELECT 'SHIPPING SCHEDULE vs RECAP', season, style_no, recap_check || ': ' || coalesce(order_qty::VARCHAR, '') || ' vs '
       || coalesce(order_qty_recap::VARCHAR, '') FROM mart.schedule_vs_recap WHERE recap_check IS NOT NULL
UNION ALL
SELECT 'Buyer PDF vs plan', season, file_no, check_result FROM mart.plan_vs_buyer_view WHERE check_result NOT IN ('SAME')
UNION ALL
SELECT 'File total cell', NULL, f.file_name, i.message FROM etl.data_issue i JOIN etl.source_file f USING (file_id)
WHERE i.code IN ('TOTAL_MISMATCH', 'PLAN_BAL_MISMATCH');

-- Season comparison: every measure split into its real part and its synthetic part (whole synthetic seasons, or
-- synthetic shipments / inspections / output filled in for real styles). The page adds the parts it is told to show.
CREATE TABLE mart.mgr_season AS
SELECT customer, season, bool_and(style_syn) AS season_syn,
       count(*) FILTER (WHERE is_active) AS styles, sum(order_qty) FILTER (WHERE is_active) AS order_qty,
       sum(shipped) FILTER (WHERE is_active AND NOT ship_syn AND NOT style_syn) AS shipped_real,
       sum(shipped) FILTER (WHERE is_active AND (ship_syn OR style_syn)) AS shipped_syn,
       count(*) FILTER (WHERE on_time IS NOT NULL AND NOT ship_syn AND NOT style_syn) AS judged_real,
       count(*) FILTER (WHERE on_time AND NOT ship_syn AND NOT style_syn) AS on_time_real,
       count(*) FILTER (WHERE on_time_tol AND NOT ship_syn AND NOT style_syn) AS on_time_tol_real,
       count(*) FILTER (WHERE on_time IS NOT NULL AND (ship_syn OR style_syn)) AS judged_syn,
       count(*) FILTER (WHERE on_time AND (ship_syn OR style_syn)) AS on_time_syn,
       count(*) FILTER (WHERE on_time_tol AND (ship_syn OR style_syn)) AS on_time_tol_syn,
       sum(delay_days) FILTER (WHERE NOT ship_syn AND NOT style_syn) AS delay_days_real,
       sum(delay_days) FILTER (WHERE ship_syn OR style_syn) AS delay_days_syn,
       count(*) FILTER (WHERE risk_reason IS NOT NULL) AS risk_styles,
       sum(inspected) FILTER (WHERE NOT insp_syn AND NOT style_syn) AS inspected_real,
       sum(inspected) FILTER (WHERE insp_syn OR style_syn) AS inspected_syn,
       sum(defects) FILTER (WHERE insp_syn OR style_syn) AS defects_syn,
       sum(pending_proposals) AS pending_proposals
FROM mart.mgr_style GROUP BY customer, season;
