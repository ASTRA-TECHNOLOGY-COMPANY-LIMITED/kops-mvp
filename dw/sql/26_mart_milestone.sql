-- ---------- Style progress (N-03): timeline per style, material ETD slips per factory ----------
CREATE TABLE mart.style_timeline AS
WITH season AS (SELECT style_no, arg_max(season, file_id) AS season FROM core.order_portfolio GROUP BY style_no)
SELECT m.style_no, coalesce(s.season, any_value(d.season)) AS season, any_value(m.customer) AS customer,
       any_value(m.factory) AS factory,
       min(m.event_date) FILTER (WHERE m.milestone = 'FPP_REQUEST') AS fpp_request,
       min(m.event_date) FILTER (WHERE m.milestone = 'FPP_CMT') AS fpp_cmt,
       min(m.event_date) FILTER (WHERE m.milestone = 'FPP_CFMD') AS fpp_cfmd,
       min(m.event_date) FILTER (WHERE m.milestone = 'FABRIC_INSPECTION') AS fabric_inspection,
       min(m.event_date) FILTER (WHERE m.milestone = 'DM_APPROVAL') AS dm_approval,
       min(m.event_date) FILTER (WHERE m.milestone = 'INLINE_CMT') AS inline_cmt,
       min(m.event_date) FILTER (WHERE m.milestone = 'FINAL_INSPECTION') AS final_inspection,
       min(m.event_date) FILTER (WHERE m.milestone = 'SHIPMENT') AS first_shipment,
       count(*) FILTER (WHERE m.milestone = 'ASSORT_CHANGE') AS assort_changes,
       count(*) AS n_events, max(m.event_date) AS last_event, bool_or(m.is_sample) AS is_sample
FROM core.style_milestone m LEFT JOIN season s USING (style_no)
LEFT JOIN core.style_dictionary d ON d.key = m.style_no
WHERE m.style_known
GROUP BY m.style_no, s.season;

CREATE TABLE mart.style_event AS
SELECT m.style_no, t.season, m.milestone, m.event_date, m.event_at, m.source_kind, m.source_title, m.factory, m.customer,
       m.sender_side, m.via, m.booking, m.is_sample
FROM core.style_milestone m LEFT JOIN mart.style_timeline t USING (style_no);

CREATE TABLE mart.material_delay AS
SELECT factory, customer, count(*) AS shipments, count(*) FILTER (WHERE etd_old IS NOT NULL) AS delayed,
       round(avg(date_diff('day', etd_old, etd_new)) FILTER (WHERE etd_old IS NOT NULL), 1) AS avg_delay_days,
       max(date_diff('day', etd_old, etd_new)) AS max_delay_days, min(etd_new) AS first_etd, max(etd_new) AS last_etd
FROM core.shipment_event WHERE direction = 'inbound_material' GROUP BY ALL;

-- ---------- SHIPPING SCHEDULE vs ORDER RECAP (N-04) ----------
CREATE TABLE mart.schedule_vs_recap AS
SELECT s.season, s.style_no, s.status, s.factory_raw, s.factory_code, o.factory_code AS factory_recap,
       s.order_qty, o.order_qty AS order_qty_recap, s.shipped_qty, s.ship_plan_qty,
       s.etd_vn, o.etd_vn AS etd_recap, s.rdd, o.rdd_kr AS rdd_recap, s.rdd_minus_etd,
       s.fixed_exfact, s.fixed_etd, s.fixed_eta, date_diff('day', s.etd_vn, s.fixed_etd) AS fixed_etd_vs_etd_days,
       s.ship_mode, coalesce(s.remark, s.remark2) AS remark,
       CASE WHEN o.style_no IS NULL THEN 'NOT_IN_RECAP'
            WHEN s.etd_vn IS DISTINCT FROM o.etd_vn THEN 'ETD_DIFF'
            WHEN s.order_qty IS DISTINCT FROM o.order_qty THEN 'QTY_DIFF'
            WHEN s.factory_code IS DISTINCT FROM o.factory_code THEN 'FACTORY_DIFF' END AS recap_check,
       s.file_id, s.sheet, s.row_no
FROM core.shipping_schedule s
LEFT JOIN core.style_order o ON o.season = s.season AND o.style_no = s.style_no;

-- ---------- Buyer's order status PDF vs KLMAS production plan (N-04) ----------
CREATE TABLE mart.plan_vs_buyer_view AS
SELECT b.brand, b.season, b.file_no, b.style_no, b.factory_code, b.qty AS qty_buyer, p.qty AS qty_plan,
       b.cut_plan AS cut_buyer, p.cut_plan AS cut_plan, b.finish_plan AS finish_buyer, p.finish_plan AS finish_plan,
       b.etd AS etd_buyer, p.etd_plan AS etd_plan, b.eta AS eta_buyer, p.eta_plan AS eta_plan, b.rdd AS rdd_buyer,
       p.rdd AS rdd_plan, b.margin_days, p.bal_days AS bal_plan, p.bal_rule, b.status AS status_buyer,
       CASE WHEN p.style_no IS NULL THEN 'NOT_IN_PLAN'
            WHEN b.qty IS DISTINCT FROM p.qty THEN 'QTY_DIFF'
            WHEN b.rdd IS DISTINCT FROM p.rdd THEN 'RDD_DIFF'
            WHEN b.etd IS DISTINCT FROM p.etd_plan OR b.eta IS DISTINCT FROM p.eta_plan THEN 'ETD_ETA_DIFF'
            WHEN b.cut_plan IS DISTINCT FROM p.cut_plan OR b.finish_plan IS DISTINCT FROM p.finish_plan THEN 'PLAN_DATE_DIFF'
            ELSE 'SAME' END AS check_result,
       b.printed_on, p.as_of AS plan_as_of, b.file_id, b.page, b.line_no
FROM core.buyer_order_status b
LEFT JOIN core.production_plan p ON p.season = b.season
     AND (p.file_no = b.file_no OR (p.file_no IS NULL AND p.style_no = b.style_no));
