-- mart: all-customer portfolio, production plan risk, version history, email analytics.

CREATE OR REPLACE MACRO mart.in_season(d, season) AS (
  CASE WHEN d IS NULL OR season IS NULL THEN NULL
       WHEN season LIKE '%SS' THEN d BETWEEN make_date(1999 + CAST(left(season, 2) AS INT), 7, 1)
                                         AND make_date(2000 + CAST(left(season, 2) AS INT), 9, 30)
       ELSE d BETWEEN make_date(2000 + CAST(left(season, 2) AS INT), 1, 1)
                  AND make_date(2001 + CAST(left(season, 2) AS INT), 3, 31) END);

CREATE TABLE mart.customer_portfolio AS
SELECT p.customer, p.brand, p.season,
       count(*) FILTER (WHERE p.is_active) AS styles_active, count(*) FILTER (WHERE NOT p.is_active) AS styles_cancelled,
       sum(p.order_qty) FILTER (WHERE p.is_active) AS order_qty,
       count(DISTINCT p.factory_code) FILTER (WHERE p.is_active) AS factories,
       min(p.etd) FILTER (WHERE p.is_active AND mart.in_season(p.etd, p.season)) AS etd_first,
       max(p.etd) FILTER (WHERE p.is_active AND mart.in_season(p.etd, p.season)) AS etd_last,
       count(*) FILTER (WHERE p.is_active AND p.etd IS NOT NULL AND NOT mart.in_season(p.etd, p.season)) AS etd_out_of_season,
       any_value(p.etd_rule) AS etd_rule, any_value(f.file_name) AS file_name,
       any_value(coalesce(f.report_date, f.file_date)) AS as_of
FROM core.order_portfolio p JOIN etl.source_file f USING (file_id) GROUP BY ALL;

CREATE TABLE mart.factory_load_all AS
SELECT coalesce(factory_code, '(chưa rõ) ' || coalesce(factory_raw, '-')) AS factory, customer, brand, season,
       count(*) AS styles, sum(order_qty) AS order_qty
FROM core.order_portfolio WHERE is_active GROUP BY ALL;

CREATE TABLE mart.etd_weekly_all AS
SELECT date_trunc('week', etd)::DATE AS week_start, customer, sum(order_qty) AS order_qty, count(*) AS styles
FROM core.order_portfolio
WHERE is_active AND mart.in_season(etd, season) GROUP BY ALL;

CREATE TABLE mart.plan_risk AS
SELECT pl.customer, pl.brand, pl.season, pl.factory_code, pl.style_no, pl.file_no, pl.item, pl.qty, pl.line_worker,
       pl.daily_target, pl.cut_plan, pl.input_plan, pl.finish_plan, pl.exf_plan, pl.due_etd, pl.rdd, pl.bal_days,
       pl.bal_calc, pl.plan_risk, (pl.exf_plan - pl.due_etd) AS exf_vs_due_days, pl.as_of, pl.remark,
       o.order_qty AS order_qty_recap, o.factory_code AS factory_recap, o.is_active AS active_in_recap,
       CASE WHEN o.style_no IS NULL THEN 'NOT_IN_RECAP'
            WHEN NOT o.is_active THEN 'CANCELLED_IN_RECAP'
            WHEN o.order_qty IS DISTINCT FROM pl.qty THEN 'QTY_DIFF'
            WHEN o.factory_code IS DISTINCT FROM pl.factory_code THEN 'FACTORY_DIFF' END AS recap_check,
       pl.file_id, pl.sheet, pl.row_no
FROM core.production_plan pl
LEFT JOIN core.order_portfolio o ON o.season = pl.season
     AND (o.file_no = pl.file_no OR (pl.file_no IS NULL AND o.style_no = pl.style_no));

-- ---------- History: every loaded version of the versioned sources ----------
CREATE TABLE mart.file_version AS
SELECT file_id, file_name, parser, season, coalesce(family, CASE WHEN parser = 'order_recap' THEN 'CHALLENGER|CHALLENGER' END) AS family,
       file_date, report_date, is_current, rows_loaded,
       row_number() OVER (PARTITION BY parser, season, coalesce(family, '') ORDER BY coalesce(file_date, report_date), file_id) AS version_no,
       count(*) OVER (PARTITION BY parser, season, coalesce(family, '')) AS n_versions,
       (report_date < lag(report_date) OVER (PARTITION BY parser, season, coalesce(family, '')
                                             ORDER BY coalesce(file_date, report_date), file_id)) AS report_date_went_back
FROM etl.source_file
WHERE status = 'LOADED' AND parser IN ('order_recap', 'order_recap_ext', 'production_plan', 'production_status', 'shipment_status');

-- Style snapshot per ORDER RECAP version (CHALLENGER detailed model + other customers)
CREATE TEMP TABLE order_snapshot AS
SELECT s.file_id, s.season, s.style_no, NULL AS file_no, s.style_no AS vkey, s.factory_raw, core.factory_code(s.factory_raw) AS factory_code,
       q.qty, s.etd_vn AS etd, s.rdd_kr AS rdd, s.status_label AS status
FROM raw.order_recap_style s
LEFT JOIN (SELECT file_id, style_no, sum(order_qty) FILTER (WHERE is_active) AS qty
           FROM raw.order_recap_color GROUP BY ALL) q USING (file_id, style_no)
UNION ALL
SELECT file_id, season, style_no, file_no, style_no || coalesce('|' || file_no, ''), factory_raw, factory_code,
       CASE WHEN is_active THEN order_qty END,
       etd, rdd, status_label
FROM raw.order_line_ext;

CREATE TABLE mart.version_change AS
WITH v AS (
  SELECT fv.*, lag(file_id) OVER (PARTITION BY parser, season, family ORDER BY version_no) AS prev_file_id,
         lag(file_name) OVER (PARTITION BY parser, season, family ORDER BY version_no) AS prev_file_name
  FROM mart.file_version fv WHERE parser IN ('order_recap', 'order_recap_ext')),
pairs AS (SELECT row_number() OVER () AS pair_id, * FROM v WHERE prev_file_id IS NOT NULL),
n AS (SELECT p.pair_id, s.* FROM pairs p JOIN order_snapshot s ON s.file_id = p.file_id),
o AS (SELECT p.pair_id, s.* FROM pairs p JOIN order_snapshot s ON s.file_id = p.prev_file_id),
j AS (
  SELECT p.family, p.season, p.prev_file_name AS from_file, p.file_name AS to_file,
         coalesce(n.style_no, o.style_no) AS style_no, coalesce(n.file_no, o.file_no) AS file_no, o.factory_raw AS f0, n.factory_raw AS f1, o.qty AS q0, n.qty AS q1,
         o.etd AS e0, n.etd AS e1, o.rdd AS r0, n.rdd AS r1, o.status AS s0, n.status AS s1,
         o.style_no IS NULL AS added, n.style_no IS NULL AS removed
  FROM n FULL JOIN o USING (pair_id, vkey)
  JOIN pairs p ON p.pair_id = coalesce(n.pair_id, o.pair_id)),
x AS (
  SELECT *, 'ADDED' AS kind, NULL AS before_v, NULL AS after_v FROM j WHERE added
  UNION ALL SELECT *, 'REMOVED', NULL, NULL FROM j WHERE removed
  UNION ALL SELECT *, 'FACTORY', f0, f1 FROM j WHERE NOT added AND NOT removed AND f0 IS DISTINCT FROM f1
  UNION ALL SELECT *, 'QTY', q0::VARCHAR, q1::VARCHAR FROM j WHERE NOT added AND NOT removed AND q0 IS DISTINCT FROM q1
  UNION ALL SELECT *, 'ETD', e0::VARCHAR, e1::VARCHAR FROM j WHERE NOT added AND NOT removed AND e0 IS DISTINCT FROM e1
  UNION ALL SELECT *, 'RDD', r0::VARCHAR, r1::VARCHAR FROM j WHERE NOT added AND NOT removed AND r0 IS DISTINCT FROM r1
  UNION ALL SELECT *, 'STATUS', s0, s1 FROM j WHERE NOT added AND NOT removed AND s0 IS DISTINCT FROM s1)
SELECT family, season, from_file, to_file, style_no, file_no, kind, before_v, after_v,
       CASE WHEN kind IN ('ETD', 'RDD') AND after_v IS NOT NULL AND NOT mart.in_season(CAST(after_v AS DATE), season)
            THEN 'ENTRY_ERROR?'
            WHEN kind IN ('ETD', 'RDD') AND before_v IS NOT NULL AND after_v IS NOT NULL
                 AND NOT mart.in_season(CAST(before_v AS DATE), season) THEN 'CORRECTION'
            ELSE 'BUSINESS' END AS change_class
FROM x;

CREATE TABLE mart.version_change_summary AS
SELECT family, season, from_file, to_file, kind, change_class, count(*) AS n
FROM mart.version_change GROUP BY ALL;

-- ---------- Email analytics ----------
CREATE TABLE mart.email_weekly AS
SELECT date_trunc('week', sent_at)::DATE AS week_start, category, count(*) AS n
FROM core.email WHERE sent_at IS NOT NULL GROUP BY ALL;

CREATE TABLE mart.email_list AS
SELECT e.msg_key, e.sent_at, e.sender, e.sender_email, e.subject, e.category, e.categories, e.lang, e.channel,
       e.is_quoted, e.n_copies, e.is_sample, e.thread_key, r.reply_hours,
       (SELECT string_agg(DISTINCT m.style_no, ', ') FROM core.email_mention m WHERE m.msg_key = e.msg_key) AS styles,
       (SELECT string_agg(DISTINCT m.customer, ', ') FROM core.email_mention m WHERE m.msg_key = e.msg_key) AS customers,
       e.summary_vi, left(e.body, 1500) AS body
FROM core.email e LEFT JOIN core.email_reply r USING (msg_key);

CREATE TABLE mart.email_kpi AS
SELECT count(*) AS emails, (SELECT count(*) FROM raw.email) - count(*) AS duplicates_removed,
       count(DISTINCT thread_key) AS threads, count(*) FILTER (WHERE is_sample) AS sample_emails,
       (SELECT count(*) FROM core.change_proposal) AS proposals,
       (SELECT count(*) FROM core.proposal_file_status WHERE file_status = 'NOT_YET') AS proposals_not_in_file,
       (SELECT median(reply_hours) FROM core.email_reply WHERE reply_hours IS NOT NULL) AS median_reply_hours,
       (SELECT count(DISTINCT style_no) FROM core.email_mention) AS styles_mentioned,
       min(sent_at) AS first_at, max(sent_at) AS last_at
FROM core.email;

CREATE TABLE mart.email_style_heat AS
SELECT m.customer, e.category, count(DISTINCT e.msg_key) AS n
FROM core.email e JOIN core.email_mention m USING (msg_key) GROUP BY ALL;
