-- Data issues that need the conformed model to detect (Python parsers log the per-file ones).

-- Daily production rows of an earlier season still in the sheet (kept in raw, not in core.daily_row, 17_core_phase1)
INSERT INTO etl.data_issue
SELECT file_id, 'INFO', 'DAILY_CARRY_OVER', style_raw,
       count(*) || ' row(s) of an earlier-season style in a ' || any_value(season) || ' daily report: not loaded in core',
       any_value(sheet)
FROM raw.daily_prod_row
WHERE year(coalesce(rdd, etd)) < 2000 + CAST(left(season, 2) AS INT) - 1
   OR CAST(nullif(regexp_extract(style_raw, '^[A-Z]{3}-(\d{2})\d{3}', 1), '') AS INT) < CAST(left(season, 2) AS INT) - 1
GROUP BY file_id, style_raw;
INSERT INTO etl.data_issue
SELECT file_id, 'WARN', 'FACTORY_UNKNOWN', style_no, 'Factory "' || factory_raw || '" not in alias list', 'ORDER RECAP!E' || row_no
FROM core.style_order WHERE is_active AND factory_code IS NULL AND factory_raw IS NOT NULL;

INSERT INTO etl.data_issue
SELECT file_id, 'INFO', 'FACTORY_MISSING', style_no, 'Active style without factory', 'ORDER RECAP!E' || row_no
FROM core.style_order WHERE is_active AND factory_raw IS NULL;

INSERT INTO etl.data_issue
SELECT DISTINCT s.file_id, 'WARN', 'STYLE_ALIAS_UNCONFIRMED', s.style_no_raw,
       'Style code ' || s.style_no_raw || ' mapped to ' || s.style_no || ' (Q05, chờ KLMAS xác nhận)', s.sheet
FROM core.shipment_detail s WHERE s.style_no <> s.style_no_raw;

INSERT INTO etl.data_issue
SELECT DISTINCT s.file_id, 'WARN', 'STYLE_NOT_IN_ORDER', s.style_no, 'Style in Shipment Status but not in ORDER RECAP', s.sheet
FROM core.shipment_detail s
WHERE s.style_no IS NOT NULL AND s.style_no NOT IN (SELECT style_no FROM core.style_order);

INSERT INTO etl.data_issue
SELECT o.file_id, 'WARN', 'XSRC_MISMATCH', o.style_no,
       'Order qty: ORDER RECAP ' || o.order_qty || ' vs Shipment ' || coalesce(sh.q::VARCHAR, '-') || ' vs Production ' || coalesce(p.order_qty_reported::VARCHAR, '-'),
       'ORDER RECAP!J' || o.row_no
FROM core.style_order o
LEFT JOIN (SELECT style_no, sum(qty) q FROM core.shipment_detail WHERE section = 'ORDER' GROUP BY 1) sh USING (style_no)
LEFT JOIN core.production_snapshot p USING (style_no)
WHERE o.is_active AND ((sh.q IS NOT NULL AND sh.q <> o.order_qty) OR (p.order_qty_reported IS NOT NULL AND p.order_qty_reported <> o.order_qty));
