-- core: emails (one row per message after de-duplication), threads, style mentions, change proposals.
-- Proposals are never applied: review_status stays PENDING_REVIEW until a person decides.

CREATE TABLE core.email AS
SELECT * EXCLUDE (rn) FROM (
  SELECT e.* EXCLUDE (body), left(e.body, 4000) AS body,
         count(*) OVER (PARTITION BY e.msg_key) AS n_copies,
         split_part(coalesce(e.categories, 'OTHER'), ',', 1) AS category,
         row_number() OVER (PARTITION BY e.msg_key ORDER BY e.is_quoted, e.file_id, e.part_no) AS rn
  FROM raw.email e JOIN core.current_file f USING (file_id)) WHERE rn = 1;

CREATE TABLE core.email_mention AS
SELECT DISTINCT e.msg_key, d.style_no, d.customer, d.brand, d.season, d.key AS matched_key, d.kind
FROM core.email e JOIN core.style_dictionary d
  ON strpos(upper(coalesce(e.subject, '') || ' ' || coalesce(e.body, '')), d.key) > 0;

CREATE TABLE core.email_thread AS
SELECT thread_key, arg_min(subject, sent_at) AS subject, count(*) AS n_messages,
       min(sent_at) AS first_at, max(sent_at) AS last_at,
       count(DISTINCT coalesce(sender_email, sender)) AS n_senders,
       string_agg(DISTINCT coalesce(sender, sender_email), ', ') AS senders,
       bool_or(is_sample) AS is_sample,
       (SELECT string_agg(DISTINCT m.customer, ', ') FROM core.email_mention m
         WHERE m.msg_key IN (SELECT msg_key FROM core.email e2 WHERE e2.thread_key = e.thread_key)) AS customers
FROM core.email e GROUP BY thread_key;

-- Reply time: gap to the previous message of the thread written by someone else.
CREATE TABLE core.email_reply AS
SELECT msg_key, thread_key, sent_at, coalesce(sender_email, sender) AS who,
       lag(coalesce(sender_email, sender)) OVER w AS prev_who, lag(sent_at) OVER w AS prev_at,
       CASE WHEN lag(coalesce(sender_email, sender)) OVER w IS DISTINCT FROM coalesce(sender_email, sender)
            THEN date_diff('minute', lag(sent_at) OVER w, sent_at) / 60.0 END AS reply_hours
FROM core.email WHERE sent_at IS NOT NULL
WINDOW w AS (PARTITION BY thread_key ORDER BY sent_at);

-- Proposals: code tokens resolved through the dictionary; CHALLENGER-shaped codes kept even when unknown.
CREATE TEMP TABLE proposal_base AS
SELECT DISTINCT ON (c.msg_key, coalesce(d.style_no, c.style_no), c.change_type, c.value_text)
       c.*, coalesce(d.style_no, c.style_no) AS style_resolved, d.customer, d.brand
FROM stg.email_change c JOIN core.current_file f USING (file_id)
LEFT JOIN core.style_dictionary d ON d.key = c.style_no
WHERE c.change_type <> 'MENTION'
  AND (d.style_no IS NOT NULL OR regexp_matches(c.style_no, '^CH[A-Z]{1,2}[0-9][MWU]?[A-Z]{2}[0-9]{4}$'))
  AND c.msg_key IN (SELECT msg_key FROM core.email);

CREATE TABLE core.change_proposal AS
SELECT c.message_id, c.msg_key, e.sent_at, e.subject, e.is_sample, c.style_resolved AS style_no,
       coalesce(o.season, pf.season) AS season, coalesce(o.factory_code, pf.factory_code) AS factory_code,
       coalesce(c.customer, pf.customer, CASE WHEN o.style_no IS NOT NULL THEN 'CHALLENGER' END) AS customer,
       c.change_type, c.value_text, coalesce(o.order_qty, pf.order_qty) AS current_qty,
       CASE WHEN c.change_type = 'QTY_PCT' THEN round(coalesce(o.order_qty, pf.order_qty) * (1 + c.pct / 100.0))::INT
            WHEN c.change_type = 'QTY' THEN c.qty_after END AS proposed_qty,
       coalesce(o.etd_vn, pf.etd) AS current_etd, c.new_date AS proposed_etd, c.color_from, c.color_to,
       (o.style_no IS NOT NULL OR pf.style_no IS NOT NULL) AS style_known, coalesce(o.status, pf.status) AS style_status,
       CASE WHEN c.change_type = 'COLOR' THEN EXISTS (
              SELECT 1 FROM core.order_color oc WHERE oc.style_no = c.style_resolved AND oc.color = c.color_from)
       END AS color_from_exists,
       -- The % change may already be in ORDER RECAP while other files still show the old qty (Q04)
       CASE WHEN c.change_type = 'QTY_PCT' THEN p.order_qty_reported END AS qty_in_other_file,
       (c.change_type = 'QTY_PCT' AND p.order_qty_reported IS NOT NULL
        AND abs(round(p.order_qty_reported * (1 + c.pct / 100.0)) - o.order_qty) <= 1) AS possibly_applied,
       c.confidence, c.evidence, c.review_status
FROM proposal_base c
LEFT JOIN core.email e USING (msg_key)
LEFT JOIN core.style_order o ON o.style_no = c.style_resolved
LEFT JOIN (SELECT * FROM core.order_portfolio WHERE customer <> 'CHALLENGER') pf ON pf.style_no = c.style_resolved
LEFT JOIN core.production_snapshot p ON p.style_no = c.style_resolved;

-- Email vs file: is the requested change already in the current file?
CREATE TABLE core.proposal_file_status AS
SELECT *, CASE
    WHEN NOT style_known THEN 'STYLE_UNKNOWN'
    WHEN change_type LIKE 'QTY%' AND proposed_qty IS NOT NULL AND (proposed_qty = current_qty OR possibly_applied) THEN 'IN_FILE'
    WHEN change_type = 'ETD' AND proposed_etd = current_etd THEN 'IN_FILE'
    WHEN change_type = 'ETD' AND proposed_etd IS NOT NULL AND current_etd IS NOT NULL
         AND CAST(sent_at AS DATE) > proposed_etd THEN 'PAST_DATE'
    ELSE 'NOT_YET' END AS file_status
FROM core.change_proposal;
