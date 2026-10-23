-- core: all customers (CHALLENGER + DHG, JBEE, KOFA, DKM), production plans and the style dictionary.

CREATE TABLE core.order_line_ext AS
SELECT o.* FROM raw.order_line_ext o JOIN core.current_file f USING (file_id);

-- One row per style for every customer. CHALLENGER comes from the detailed model (core.style_order).
CREATE TABLE core.order_portfolio AS
SELECT 'CHALLENGER' AS customer, 'CHALLENGER' AS brand, season, style_no, NULL AS file_no, factory_code, factory_raw,
       order_qty, etd_vn AS etd, rdd_kr AS rdd, status, is_active, 'RDD-12/-14 (Q26)' AS etd_rule, file_id
FROM core.style_order
UNION ALL
SELECT coalesce(customer, '?'), coalesce(brand, '?'), season, style_no, file_no, factory_code, factory_raw,
       order_qty, etd, rdd, status_label, is_active, etd_rule, file_id
FROM core.order_line_ext;

CREATE TABLE core.production_plan AS
SELECT p.*,
       CASE WHEN p.bal_days IS NULL THEN 'UNKNOWN' WHEN p.bal_days < 0 THEN 'LATE'
            WHEN p.bal_days <= 3 THEN 'TIGHT' ELSE 'OK' END AS plan_risk,
       p.qty / nullif(p.daily_target, 0) AS days_needed
FROM raw.production_plan p JOIN core.current_file f USING (file_id);

-- Every code a person may write in an email or file for a style -> the style (all customers).
CREATE TABLE core.style_dictionary AS
WITH keys AS (
  SELECT style_no AS key, style_no, customer, brand, season, 'STYLE' AS kind FROM core.order_portfolio
  UNION ALL SELECT file_no, style_no, customer, brand, season, 'FILE_NO' FROM core.order_portfolio WHERE file_no IS NOT NULL
  UNION ALL SELECT trim(a.alias), o.style_no, o.customer, o.brand, o.season, 'ALIAS'
            FROM core.order_line_ext o, unnest(string_split(o.style_aliases, ',')) AS a(alias) WHERE o.style_aliases IS NOT NULL
  UNION ALL SELECT alias_style, style_no, 'CHALLENGER', 'CHALLENGER', NULL, 'ALIAS' FROM stg.style_alias
  UNION ALL SELECT style_no, style_no, customer, brand, season, 'PLAN' FROM core.production_plan
  UNION ALL SELECT file_no, style_no, customer, brand, season, 'PLAN_FILE_NO' FROM core.production_plan WHERE file_no IS NOT NULL)
SELECT DISTINCT upper(trim(key)) AS key, style_no, customer, brand, season, kind
FROM keys WHERE key IS NOT NULL AND length(trim(key)) >= 6;
