-- Linked model (D-01): conformed dimensions, facts and bridges over everything loaded, for the manager dashboard.
-- Doc: dw/docs/data_model.md (ERD, grain, keys, alias rules). core / mart tables keep their names and content.
-- Surrogate keys (*_key) are row numbers over the natural key: stable for the same data, rebuilt every build; the
-- natural keys (customer, season, factory_code, customer|season|style_no) are the durable identifiers.
-- Styles are linked only through recorded aliases (no fuzzy match): what cannot be linked goes to etl.link_orphan.
CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS fact;
CREATE SCHEMA IF NOT EXISTS bridge;

CREATE OR REPLACE MACRO dim.nkey(s) AS
  upper(trim(regexp_replace(strip_accents(replace(replace(coalesce(s, ''), 'Đ', 'D'), 'đ', 'd')), '\s+', ' ', 'g')));

-- ================================================================ dimensions
CREATE TABLE dim.customer AS
WITH c AS (
  SELECT customer FROM core.order_portfolio UNION SELECT customer FROM core.production_plan
  UNION SELECT customer FROM stg.customer_ref)
SELECT row_number() OVER (ORDER BY c.customer) AS customer_key, c.customer, coalesce(r.name, c.customer) AS name,
       CASE WHEN r.customer IS NOT NULL THEN 'config' ELSE 'data' END AS source
FROM c LEFT JOIN stg.customer_ref r USING (customer) WHERE c.customer IS NOT NULL AND c.customer <> '?';

CREATE TABLE dim.brand AS
WITH b AS (
  SELECT customer, brand FROM core.order_portfolio UNION SELECT customer, brand FROM core.production_plan
  UNION SELECT 'DHG', brand FROM core.buyer_order_status)
SELECT row_number() OVER (ORDER BY b.customer, b.brand) AS brand_key, b.brand, c.customer_key, b.customer
FROM b JOIN dim.customer c USING (customer) WHERE b.brand IS NOT NULL AND b.brand <> '?';

-- Season = selling window (assumption ASM-SEASON-01 in dw/docs/assumptions.md): SS Feb-Jul, FW Aug-Jan of next year.
CREATE TABLE dim.season AS
WITH s AS (
  SELECT season FROM core.order_portfolio UNION SELECT season FROM core.production_plan
  UNION SELECT season FROM core.production_snapshot UNION SELECT season FROM core.shipment_detail
  UNION SELECT season FROM core.shipping_schedule UNION SELECT season FROM core.buyer_order_status
  UNION SELECT season FROM core.document)
SELECT row_number() OVER (ORDER BY 2000 + CAST(left(season, 2) AS INT), right(season, 2) = 'FW') AS season_key, season,
       2000 + CAST(left(season, 2) AS INT) AS year, right(season, 2) AS half,
       CASE WHEN right(season, 2) = 'SS' THEN make_date(2000 + CAST(left(season, 2) AS INT), 2, 1)
            ELSE make_date(2000 + CAST(left(season, 2) AS INT), 8, 1) END AS start_date,
       CASE WHEN right(season, 2) = 'SS' THEN make_date(2000 + CAST(left(season, 2) AS INT), 7, 31)
            ELSE make_date(2001 + CAST(left(season, 2) AS INT), 1, 31) END AS end_date
FROM s WHERE regexp_full_match(season, '2[0-9](SS|FW)');

CREATE TABLE dim.date AS
SELECT CAST(strftime(d, '%Y%m%d') AS INT) AS date_key, CAST(d AS DATE) AS date, year(d) AS year, month(d) AS month,
       CAST(date_trunc('week', d) AS DATE) AS week_start, isodow(d) AS iso_dow, isodow(d) = 7 AS is_sunday
FROM generate_series(DATE '2024-01-01', DATE '2028-12-31', INTERVAL 1 DAY) AS g(d);

CREATE OR REPLACE MACRO dim.date_key(d) AS CAST(strftime(d, '%Y%m%d') AS INT);

-- Factories: canonical codes of the parsers' alias table + unconfirmed aliases (Q08) + codes seen in the data.
CREATE TABLE dim.factory_alias AS
SELECT alias_key, factory_code, 'CONFIRMED' AS confidence, NULL AS question, 'config.FACTORY_ALIASES' AS source
FROM stg.factory_alias
UNION ALL
SELECT alias_key, factory_code, confidence, question, 'config.FACTORY_ALIAS_REVIEW'
FROM stg.factory_alias_review WHERE alias_key NOT IN (SELECT alias_key FROM stg.factory_alias);

CREATE TABLE dim.factory AS
WITH f AS (
  SELECT factory_code FROM dim.factory_alias
  UNION SELECT factory_code FROM core.order_portfolio UNION SELECT factory_code FROM core.production_plan
  UNION SELECT factory_code FROM core.production_snapshot UNION SELECT factory_code FROM core.shipment_detail
  UNION SELECT factory_code FROM core.shipping_schedule)
SELECT row_number() OVER (ORDER BY factory_code) AS factory_key, factory_code,
       coalesce((SELECT min(confidence) FROM dim.factory_alias a WHERE a.factory_code = f.factory_code
                 AND a.alias_key = f.factory_code), 'CONFIRMED') AS confidence
FROM f WHERE factory_code IS NOT NULL;

-- Styles: master = every ORDER RECAP version (a style stays a style after it is dropped / cancelled).
CREATE TEMP TABLE style_master AS
SELECT 'CHALLENGER' AS customer, 'CHALLENGER' AS brand, s.season, s.style_no, NULL::VARCHAR AS file_no, NULL AS aliases,
       s.file_id, f.file_date, f.is_current
FROM raw.order_recap_style s JOIN etl.source_file f USING (file_id)
UNION ALL
SELECT coalesce(o.customer, '?'), o.brand, o.season, o.style_no, o.file_no, o.style_aliases, o.file_id, f.file_date, f.is_current
FROM raw.order_line_ext o JOIN etl.source_file f USING (file_id)
WHERE o.style_no IS NOT NULL AND o.season IS NOT NULL;

CREATE TABLE dim.style AS
WITH last AS (   -- newest RECAP row per style (current version first)
  SELECT * FROM style_master
  QUALIFY row_number() OVER (PARTITION BY customer, season, style_no ORDER BY is_current DESC, file_date DESC NULLS LAST, file_id DESC) = 1)
SELECT row_number() OVER (ORDER BY l.customer, l.season, l.style_no) AS style_key,
       l.customer || '|' || l.season || '|' || l.style_no AS style_nk, l.customer, l.brand, l.season, l.style_no,
       c.customer_key, b.brand_key, s.season_key,
       po.factory_code, po.factory_raw,
       po.order_qty, po.etd, po.rdd, po.status, coalesce(po.is_active, false) AS is_active,
       po.style_no IS NOT NULL AS in_current_recap, l.file_id AS source_file_id
FROM last l
LEFT JOIN dim.customer c ON c.customer = l.customer
LEFT JOIN dim.brand b ON b.customer = l.customer AND b.brand = l.brand
LEFT JOIN dim.season s ON s.season = l.season
LEFT JOIN (SELECT * FROM core.order_portfolio
           QUALIFY row_number() OVER (PARTITION BY customer, season, style_no ORDER BY is_active DESC, order_qty DESC NULLS LAST) = 1) po
  ON po.customer = l.customer AND po.season = l.season AND po.style_no = l.style_no;

-- Every code that names a style -> style_key. kind: STYLE, FILE_NO, FILE_NO_HEAD, ALIAS (RECAP '(=..)'), TYPO (config,
-- unconfirmed Q05), PLAN_FILE_NO / BUYER_PDF (plan / DHG PDF rows whose style code is in the master).
CREATE TEMP TABLE alias_raw AS
SELECT style_no AS code, season, customer, style_no, 'STYLE' AS kind, 'ORDER RECAP' AS source, 'HIGH' AS confidence FROM style_master
UNION SELECT file_no, season, customer, style_no, 'FILE_NO', 'ORDER RECAP', 'HIGH' FROM style_master WHERE file_no IS NOT NULL
UNION SELECT regexp_extract(file_no, '^([A-Z]+-\d+)', 1), season, customer, style_no, 'FILE_NO_HEAD', 'ORDER RECAP', 'MEDIUM'
      FROM style_master WHERE regexp_matches(file_no, '^[A-Z]+-\d+-')
UNION SELECT trim(a.code), m.season, m.customer, m.style_no, 'ALIAS', 'ORDER RECAP', 'HIGH'
      FROM style_master m, unnest(string_split(m.aliases, ',')) AS a(code) WHERE m.aliases IS NOT NULL
UNION SELECT t.alias_style, m.season, m.customer, m.style_no, 'TYPO', 'config.STYLE_ALIASES (Q05)', 'MEDIUM'
      FROM stg.style_alias t JOIN style_master m ON m.style_no = t.style_no
UNION SELECT p.file_no, p.season, m.customer, m.style_no, 'PLAN_FILE_NO', 'PRODUCTION PLAN', 'HIGH'
      FROM core.production_plan p JOIN style_master m ON m.season = p.season AND m.style_no = p.style_no
      WHERE p.file_no IS NOT NULL
UNION SELECT b.file_no, b.season, m.customer, m.style_no, 'BUYER_PDF', 'buyer order status PDF', 'HIGH'
      FROM core.buyer_order_status b JOIN style_master m ON m.season = b.season AND m.style_no = b.style_no;

CREATE TABLE dim.style_alias AS
WITH a AS (
  SELECT DISTINCT upper(trim(r.code)) AS alias_code, r.season, s.style_key, r.kind, r.source, r.confidence
  FROM alias_raw r JOIN dim.style s ON s.customer = r.customer AND s.season = r.season AND s.style_no = r.style_no
  WHERE r.code IS NOT NULL AND length(trim(r.code)) >= 4)
SELECT *, count(DISTINCT style_key) OVER (PARTITION BY alias_code, season) > 1 AS ambiguous FROM a;

-- code (+ season if known) -> one style_key; codes naming two styles stay unlinked (AMBIGUOUS)
CREATE TEMP TABLE style_lookup AS
SELECT alias_code, season, any_value(style_key) AS style_key, count(DISTINCT style_key) AS n
FROM dim.style_alias GROUP BY alias_code, season;
CREATE TEMP TABLE style_lookup_any AS          -- when the fact has no season
SELECT alias_code, any_value(style_key) AS style_key, count(DISTINCT style_key) AS n FROM dim.style_alias GROUP BY alias_code;

-- Parties of e-mail (address grain): KLMAS domains, local party file, free mail = INDIVIDUAL, else EXTERNAL.
CREATE TABLE dim.party AS
WITH a AS (
  SELECT DISTINCT lower(x) AS address
  FROM core.email, unnest(regexp_extract_all(coalesce(sender_email, '') || ' ' || coalesce(recipients, '') || ' ' || coalesce(cc, ''),
                                             '[\w.+-]+@[\w-]+(?:\.[\w-]+)+')) AS u(x))
SELECT row_number() OVER (ORDER BY a.address) AS party_key, a.address, split_part(a.address, '@', 2) AS domain,
       coalesce(p.party_type, CASE WHEN split_part(a.address, '@', 2) IN (SELECT domain FROM stg.free_mail) THEN 'INDIVIDUAL'
                                   ELSE 'EXTERNAL' END) AS party_type,
       p.ref_code, CASE WHEN p.domain IS NOT NULL THEN 'domain rule' ELSE 'default' END AS source
FROM a LEFT JOIN stg.party_domain p ON p.domain = split_part(a.address, '@', 2);

-- ================================================================ facts (is_synthetic = false: real files only)
-- Every fact first gets the conformed columns customer, season, style_code, factory_code, factory_raw, fact_date; the
-- keys are then added in one pass (fact_keys below) by joins on the alias / lookup tables.
CREATE TEMP TABLE f_order_line AS        -- grain: style x colour (CHALLENGER) or style x order line (others); current RECAP
SELECT 'CHALLENGER' AS customer, o.season, o.style_no AS style_code, o.factory_code, o.factory_raw, o.etd_vn AS fact_date,
       oc.color, NULL::VARCHAR AS file_no, oc.order_qty, oc.is_active, o.etd_vn AS etd, o.rdd_kr AS rdd,
       oc.file_id AS source_file_id, 'ORDER RECAP!R' || oc.row_no AS source_ref
FROM core.order_color oc JOIN core.style_order o USING (season, style_no)
UNION ALL
SELECT customer, season, style_no, factory_code, factory_raw, etd, NULL, file_no, order_qty, is_active, etd, rdd, file_id,
       sheet || '!R' || row_no
FROM core.order_line_ext;

CREATE TEMP TABLE f_plan AS              -- grain: style x factory x plan version (current plan files)
SELECT customer, season, style_no AS style_code, factory_code, factory_raw, exf_plan AS fact_date, file_no, qty, daily_target,
       cut_plan, input_plan, finish_plan, exf_plan, etd_plan, eta_plan, due_etd, rdd, bal_days, bal_calc, bal_rule, plan_risk,
       as_of, file_id AS source_file_id, sheet || '!R' || row_no AS source_ref
FROM core.production_plan;

CREATE TEMP TABLE f_production_status AS -- grain: style x status snapshot (current PRODUCTION AND SHIPPING STATUS)
SELECT 'CHALLENGER' AS customer, season, style_no AS style_code, factory_code, factory_raw, as_of AS fact_date,
       order_qty_reported, daily_output, output_qty, inspected_qty, shipped_qty_reported, cutting_plan, input_plan,
       sewing_finish_plan, exfact_est, etd_vn, rdd, file_id AS source_file_id, 'R' || row_no AS source_ref
FROM core.production_snapshot;

CREATE TEMP TABLE f_shipment_line AS     -- grain: lot (label) x style x colour x size, SHIPMENT and SAMPLE sections
SELECT 'CHALLENGER' AS customer, season, style_no AS style_code, factory_code, NULL::VARCHAR AS factory_raw, lot_etd AS fact_date,
       section, label AS lot_label, color, size_code, qty, lot_etd, lot_eta, ship_mode, sample_type,
       file_id AS source_file_id, sheet || '!R' || row_no || 'C' || col_no AS source_ref
FROM core.shipment_detail WHERE section IN ('SHIPMENT', 'SAMPLE');

CREATE TEMP TABLE f_shipment_lot AS      -- grain: lot x style
SELECT customer, season, style_code, factory_code, NULL::VARCHAR AS factory_raw, any_value(lot_etd) AS fact_date, lot_label,
       any_value(lot_etd) AS lot_etd, any_value(lot_eta) AS lot_eta, any_value(ship_mode) AS ship_mode, sum(qty) AS qty,
       any_value(source_file_id) AS source_file_id
FROM f_shipment_line WHERE section = 'SHIPMENT' GROUP BY customer, season, style_code, factory_code, lot_label;

CREATE TEMP TABLE f_milestone AS         -- grain: style x milestone x source (e-mail message or document)
SELECT customer, NULL::VARCHAR AS season, style_no AS style_code, NULL::VARCHAR AS factory_code, factory AS factory_raw, event_date AS fact_date,
       milestone, event_date, event_at, source_kind, source_ref, source_title, sender_side, booking, is_sample,
       'rule' AS extractor, CASE WHEN source_kind = 'email' THEN 'PENDING_REVIEW' ELSE 'IN_FILE' END AS review_status
FROM core.style_milestone WHERE style_known;

CREATE TEMP TABLE f_change AS            -- grain: one change of one style (qty note, factory move, version diff, e-mail proposal)
SELECT 'CHALLENGER' AS customer, q.season, q.style_no AS style_code, NULL::VARCHAR AS factory_code, NULL::VARCHAR AS factory_raw,
       q.change_date AS fact_date, 'QTY_NOTE' AS change_type, q.qty_before::VARCHAR AS before_v, q.qty_after::VARCHAR AS after_v,
       q.note_raw AS detail, 'ORDER RECAP note' AS source, q.file_id AS source_file_id, q.location AS source_ref,
       'IN_FILE' AS review_status
FROM core.qty_change q
UNION ALL
SELECT 'CHALLENGER', e.season, e.style_no, e.factory_code, e.factory_hint, e.event_date, 'FACTORY_MOVE', NULL::VARCHAR,
       coalesce(e.factory_code, e.factory_hint), e.note_raw, 'ORDER RECAP note', e.file_id, e.location, 'IN_FILE'
FROM core.factory_event e
UNION ALL
SELECT split_part(v.family, '|', 1), v.season, v.style_no, NULL, NULL, NULL, 'VERSION_' || v.kind, v.before_v, v.after_v,
       v.change_class, v.from_file || ' -> ' || v.to_file, NULL, v.to_file, 'IN_FILE'
FROM mart.version_change v WHERE v.kind NOT IN ('ADDED', 'REMOVED')
UNION ALL
SELECT p.customer, p.season, p.style_no, p.factory_code, NULL, CAST(p.sent_at AS DATE), 'EMAIL_' || p.change_type, NULL,
       p.value_text, p.evidence, 'e-mail', NULL, p.msg_key, p.review_status
FROM core.change_proposal p WHERE NOT p.is_sample;

CREATE TEMP TABLE f_document AS          -- grain: one technical document (name only, never opened)
SELECT customer, season, style_no AS style_code, NULL::VARCHAR AS factory_code, factory AS factory_raw, doc_date AS fact_date,
       file_id AS source_file_id, file_name, ext, size_bytes, stage, doc_kind, doc_date, meta_source, style_known
FROM core.document;

CREATE TEMP TABLE f_daily_output AS      -- grain: style x factory x report day (daily production report, D-02)
SELECT customer, season, style_no AS style_code, factory_code, NULL::VARCHAR AS factory_raw, report_date AS fact_date,
       brand, output_day, output_ttl, input_day, cut_day, NULL::INTEGER AS source_file_id
FROM core.daily_output_series;

CREATE TEMP TABLE f_inspection AS        -- grain: one inspection result. KLMAS tracker: style x piece x colour x day
SELECT 'CHALLENGER' AS customer, NULL::VARCHAR AS season, style_no AS style_code, factory_code, NULL::VARCHAR AS factory_raw,
       inspect_date AS fact_date, 'KLMAS' AS source, piece, color, NULL::VARCHAR AS brand, passed_qty,
       NULL::INTEGER AS inspected_qty, NULL::INTEGER AS defect_qty, NULL::VARCHAR AS result, NULL::INTEGER AS inspection_no,
       NULL::INTEGER AS source_file_id
FROM core.inspection_passed
UNION ALL                                -- third-party: one row per inspection (brands outside KLMAS's orders)
SELECT NULL, NULL, style_no, factory_code, factory_raw, inspect_date, 'THIRD_PARTY', NULL, po_color, brand, pass_qty,
       inspected_qty, defect_qty, result, inspection_no, file_id
FROM core.qc_inspection;

-- factory text -> factory_key: canonical code, confirmed or review alias; 'A>>B' moves count as B
CREATE TEMP TABLE factory_lookup AS
SELECT factory_code AS txt, factory_key FROM dim.factory
UNION SELECT a.alias_key, f.factory_key FROM dim.factory_alias a JOIN dim.factory f USING (factory_code);

CREATE OR REPLACE MACRO dim.fac_txt(code, raw_txt) AS coalesce(CAST(code AS VARCHAR),
  dim.nkey(regexp_replace(list_last(string_split(regexp_replace(coalesce(CAST(raw_txt AS VARCHAR), ''), '>+', '>', 'g'), '>')), '\(\d{6}\)', '', 'g')));

ALTER TABLE dim.style ADD COLUMN factory_key BIGINT;
UPDATE dim.style SET factory_key = fl.factory_key FROM factory_lookup fl WHERE fl.txt = dim.fac_txt(dim.style.factory_code, dim.style.factory_raw);

CREATE OR REPLACE MACRO fact.with_keys(t) AS TABLE
SELECT f.*, coalesce(l1.style_key, l2.style_key) AS style_key,
       CASE WHEN coalesce(l1.style_key, l2.style_key) IS NOT NULL THEN NULL
            WHEN f.style_code IS NULL THEN 'NO_STYLE_CODE'
            WHEN a1.n > 1 OR a2.n > 1 THEN 'AMBIGUOUS_CODE'
            WHEN NOT EXISTS (SELECT 1 FROM dim.style s WHERE s.customer = f.customer AND s.season = f.season)
                 AND f.season IS NOT NULL THEN 'NO_ORDER_RECAP_FOR_SEASON'
            ELSE 'NOT_IN_ORDER_RECAP' END AS link_issue,
       coalesce(s.customer_key, c.customer_key) AS customer_key, coalesce(s.season_key, sn.season_key) AS season_key,
       fl.factory_key, dim.date_key(f.fact_date) AS date_key, false AS is_synthetic
FROM query_table(t) f
LEFT JOIN style_lookup l1 ON f.season IS NOT NULL AND l1.alias_code = upper(trim(CAST(f.style_code AS VARCHAR))) AND l1.season = f.season AND l1.n = 1
LEFT JOIN style_lookup a1 ON f.season IS NOT NULL AND a1.alias_code = upper(trim(CAST(f.style_code AS VARCHAR))) AND a1.season = f.season
LEFT JOIN style_lookup_any l2 ON f.season IS NULL AND l2.alias_code = upper(trim(CAST(f.style_code AS VARCHAR))) AND l2.n = 1
LEFT JOIN style_lookup_any a2 ON f.season IS NULL AND a2.alias_code = upper(trim(CAST(f.style_code AS VARCHAR)))
LEFT JOIN dim.style s ON s.style_key = coalesce(l1.style_key, l2.style_key)
LEFT JOIN dim.customer c ON c.customer = f.customer
LEFT JOIN dim.season sn ON sn.season = f.season
LEFT JOIN factory_lookup fl ON fl.txt = dim.fac_txt(f.factory_code, f.factory_raw);

CREATE TABLE fact.order_line AS FROM fact.with_keys('f_order_line');
CREATE TABLE fact.plan AS FROM fact.with_keys('f_plan');
CREATE TABLE fact.production_status AS FROM fact.with_keys('f_production_status');
CREATE TABLE fact.shipment_line AS FROM fact.with_keys('f_shipment_line');
CREATE TABLE fact.shipment_lot AS FROM fact.with_keys('f_shipment_lot');
CREATE TABLE fact.milestone AS FROM fact.with_keys('f_milestone');
CREATE TABLE fact.change AS FROM fact.with_keys('f_change');
CREATE TABLE fact.document AS FROM fact.with_keys('f_document');
CREATE TABLE fact.daily_output AS FROM fact.with_keys('f_daily_output');
CREATE TABLE fact.inspection AS FROM fact.with_keys('f_inspection');

CREATE TABLE fact.inspection_day AS      -- grain: factory x day (KLMAS tracker rows A / C / D / F; no names)
SELECT d.*, fl.factory_key, dim.date_key(d.inspect_date) AS date_key, 'KLMAS' AS source, false AS is_synthetic
FROM core.inspection_day d LEFT JOIN factory_lookup fl ON fl.txt = d.factory_code;

CREATE TABLE fact.defect AS              -- grain: third-party inspection x defect code (minor / major points)
SELECT d.inspection_no, d.code, d.code_group, d.minor, d.major, d.minor + d.major AS points, i.factory_key, i.date_key,
       i.brand, 'THIRD_PARTY' AS source, false AS is_synthetic
FROM core.qc_defect d JOIN fact.inspection i ON i.source = 'THIRD_PARTY' AND i.inspection_no = d.inspection_no;

CREATE TABLE fact.shipment_event AS      -- grain: shipment (booking, or factory + ETD) from e-mail subjects; no style
SELECT e.event_id, e.direction, e.booking, e.forwarder, e.factory AS factory_raw, e.customer, e.origin, e.etd_old, e.etd_new,
       e.eta, e.ship_mode, e.load_type, e.is_delay, e.first_sent_at, e.n_messages, e.subject, e.source_ref, e.is_sample,
       'rule' AS extractor, 'PENDING_REVIEW' AS review_status, c.customer_key, fl.factory_key,
       dim.date_key(e.etd_new) AS date_key, false AS is_synthetic
FROM core.shipment_event e LEFT JOIN dim.customer c ON c.customer = e.customer
LEFT JOIN factory_lookup fl ON fl.txt = e.factory;

CREATE TABLE fact.email AS               -- grain: one message after de-duplication (msg_key)
SELECT e.msg_key, e.thread_key, e.sent_at, dim.date_key(CAST(e.sent_at AS DATE)) AS date_key, e.sender_email, e.subject,
       e.category, e.lang, e.channel, e.is_quoted, e.is_sample, r.reply_hours, e.file_id AS source_file_id, false AS is_synthetic
FROM core.email e LEFT JOIN core.email_reply r USING (msg_key);

-- ================================================================ bridges
CREATE TABLE bridge.email_style AS        -- e-mail <-> style (style codes found in subject + body, N-07)
SELECT DISTINCT m.msg_key, l.style_key, m.matched_key, m.kind
FROM core.email_mention m JOIN style_lookup l ON l.alias_code = m.style_no AND l.season = m.season AND l.n = 1;

CREATE TABLE bridge.email_party AS
SELECT DISTINCT e.msg_key, p.party_key, r.role
FROM core.email e,
     LATERAL (SELECT 'FROM' AS role, e.sender_email AS txt UNION ALL SELECT 'TO', e.recipients UNION ALL SELECT 'CC', e.cc) r,
     unnest(regexp_extract_all(coalesce(r.txt, ''), '[\w.+-]+@[\w-]+(?:\.[\w-]+)+')) AS u(x)
JOIN dim.party p ON p.address = lower(u.x);

-- Factory of a style over time (SCD2): factory notes of ORDER RECAP ('260512 MOVED FACT(HH)') then the current factory.
CREATE TABLE bridge.style_factory AS
WITH ev AS (
  SELECT e.season, e.style_no, e.event_date, coalesce(e.factory_code, e.factory_hint) AS factory_txt, e.factory_code, 'note' AS src
  FROM core.factory_event e WHERE e.event_date IS NOT NULL
  UNION ALL
  SELECT s.season, s.style_no, NULL, s.factory_raw, s.factory_code, 'current RECAP' FROM core.style_order s),
k AS (
  SELECT l.style_key, ev.event_date, ev.factory_txt, fl.factory_key, ev.src
  FROM ev JOIN style_lookup l ON l.alias_code = ev.style_no AND l.season = ev.season AND l.n = 1
  LEFT JOIN factory_lookup fl ON fl.txt = dim.fac_txt(ev.factory_code, ev.factory_txt)),
o AS (
  SELECT *, row_number() OVER (PARTITION BY style_key ORDER BY event_date NULLS LAST, src DESC) AS seq FROM k WHERE style_key IS NOT NULL)
SELECT style_key, factory_key, factory_txt, src, event_date AS valid_from,
       lead(event_date) OVER (PARTITION BY style_key ORDER BY seq) AS valid_to,
       seq = max(seq) OVER (PARTITION BY style_key) AS is_current
FROM o;

-- ================================================================ link check (D-01)
-- Every fact row that names a style but cannot be linked, with the reason. Rows of a customer x season for which no
-- ORDER RECAP was received are listed (NO_ORDER_RECAP_FOR_SEASON) but are not counted against the link rate.
CREATE TABLE etl.link_orphan AS
WITH o AS (
  SELECT 'order_line' AS fact, customer, season, style_code, link_issue, source_file_id, source_ref FROM fact.order_line
  UNION ALL SELECT 'plan', customer, season, style_code, link_issue, source_file_id, source_ref FROM fact.plan
  UNION ALL SELECT 'production_status', customer, season, style_code, link_issue, source_file_id, source_ref FROM fact.production_status
  UNION ALL SELECT 'shipment_line', customer, season, style_code, link_issue, source_file_id, source_ref FROM fact.shipment_line
  UNION ALL SELECT 'milestone', customer, season, style_code, link_issue, NULL, source_ref FROM fact.milestone
  UNION ALL SELECT 'change', customer, season, style_code, link_issue, source_file_id, source_ref FROM fact.change
  UNION ALL SELECT 'document', customer, season, style_code, link_issue, source_file_id, file_name FROM fact.document
  UNION ALL SELECT 'daily_output', customer, season, style_code, link_issue, NULL, NULL FROM fact.daily_output
  UNION ALL SELECT 'inspection', customer, season, style_code, link_issue, NULL, NULL FROM fact.inspection WHERE source = 'KLMAS')
SELECT o.fact, o.customer, o.season, o.style_code, o.link_issue AS reason, f.file_name AS source_file, o.source_ref
FROM o LEFT JOIN etl.source_file f ON f.file_id = o.source_file_id
WHERE o.link_issue IS NOT NULL AND o.link_issue <> 'NO_STYLE_CODE';

CREATE TABLE mart.link_rate AS
WITH a AS (
  SELECT 'order_line' AS fact, customer, season, style_key, link_issue FROM fact.order_line
  UNION ALL SELECT 'plan', customer, season, style_key, link_issue FROM fact.plan
  UNION ALL SELECT 'production_status', customer, season, style_key, link_issue FROM fact.production_status
  UNION ALL SELECT 'shipment_line', customer, season, style_key, link_issue FROM fact.shipment_line
  UNION ALL SELECT 'milestone', customer, season, style_key, link_issue FROM fact.milestone
  UNION ALL SELECT 'change', customer, season, style_key, link_issue FROM fact.change
  UNION ALL SELECT 'document', customer, season, style_key, link_issue FROM fact.document
  UNION ALL SELECT 'daily_output', customer, season, style_key, link_issue FROM fact.daily_output
  UNION ALL SELECT 'inspection', customer, season, style_key, link_issue FROM fact.inspection WHERE source = 'KLMAS')
SELECT coalesce(customer, '?') AS customer, coalesce(season, '?') AS season, count(*) AS rows_with_style,
       count(style_key) AS linked, count(*) FILTER (WHERE link_issue = 'NO_ORDER_RECAP_FOR_SEASON') AS no_master,
       round(100.0 * count(style_key) / nullif(count(*) - count(*) FILTER (WHERE link_issue = 'NO_ORDER_RECAP_FOR_SEASON'), 0), 1)
         AS link_pct
FROM a WHERE link_issue IS DISTINCT FROM 'NO_STYLE_CODE' GROUP BY ALL;
