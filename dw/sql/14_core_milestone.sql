-- Style milestones and shipment events (N-03). Rule-based hints from email subjects and document names: every row
-- keeps its source (msg_key / file name) so a person can check it. Subjects are free-form (KLMAS 23/10): a mail the
-- rules cannot read simply has no milestone.

-- One row per message (same message saved in several threads counted once, like core.email).
CREATE TEMP TABLE email_event AS
SELECT DISTINCT ON (v.msg_key) v.* EXCLUDE (file_id, sent_at), e.sent_at, e.subject, e.thread_key, e.is_sample,
       CASE WHEN list_contains(string_split(coalesce((SELECT rule_value FROM stg.rule WHERE rule_key = 'klmas_domains'), ''), ','),
                               split_part(e.sender_email, '@', 2)) THEN 'KLMAS' ELSE 'EXTERNAL' END AS sender_side
FROM stg.email_event v JOIN core.email e USING (msg_key)
ORDER BY v.msg_key, v.file_id;

-- Styles of each event: codes in the subject / attachment names found in the style dictionary; otherwise the
-- styles mentioned in the body; otherwise the subject codes as written (style_known = false).
CREATE TEMP TABLE event_style AS
WITH cand AS (
  SELECT v.msg_key, trim(c.code) AS code FROM email_event v, unnest(string_split(v.style_candidates, ',')) AS c(code)
  WHERE v.style_candidates IS NOT NULL),
named AS (
  SELECT DISTINCT c.msg_key, d.style_no, d.customer, 'subject' AS via, true AS style_known
  FROM cand c JOIN core.style_dictionary d ON d.key = c.code),
body AS (
  SELECT DISTINCT m.msg_key, m.style_no, m.customer, 'body' AS via, true AS style_known
  FROM core.email_mention m JOIN email_event v USING (msg_key)
  WHERE m.msg_key NOT IN (SELECT msg_key FROM named))
SELECT * FROM named UNION ALL SELECT * FROM body
UNION ALL
SELECT DISTINCT c.msg_key, c.code, NULL, 'subject', false FROM cand c
WHERE c.msg_key NOT IN (SELECT msg_key FROM named) AND c.msg_key NOT IN (SELECT msg_key FROM body);

-- Shipments: messages of one shipment share a booking; announcements written before the booking was known join it
-- through (direction, factory, ETD). ETD moved by a later message -> etd_old / etd_new.
CREATE TEMP TABLE ship_msg AS
WITH s AS (
  SELECT *, coalesce(booking, max(booking) OVER (PARTITION BY direction, factory, etd_new)) AS bk
  FROM email_event WHERE milestone = 'SHIPMENT')
SELECT *, coalesce(bk, direction || '|' || coalesce(factory, '?') || '|' || etd_new) AS event_key FROM s;

CREATE TABLE core.shipment_event AS
WITH cust AS (       -- customer of the styles named in the shipment mails, when the subject has none (port -> factory)
  SELECT m.event_key, mode(s.customer) AS customer
  FROM ship_msg m JOIN event_style s USING (msg_key) WHERE s.customer IS NOT NULL GROUP BY m.event_key)
SELECT substr(md5(m.event_key), 1, 12) AS event_id, any_value(m.direction) AS direction, max(m.bk) AS booking,
       max(m.forwarder) AS forwarder, any_value(m.factory) AS factory,
       coalesce(max(m.customer), any_value(c.customer)) AS customer, max(m.origin) AS origin,
       arg_max(m.etd_new, m.sent_at) AS etd_new,
       CASE WHEN min(coalesce(m.etd_old, m.etd_new)) <> arg_max(m.etd_new, m.sent_at)
            THEN min(coalesce(m.etd_old, m.etd_new)) END AS etd_old,
       max(m.eta) AS eta, max(m.ship_mode) AS ship_mode, max(m.load_type) AS load_type, bool_or(m.is_delay) AS is_delay,
       min(m.sent_at) AS first_sent_at, max(m.sent_at) AS last_sent_at, count(*) AS n_messages,
       arg_min(m.subject, m.sent_at) AS subject, arg_min(m.msg_key, m.sent_at) AS source_ref, bool_or(m.is_sample) AS is_sample
FROM ship_msg m LEFT JOIN cust c USING (event_key)
GROUP BY m.event_key;

CREATE TABLE core.style_milestone AS
WITH fac AS (SELECT style_no, arg_max(factory_code, file_id) AS factory_code FROM core.order_portfolio GROUP BY style_no),
email_ms AS (
  SELECT s.style_no, s.style_known, v.milestone, CAST(v.sent_at AS DATE) AS event_date, v.sent_at AS event_at,
         'email' AS source_kind, v.msg_key AS source_ref, v.subject AS source_title,
         coalesce(v.factory, f.factory_code) AS factory, coalesce(s.customer, v.customer) AS customer,
         v.sender_side, s.via, NULL::VARCHAR AS booking, v.is_sample
  FROM email_event v JOIN event_style s USING (msg_key) LEFT JOIN fac f USING (style_no)
  WHERE v.milestone <> 'SHIPMENT'),
-- Finished-goods shipments: styles named in the mails, or styles whose Shipment Status lot left the same factory
-- within 3 days of the shipment ETD (the shipping mails rarely list styles).
ship_style AS (
  SELECT DISTINCT m.event_key, s.style_no, s.style_known, s.customer, s.via
  FROM ship_msg m JOIN event_style s USING (msg_key) WHERE m.direction = 'outbound'
  UNION
  SELECT DISTINCT m.event_key, d.style_no, true, NULL, 'shipment_status_lot'
  FROM (SELECT DISTINCT event_key, factory, etd_new FROM ship_msg WHERE direction = 'outbound') m
  JOIN core.shipment_detail d ON d.section = 'SHIPMENT' AND d.factory_code = m.factory
   AND abs(date_diff('day', d.lot_etd, m.etd_new)) <= 3),
ship_ms AS (
  SELECT st.style_no, bool_or(st.style_known) AS style_known, 'SHIPMENT' AS milestone,
         CAST(any_value(e.first_sent_at) AS DATE) AS event_date, any_value(e.first_sent_at) AS event_at,
         'email' AS source_kind, any_value(e.source_ref) AS source_ref, any_value(e.subject) AS source_title,
         any_value(e.factory) AS factory, coalesce(any_value(e.customer), any_value(st.customer)) AS customer,
         NULL AS sender_side, string_agg(DISTINCT st.via, ',') AS via, any_value(e.booking) AS booking,
         any_value(e.is_sample) AS is_sample
  FROM ship_style st JOIN core.shipment_event e ON e.event_id = substr(md5(st.event_key), 1, 12)
  GROUP BY st.style_no, e.event_id),
file_ms AS (
  SELECT d.style_no, d.style_known, d.stage AS milestone, d.doc_date AS event_date, NULL::TIMESTAMP AS event_at,
         'file' AS source_kind, d.file_name AS source_ref, d.file_name AS source_title, d.factory, d.customer,
         NULL AS sender_side, d.meta_source AS via, NULL AS booking, d.is_sample
  FROM core.document d
  WHERE d.stage IS NOT NULL AND d.doc_date IS NOT NULL AND d.style_no IS NOT NULL
    AND d.doc_kind NOT IN ('CAD_PATTERN', 'ARCHIVE', 'IMAGE', 'LINK', 'OTHER'))
SELECT * FROM email_ms UNION ALL BY NAME SELECT * FROM ship_ms UNION ALL BY NAME SELECT * FROM file_ms;
