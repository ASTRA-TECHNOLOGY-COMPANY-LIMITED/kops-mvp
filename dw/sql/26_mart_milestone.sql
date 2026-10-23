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
