-- =====================================================================
-- KOPS Production Data Warehouse — PostgreSQL 16, schema `dw` (star schema)
-- Source: schema `core` (OLTP, see analys-docs/schema.sql), loaded by dbt.
-- Answers: order & style history, factory-change history per lot (SCD2),
--          progress vs ETD/RDD, return % per partner.
-- Status: DRAFT for the KOPS MVP discussion. Tested on PostgreSQL 16.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS dw;

-- ---------------- dimensions ----------------
CREATE TABLE dw.dim_date (
  date_key     int PRIMARY KEY,               -- 20261012
  full_date    date NOT NULL UNIQUE,
  iso_year     smallint NOT NULL,
  iso_week     smallint NOT NULL,
  month        smallint NOT NULL,
  is_sunday    boolean NOT NULL               -- garment lines in VN work Mon–Sat
);

CREATE TABLE dw.dim_season (
  season_key  smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  brand_code  varchar(20) NOT NULL,           -- CHALLENGER, FILA ...
  season_code varchar(10) NOT NULL,           -- 26FW
  half        char(2) NOT NULL CHECK (half IN ('SS','FW')),
  season_year smallint NOT NULL,
  UNIQUE (brand_code, season_code)
);

CREATE TABLE dw.dim_partner (                 -- factories, fabric/trim suppliers, brands (buyers), 3rd-party QC clients
  partner_key   int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  partner_type  varchar(10) NOT NULL CHECK (partner_type IN ('FACTORY','SUPPLIER','BRAND','LOGISTICS')),
  partner_code  varchar(20) NOT NULL,
  partner_name  text NOT NULL,
  region        text,
  country_code  char(2),
  is_active     boolean NOT NULL DEFAULT true,
  UNIQUE (partner_type, partner_code)
);

CREATE TABLE dw.dim_style (                   -- SCD2: description / ETD / qty-relevant attributes change over the season
  style_key      int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_no       varchar(12) NOT NULL,        -- care-label number, natural key
  season_key     smallint NOT NULL REFERENCES dw.dim_season(season_key),
  order_no       varchar(10),                 -- F9, W30, O20, R1, SP1
  collection     text,                        -- 26FW-FALL, ONLINE (ESSENTIAL LINE), REORDER
  gender         char(1),
  item_type      char(2),
  desc_en        text,
  name_kr        text,
  main_fabric    text,
  etd_vn         date,
  rdd_kr         date,
  status_code    varchar(20),
  valid_from     timestamptz NOT NULL,
  valid_to       timestamptz,                 -- NULL = current version
  is_current     boolean GENERATED ALWAYS AS (valid_to IS NULL) STORED,
  change_reason  text
);
CREATE UNIQUE INDEX ux_dim_style_current ON dw.dim_style(style_no, season_key) WHERE valid_to IS NULL;
CREATE INDEX ON dw.dim_style(style_no);

CREATE TABLE dw.dim_factory_assignment (      -- SCD2: one row per (style, factory, period). Brief: "lịch sử thay đổi nhà máy của các lô hàng"
  assignment_key int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_no       varchar(12) NOT NULL,
  season_key     smallint NOT NULL REFERENCES dw.dim_season(season_key),
  factory_key    int NOT NULL REFERENCES dw.dim_partner(partner_key),
  valid_from     date NOT NULL,
  valid_to       date,                        -- exclusive
  move_reason    varchar(20) CHECK (move_reason IN ('INITIAL','SCHEDULE','CAPACITY','QUALITY','COST','OTHER')),
  source         text NOT NULL,               -- 'ORDER RECAP note 260512', 'FAB(0615) snapshot', 'KOPS user'
  changed_by     text,
  CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX ux_fa_current ON dw.dim_factory_assignment(style_no, season_key) WHERE valid_to IS NULL;
CREATE INDEX ON dw.dim_factory_assignment(factory_key);

CREATE TABLE dw.dim_inspector (
  inspector_key int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  employee_code varchar(20) NOT NULL UNIQUE,
  full_name     text NOT NULL,
  region        text,
  specialties   char(2)[],
  dedicated_factory_key int REFERENCES dw.dim_partner(partner_key)
);

CREATE TABLE dw.dim_defect (
  defect_code varchar(10) PRIMARY KEY,        -- A01 ...
  name_vi     text NOT NULL,
  name_ko     text,
  severity    varchar(8) NOT NULL CHECK (severity IN ('Critical','Major','Minor'))
);

-- ---------------- facts ----------------
CREATE TABLE dw.fact_order_line (             -- grain: style version × colour × size (current order)
  style_key    int NOT NULL REFERENCES dw.dim_style(style_key),
  factory_key  int REFERENCES dw.dim_partner(partner_key),
  color        text NOT NULL,
  size_code    varchar(10) NOT NULL,
  order_qty    int NOT NULL CHECK (order_qty >= 0),
  PRIMARY KEY (style_key, color, size_code)
);

CREATE TABLE dw.fact_shipment_line (          -- grain: shipment batch × style × colour × size
  ship_etd_key int NOT NULL REFERENCES dw.dim_date(date_key),
  ship_eta_key int REFERENCES dw.dim_date(date_key),
  style_key    int NOT NULL REFERENCES dw.dim_style(style_key),
  factory_key  int NOT NULL REFERENCES dw.dim_partner(partner_key),
  mode         varchar(6) NOT NULL,           -- SEA / AIR / HC
  batch_no     smallint NOT NULL,             -- 1st..4th ship
  color        text NOT NULL,
  size_code    varchar(10) NOT NULL,
  qty          int NOT NULL CHECK (qty > 0),
  is_sample    boolean NOT NULL DEFAULT false,
  delay_vs_etd_days int,                      -- ship ETD − style ETD (computed in dbt)
  PRIMARY KEY (ship_etd_key, style_key, color, size_code, is_sample, batch_no)
);
CREATE INDEX ON dw.fact_shipment_line(factory_key);

CREATE TABLE dw.fact_production_daily (       -- grain: day × style × factory (daily production report)
  date_key       int NOT NULL REFERENCES dw.dim_date(date_key),
  style_key      int NOT NULL REFERENCES dw.dim_style(style_key),
  factory_key    int NOT NULL REFERENCES dw.dim_partner(partner_key),
  line_no        text,
  cut_qty        int NOT NULL DEFAULT 0,
  input_qty      int NOT NULL DEFAULT 0,
  output_qty     int NOT NULL DEFAULT 0,
  inspected_qty  int NOT NULL DEFAULT 0,
  plan_output    int,                         -- for "under plan" alerts (meeting item #8)
  PRIMARY KEY (date_key, style_key, factory_key)
);

CREATE TABLE dw.fact_inspection (             -- grain: one inspection lot (own orders + 3rd-party brands)
  inspection_id   bigint PRIMARY KEY,         -- from core.inspection
  date_key        int NOT NULL REFERENCES dw.dim_date(date_key),
  brand_key       int NOT NULL REFERENCES dw.dim_partner(partner_key),
  factory_key     int NOT NULL REFERENCES dw.dim_partner(partner_key),
  inspector_key   int NOT NULL REFERENCES dw.dim_inspector(inspector_key),
  style_key       int REFERENCES dw.dim_style(style_key),      -- NULL for 3rd-party lots not managed by KLMAS
  external_style  text,
  inspection_type varchar(10) NOT NULL CHECK (inspection_type IN ('INLINE','FINAL','REINSPECT')),
  lot_qty         int NOT NULL CHECK (lot_qty > 0),
  sample_qty      int NOT NULL CHECK (sample_qty > 0),
  critical_cnt    int NOT NULL DEFAULT 0,
  major_cnt       int NOT NULL DEFAULT 0,
  minor_cnt       int NOT NULL DEFAULT 0,
  result          varchar(4) NOT NULL CHECK (result IN ('PASS','FAIL')),
  returned_qty    int NOT NULL DEFAULT 0,     -- qty sent back to factory for rework after FAIL
  claim_qty       int NOT NULL DEFAULT 0,     -- qty claimed by buyer after delivery
  missed_by_inspector boolean NOT NULL DEFAULT false            -- set by re-inspection sampling (inspector accountability)
);
CREATE INDEX ON dw.fact_inspection(factory_key, date_key);
CREATE INDEX ON dw.fact_inspection(brand_key, date_key);

CREATE TABLE dw.fact_inspection_defect (
  inspection_id bigint NOT NULL REFERENCES dw.fact_inspection(inspection_id) ON DELETE CASCADE,
  defect_code   varchar(10) NOT NULL REFERENCES dw.dim_defect(defect_code),
  qty           int NOT NULL CHECK (qty > 0),
  PRIMARY KEY (inspection_id, defect_code)
);

-- ---------------- marts / semantic views ----------------
-- Return % per partner and month = (returned + claimed) / inspected lot qty   (definition to be confirmed by KLMAS)
CREATE VIEW dw.v_partner_return_rate AS
SELECT p.partner_name AS factory, d.iso_year, d.month,
       count(*)                                   AS lots,
       sum(i.lot_qty)                             AS inspected_qty,
       round(100.0 * count(*) FILTER (WHERE i.result = 'FAIL') / count(*), 2)              AS lot_fail_pct,
       round(100.0 * (sum(i.returned_qty) + sum(i.claim_qty)) / nullif(sum(i.lot_qty),0), 2) AS return_pct,
       round(100.0 * sum(i.major_cnt + i.minor_cnt + i.critical_cnt) / nullif(sum(i.sample_qty),0), 2) AS dhu
FROM dw.fact_inspection i
JOIN dw.dim_partner p ON p.partner_key = i.factory_key
JOIN dw.dim_date d    ON d.date_key = i.date_key
GROUP BY 1,2,3;

-- Factory moves: every SCD2 transition with previous factory
CREATE VIEW dw.v_factory_moves AS
SELECT fa.style_no, s.season_code, prev.partner_name AS from_factory, cur.partner_name AS to_factory,
       fa.valid_from AS moved_on, fa.move_reason, fa.source, fa.changed_by
FROM (SELECT fa.*, lag(factory_key) OVER (PARTITION BY style_no, season_key ORDER BY valid_from) AS prev_factory_key
      FROM dw.dim_factory_assignment fa) fa
JOIN dw.dim_season s  ON s.season_key = fa.season_key
JOIN dw.dim_partner cur ON cur.partner_key = fa.factory_key
LEFT JOIN dw.dim_partner prev ON prev.partner_key = fa.prev_factory_key
WHERE fa.prev_factory_key IS NOT NULL AND fa.prev_factory_key <> fa.factory_key;

-- Style progress vs ETD with projected ready date (meeting rule: remaining ÷ daily output, skip Sundays, +5 days)
CREATE VIEW dw.v_style_progress AS
WITH o AS (SELECT style_key, sum(order_qty) AS order_qty FROM dw.fact_order_line GROUP BY 1),
     p AS (SELECT style_key, sum(output_qty) AS output_qty, sum(inspected_qty) AS inspected_qty,
                  (array_agg(output_qty ORDER BY date_key DESC))[1] AS last_day_output
           FROM dw.fact_production_daily GROUP BY 1),
     sh AS (SELECT style_key, sum(qty) FILTER (WHERE NOT is_sample) AS shipped_qty, sum(qty) FILTER (WHERE is_sample) AS sample_qty,
                   min(delay_vs_etd_days) AS first_ship_delay FROM dw.fact_shipment_line GROUP BY 1)
SELECT s.style_no, se.season_code, s.order_no, s.etd_vn, s.rdd_kr,
       o.order_qty, coalesce(p.output_qty,0) AS output_qty, coalesce(p.inspected_qty,0) AS inspected_qty,
       coalesce(sh.shipped_qty,0) AS shipped_qty, coalesce(sh.sample_qty,0) AS sample_qty, sh.first_ship_delay,
       CASE WHEN coalesce(p.output_qty,0) < o.order_qty THEN
         current_date + (ceil((o.order_qty - coalesce(p.output_qty,0))::numeric / greatest(coalesce(nullif(p.last_day_output,0),45),1)) * 7 / 6)::int + 5
       END AS projected_ready_date
FROM dw.dim_style s
JOIN dw.dim_season se ON se.season_key = s.season_key
JOIN o ON o.style_key = s.style_key
LEFT JOIN p ON p.style_key = s.style_key
LEFT JOIN sh ON sh.style_key = s.style_key
WHERE s.is_current;

-- ---------------- SCD2 load pattern (dbt snapshot equivalent) ----------------
-- Called by the loader with the current factory per style from core.factory_assignment.
CREATE OR REPLACE FUNCTION dw.upsert_factory_assignment(p_style text, p_season smallint, p_factory int,
                                                         p_on date, p_reason text, p_source text, p_by text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE cur dw.dim_factory_assignment; had boolean;
BEGIN
  SELECT * INTO cur FROM dw.dim_factory_assignment
   WHERE style_no = p_style AND season_key = p_season AND valid_to IS NULL FOR UPDATE;
  had := FOUND;
  IF had AND cur.factory_key = p_factory THEN RETURN; END IF;          -- no change
  IF had THEN
    UPDATE dw.dim_factory_assignment SET valid_to = p_on WHERE assignment_key = cur.assignment_key;
  END IF;
  INSERT INTO dw.dim_factory_assignment(style_no, season_key, factory_key, valid_from, move_reason, source, changed_by)
  VALUES (p_style, p_season, p_factory, p_on, CASE WHEN had THEN p_reason ELSE 'INITIAL' END, p_source, p_by);
END $$;
