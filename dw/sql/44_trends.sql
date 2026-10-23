-- Season trends (F-04 chatbot, F-05 "Xu hướng" page): size, colour, item, gender, main fabric per season, real data only.
-- Only what the files carry: CHALLENGER (ORDER RECAP colours, item / gender from the style code, main fabric) and the
-- Shipment Status assortment per size (CHALLENGER 26FW, MIZUNO 27SS; CHALLENGER 27SS has no Shipment Status yet).
-- 25SS / 25FW exist only as synthetic seasons (no size / colour) and are not here.
CREATE TABLE mart.trend_style AS          -- one row per active style with its attributes (customer x season x brand)
SELECT s.customer, s.season, s.brand, s.style_no, s.factory_code, s.order_qty,
       o.gender, o.item_type, o.main_fabric,
       nullif(trim(regexp_extract(o.main_fabric, '^([^)]+)\)', 1)), '') AS fabric_supplier
FROM dim.style s JOIN core.style_order o ON o.season = s.season AND o.style_no = s.style_no
WHERE s.customer = 'CHALLENGER' AND s.is_active;

CREATE TABLE mart.trend_size AS          -- ordered qty per size (Shipment Status assortment: CHALLENGER 26FW, MIZUNO 27SS)
SELECT s.customer, a.season, s.brand, t.gender, t.item_type,
       upper(trim(regexp_replace(a.size_code, '\s*\(.*$', ''))) AS size_code,      -- MIZUNO 'L(100)' -> 'L'
       sum(a.ordered) AS qty, count(DISTINCT a.style_no) AS styles
FROM mart.assortment a
JOIN (SELECT DISTINCT season, style_no, customer, brand FROM dim.style) s ON s.season = a.season AND s.style_no = a.style_no
LEFT JOIN mart.trend_style t ON t.season = a.season AND t.style_no = a.style_no
WHERE a.ordered > 0 GROUP BY ALL;

CREATE TABLE mart.trend_color AS         -- ordered qty per colour (ORDER RECAP, active colours)
SELECT t.customer, t.season, t.brand, t.gender, t.item_type, upper(trim(c.color)) AS color,
       sum(c.order_qty) AS qty, count(DISTINCT c.style_no) AS styles
FROM core.order_color c JOIN mart.trend_style t ON t.season = c.season AND t.style_no = c.style_no
WHERE c.is_active AND c.order_qty > 0 GROUP BY ALL;

CREATE TABLE mart.trend_item AS          -- styles and qty per item / gender
SELECT customer, season, brand, gender, item_type, count(*) AS styles, sum(order_qty) AS qty
FROM mart.trend_style GROUP BY ALL;

CREATE TABLE mart.trend_fabric AS        -- main fabric supplier per season (the files name supplier + article, no composition)
SELECT customer, season, brand, coalesce(fabric_supplier, '(?)') AS fabric_supplier, count(*) AS styles, sum(order_qty) AS qty
FROM mart.trend_style GROUP BY ALL;
