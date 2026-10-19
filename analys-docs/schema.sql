-- =====================================================================
-- KLMAS production-management DB — PostgreSQL 15+  (Option B: etl/raw/stg/core/mart)
-- Status: DRAFT. Items marked (P) are provisional — require business confirmation.
-- Generated from analysis of klmas-docs (2026-10-16). Not executed against any server.
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- for factory_assignment non-overlap
CREATE EXTENSION IF NOT EXISTS unaccent;     -- for alias normalisation (Vietnamese diacritics)

CREATE SCHEMA IF NOT EXISTS etl;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;

-- ---------------------------------------------------------------------
-- ETL metadata
-- ---------------------------------------------------------------------
CREATE TABLE etl.source_file (
  file_id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  file_path            text        NOT NULL,
  file_name            text        NOT NULL,
  sha256               char(64)    NOT NULL UNIQUE,
  size_bytes           bigint      NOT NULL,
  file_mtime           timestamptz,
  file_format          varchar(8)  NOT NULL CHECK (file_format IN ('xlsx','xlsb','xls','pdf')),
  doc_type             varchar(30) NOT NULL,          -- PRODUCTION_STATUS | SHIPMENT_STATUS | ORDER_RECAP | COMPANY_PROFILE
  report_date          date,                          -- parsed from YYMMDD prefix
  revision             varchar(5),                    -- e.g. R2
  author_tag           varchar(30),                   -- e.g. HUONG, MJ
  season_code          varchar(10),
  data_cutoff_note     text,                          -- e.g. '(~10.10)'
  duplicate_of_file_id bigint REFERENCES etl.source_file(file_id),
  superseded_by_file_id bigint REFERENCES etl.source_file(file_id),
  registered_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE etl.ingestion_run (
  run_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  file_id        bigint      NOT NULL REFERENCES etl.source_file(file_id),
  parser_name    varchar(50) NOT NULL,
  parser_version varchar(20) NOT NULL,
  started_at     timestamptz NOT NULL DEFAULT now(),
  finished_at    timestamptz,
  status         varchar(12) NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','SUCCESS','PARTIAL','FAILED','ROLLED_BACK')),
  counts         jsonb       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ON etl.ingestion_run(file_id);

CREATE TABLE etl.data_issue (
  issue_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id      bigint      NOT NULL REFERENCES etl.ingestion_run(run_id),
  file_id     bigint      NOT NULL REFERENCES etl.source_file(file_id),
  sheet_name  text,
  cell_ref    text,                     -- A1 ref or block ref, e.g. 'DM(27)!B4:L34'
  entity      varchar(40),
  rule_code   varchar(40) NOT NULL,     -- e.g. STYLE_NO_FORMAT, ETA_BEFORE_ETD, XSRC_MISMATCH, EXCEL_ERROR
  severity    varchar(8)  NOT NULL CHECK (severity IN ('ERROR','WARN','INFO')),
  raw_value   text,
  message     text        NOT NULL,
  status      varchar(10) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','ACCEPTED','FIXED','IGNORED')),
  resolved_by text,
  resolved_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON etl.data_issue(rule_code, status);
CREATE INDEX ON etl.data_issue(file_id);

-- ---------------------------------------------------------------------
-- RAW layer: verbatim cells
-- ---------------------------------------------------------------------
CREATE TABLE raw.sheet (
  sheet_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id       bigint NOT NULL REFERENCES etl.ingestion_run(run_id),
  file_id      bigint NOT NULL REFERENCES etl.source_file(file_id),
  sheet_name   text   NOT NULL,
  sheet_index  smallint NOT NULL,
  sheet_state  varchar(12) NOT NULL,     -- visible | hidden | veryHidden
  dimension    text,
  merged_count int,
  UNIQUE (run_id, sheet_name)
);

CREATE TABLE raw.cell (
  sheet_id      bigint   NOT NULL REFERENCES raw.sheet(sheet_id) ON DELETE CASCADE,
  row_no        int      NOT NULL,
  col_no        int      NOT NULL,
  a1_ref        varchar(12) NOT NULL,
  value_type    varchar(10) NOT NULL,    -- s | n | d | b | e(error) | f(formula only)
  value_text    text,                    -- verbatim display/string value
  value_num     numeric,
  formula       text,
  fill_rgb      varchar(10),             -- needed: status is colour-coded
  number_format text,
  merged_range  text,
  PRIMARY KEY (sheet_id, row_no, col_no)
);

CREATE TABLE raw.pdf_page (
  file_id   bigint NOT NULL REFERENCES etl.source_file(file_id),
  run_id    bigint NOT NULL REFERENCES etl.ingestion_run(run_id),
  page_no   smallint NOT NULL,
  text_layer text,
  ocr_text   text,
  needs_ocr  boolean NOT NULL DEFAULT false,
  PRIMARY KEY (run_id, page_no)
);

-- ---------------------------------------------------------------------
-- STAGING (template-specific, text-typed + parsed columns). Examples.
-- ---------------------------------------------------------------------
CREATE TABLE stg.ship_block_line (            -- F2: one row per block x section x color x size
  run_id       bigint NOT NULL REFERENCES etl.ingestion_run(run_id),
  sheet_name   text   NOT NULL,
  block_ref    text   NOT NULL,               -- e.g. 'B4'
  block_no_raw text,
  style_no_raw text,
  rec_type     varchar(10) NOT NULL CHECK (rec_type IN ('ORDER','SHIPMENT','SAMPLE')),
  event_label_raw text,
  color_raw    text,
  size_raw     text NOT NULL,
  qty          numeric NOT NULL,
  src_row      int NOT NULL,
  src_col      int NOT NULL,
  parse_ok     boolean NOT NULL DEFAULT true,
  PRIMARY KEY (run_id, sheet_name, src_row, src_col)
);

CREATE TABLE stg.recap_style_block (          -- F3/F4 ORDER RECAP: one row per 4-row block
  run_id        bigint NOT NULL REFERENCES etl.ingestion_run(run_id),
  first_row     int    NOT NULL,
  order_no_raw  text,
  style_no_raw  text   NOT NULL,
  factory_raw   text,
  collection_raw text,
  line_raw      text,
  item_en_raw   text,
  item_kr_raw   text,
  main_fabric_raw text,
  total_qty_raw text,
  etd_raw       text,
  rdd_raw       text,
  status_fill_rgb varchar(10),
  milestones    jsonb NOT NULL DEFAULT '{}'::jsonb,   -- {column_header: raw_text}
  PRIMARY KEY (run_id, first_row)
);

CREATE TABLE stg.recap_color_row (
  run_id     bigint NOT NULL,
  first_row  int    NOT NULL,
  src_row    int    NOT NULL,
  color_raw  text   NOT NULL,
  qty_raw    text,
  note_raw   text,
  PRIMARY KEY (run_id, src_row),
  FOREIGN KEY (run_id, first_row) REFERENCES stg.recap_style_block(run_id, first_row)
);

-- stg.prod_status_row (F1) and stg.fab_row (FAB sheets) follow the same pattern: all source columns as text + run_id + src_row.

-- ---------------------------------------------------------------------
-- CORE: reference data
-- ---------------------------------------------------------------------
CREATE TABLE core.brand (
  brand_id   smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  brand_code varchar(20) NOT NULL UNIQUE,     -- 'CHALLENGER'
  brand_name text NOT NULL,
  style_prefix varchar(4)                     -- 'CH'
);

CREATE TABLE core.season (
  season_id   smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  brand_id    smallint NOT NULL REFERENCES core.brand(brand_id),
  season_code varchar(10) NOT NULL,           -- '26FW'
  season_year smallint NOT NULL CHECK (season_year BETWEEN 2000 AND 2100),
  half        char(2)  NOT NULL CHECK (half IN ('SS','FW')),
  UNIQUE (brand_id, season_code)
);

CREATE TABLE core.collection (
  collection_id   int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id       smallint NOT NULL REFERENCES core.season(season_id),
  collection_code text NOT NULL,             -- '26FW-FALL', '26FW-ONLINE (ESSENTIAL LINE)', 'REORDER'
  channel         varchar(10) CHECK (channel IN ('OFFLINE','ONLINE')),
  is_reorder      boolean NOT NULL DEFAULT false,
  UNIQUE (season_id, collection_code)
);

CREATE TABLE core.product_line (
  line_code varchar(12) PRIMARY KEY,          -- NORMAL | ESSENTIALS | REORDER
  name_kr   text,                             -- 정상 | ... | 리오더
  name_en   text
);

CREATE TABLE core.item_type (
  item_type_code char(2) PRIMARY KEY,         -- JK, VT, WT, LT, ST, PT, SK, HP, OP, IT, MK, HC, GW, CP, WI ...
  name_en  text,
  name_kr  text,
  category varchar(10)                        -- (P) TOP | BOTTOM | OUTER | ACC
);

CREATE TABLE core.factory (
  factory_id     int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  factory_code   varchar(20) NOT NULL UNIQUE, -- 'TBM', 'DM', 'TP' ... (P) codes to be agreed
  name_canonical text NOT NULL UNIQUE,        -- 'TAN BINH MINH'
  name_vi        text,                        -- with diacritics
  location       text,
  parent_factory_id int REFERENCES core.factory(factory_id),   -- (P) FG VINA / FG BAC GIANG group
  is_active      boolean NOT NULL DEFAULT true
);

CREATE TABLE core.factory_alias (
  alias_norm text PRIMARY KEY,                -- upper(unaccent(trim(x)))
  factory_id int  NOT NULL REFERENCES core.factory(factory_id),
  alias_raw  text NOT NULL
);
CREATE INDEX ON core.factory_alias(factory_id);

CREATE TABLE core.color (
  color_id   int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  color_code varchar(30) NOT NULL UNIQUE,     -- 'KHAKI_GREY'
  color_name text NOT NULL
);
CREATE TABLE core.color_alias (
  alias_norm text PRIMARY KEY,                -- 'K.GREY','K/GREY','K GREY' -> KHAKI_GREY
  color_id   int NOT NULL REFERENCES core.color(color_id)
);
CREATE INDEX ON core.color_alias(color_id);

CREATE TABLE core.size (
  size_code  varchar(10) PRIMARY KEY,         -- XS,S,M,L,XL,2XL,F
  sort_order smallint NOT NULL
);
CREATE TABLE core.size_alias (
  alias      varchar(10) PRIMARY KEY,         -- 'XXL' -> '2XL' (P: confirm equivalence)
  size_code  varchar(10) NOT NULL REFERENCES core.size(size_code)
);

CREATE TABLE core.shipping_mode (
  mode_code varchar(6) PRIMARY KEY,           -- SEA, AIR, HC (hand carry - P)
  name text NOT NULL
);

CREATE TABLE core.milestone_type (
  milestone_code varchar(30) PRIMARY KEY,
  stage          varchar(20) NOT NULL,        -- SAMPLE | MATERIAL | BULK_PREP | PRODUCTION | SHIPPING | DOCS
  name_en        text NOT NULL,
  sort_order     smallint NOT NULL
);

CREATE TABLE core.style_status (
  status_code      varchar(20) PRIMARY KEY,   -- NOT_FIXED, FIXED_PRICE, ON_PRODUCTION, SEWING_FINISHED, KOREA_SHIP_OUT, CANCEL, PENDING
  legend_fill_rgb  varchar(10),
  is_terminal      boolean NOT NULL DEFAULT false
);

CREATE TABLE core.supplier (
  supplier_id   int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  supplier_type varchar(6) NOT NULL CHECK (supplier_type IN ('FABRIC','TRIM')),
  supplier_name text NOT NULL,
  country_code  char(2),
  UNIQUE (supplier_type, supplier_name)
);
CREATE TABLE core.supplier_alias (
  alias_norm  text PRIMARY KEY,
  supplier_id int NOT NULL REFERENCES core.supplier(supplier_id)
);

-- ---------------------------------------------------------------------
-- CORE: product & order
-- ---------------------------------------------------------------------
CREATE TABLE core.style (
  style_id        int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_no        varchar(12) NOT NULL UNIQUE,
  brand_id        smallint NOT NULL REFERENCES core.brand(brand_id),
  gender          char(1) CHECK (gender IN ('M','W','U')),
  item_type_code  char(2) REFERENCES core.item_type(item_type_code),
  year_code       char(1),                    -- (P) E=2025, F=2026, G=2027
  subseason_digit char(1),                    -- (P) 1 spring,2 summer,3 fall,4 winter
  serial_no       char(4),
  description_en  text,
  name_kr         text,
  is_code_valid   boolean GENERATED ALWAYS AS (style_no ~ '^CH[A-Z][0-9][MWU][A-Z]{2}[0-9]{4}$') STORED,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz
);
CREATE INDEX ON core.style(brand_id);
CREATE INDEX ON core.style(item_type_code);

CREATE TABLE core.style_alias (
  alias_style_no varchar(16) PRIMARY KEY,     -- 'CHFWWT6817', 'CHF4WSK6851' ...
  style_id       int  NOT NULL REFERENCES core.style(style_id),
  reason         text NOT NULL,               -- TYPO | RECODED | UNCONFIRMED
  confirmed      boolean NOT NULL DEFAULT false
);
CREATE INDEX ON core.style_alias(style_id);

CREATE TABLE core.style_order (
  style_order_id   int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id        smallint NOT NULL REFERENCES core.season(season_id),
  collection_id    int      NOT NULL REFERENCES core.collection(collection_id),
  style_id         int      NOT NULL REFERENCES core.style(style_id),
  order_no         varchar(10),               -- 'F9','W30','O20','R1','SP1','S6'
  line_code        varchar(12) REFERENCES core.product_line(line_code),
  status_code      varchar(20) NOT NULL REFERENCES core.style_status(status_code),
  etd_vn           date,
  rdd_kr           date,
  etd_raw          text,
  main_fabric_text text,
  cancelled_at     date,
  remarks          text,
  source_file_id   bigint REFERENCES etl.source_file(file_id),
  ingestion_run_id bigint REFERENCES etl.ingestion_run(run_id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz,
  UNIQUE (season_id, style_id, collection_id),
  CONSTRAINT ck_rdd_after_etd CHECK (rdd_kr IS NULL OR etd_vn IS NULL OR rdd_kr >= etd_vn)
);
CREATE UNIQUE INDEX ux_style_order_no ON core.style_order(season_id, order_no) WHERE order_no IS NOT NULL;
CREATE INDEX ON core.style_order(style_id);
CREATE INDEX ON core.style_order(collection_id);
CREATE INDEX ON core.style_order(status_code);
CREATE INDEX ON core.style_order(etd_vn);

CREATE TABLE core.style_order_status_history (
  style_order_id int NOT NULL REFERENCES core.style_order(style_order_id),
  status_code    varchar(20) NOT NULL REFERENCES core.style_status(status_code),
  valid_from     timestamptz NOT NULL,
  source_file_id bigint REFERENCES etl.source_file(file_id),
  PRIMARY KEY (style_order_id, valid_from)
);

CREATE TABLE core.style_order_color (
  soc_id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id int  NOT NULL REFERENCES core.style_order(style_order_id),
  color_id       int  NOT NULL REFERENCES core.color(color_id),
  color_raw      text NOT NULL,
  seq            smallint,
  order_qty      int  NOT NULL CHECK (order_qty >= 0),
  note           text,
  source_file_id bigint REFERENCES etl.source_file(file_id),
  UNIQUE (style_order_id, color_id)
);
CREATE INDEX ON core.style_order_color(color_id);

CREATE TABLE core.order_qty_size (
  soc_id    int NOT NULL REFERENCES core.style_order_color(soc_id) ON DELETE CASCADE,
  size_code varchar(10) NOT NULL REFERENCES core.size(size_code),
  qty       int NOT NULL CHECK (qty >= 0),
  source_file_id bigint REFERENCES etl.source_file(file_id),
  PRIMARY KEY (soc_id, size_code)
);

CREATE TABLE core.order_qty_change (
  change_id   int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  soc_id      int NOT NULL REFERENCES core.style_order_color(soc_id),
  change_date date,
  qty_before  int,
  qty_after   int,
  note_raw    text NOT NULL
);
CREATE INDEX ON core.order_qty_change(soc_id);

CREATE TABLE core.factory_assignment (
  assignment_id  int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id int  NOT NULL REFERENCES core.style_order(style_order_id),
  factory_id     int  NOT NULL REFERENCES core.factory(factory_id),
  valid_from     date NOT NULL,
  valid_to       date,
  note_raw       text,
  source_file_id bigint REFERENCES etl.source_file(file_id),
  CHECK (valid_to IS NULL OR valid_to > valid_from),
  EXCLUDE USING gist (style_order_id WITH =, daterange(valid_from, valid_to, '[)') WITH &&)
);
CREATE INDEX ON core.factory_assignment(factory_id);

CREATE TABLE core.trim_item (
  trim_item_id    int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  trim_code       varchar(20) NOT NULL UNIQUE,   -- 'AP_TR02','DW_EM003','DS_CHLB13'
  supplier_prefix varchar(5),                    -- (P) AP, DW, DS, AC, ID, JY, FB
  trim_type       text,                          -- H.T LOGO, WAPPEN, LABEL, EMB, PRINT
  description     text
);

CREATE TABLE core.style_trim (
  style_trim_id  int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id int NOT NULL REFERENCES core.style_order(style_order_id),
  group_no       smallint,
  trim_group     text,
  trim_item_id   int REFERENCES core.trim_item(trim_item_id),
  spec_text      text NOT NULL,
  source_file_id bigint REFERENCES etl.source_file(file_id)
);
CREATE INDEX ON core.style_trim(style_order_id);
CREATE INDEX ON core.style_trim(trim_item_id);

-- ---------------------------------------------------------------------
-- CORE: progress
-- ---------------------------------------------------------------------
CREATE TABLE core.milestone_event (
  event_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id int NOT NULL REFERENCES core.style_order(style_order_id),
  milestone_code varchar(30) NOT NULL REFERENCES core.milestone_type(milestone_code),
  round_no       smallint NOT NULL DEFAULT 1,
  action         varchar(12) CHECK (action IN ('PLAN','SENT','RECEIVED','RETURN','REJECT','CMMT','CFM','ETD','ETA','DONE')),
  event_date     date,
  is_estimated   boolean NOT NULL DEFAULT false,
  detail         text,
  raw_text       text NOT NULL,
  source_file_id bigint REFERENCES etl.source_file(file_id),
  source_cell_ref text,
  CHECK (event_date IS NULL OR event_date BETWEEN DATE '2020-01-01' AND DATE '2035-12-31')
);
CREATE INDEX ON core.milestone_event(style_order_id, milestone_code, round_no);

CREATE TABLE core.production_snapshot (
  snapshot_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id       int  NOT NULL REFERENCES core.style_order(style_order_id),
  as_of_date           date NOT NULL,
  daily_output         int CHECK (daily_output >= 0),
  output_qty           int CHECK (output_qty >= 0),
  inspected_qty        int CHECK (inspected_qty >= 0),
  shipped_qty_reported int CHECK (shipped_qty_reported >= 0),
  source_file_id       bigint NOT NULL REFERENCES etl.source_file(file_id),
  UNIQUE (style_order_id, as_of_date, source_file_id)
);

CREATE TABLE core.production_plan (
  plan_id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id     int  NOT NULL REFERENCES core.style_order(style_order_id),
  as_of_date         date NOT NULL,
  cutting_plan       date,
  input_plan         date,
  sewing_finish_plan date,
  exfact_est         date,
  etd_est            date,
  eta_est            date,
  plan_raw           text,
  source_file_id     bigint NOT NULL REFERENCES etl.source_file(file_id),
  UNIQUE (style_order_id, as_of_date, source_file_id)
);

-- ---------------------------------------------------------------------
-- CORE: shipping & samples
-- ---------------------------------------------------------------------
CREATE TABLE core.shipment (
  shipment_id  int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id    smallint NOT NULL REFERENCES core.season(season_id),
  etd          date,
  eta          date,
  mode_code    varchar(6) REFERENCES core.shipping_mode(mode_code),
  label_raw    text NOT NULL,
  needs_review boolean NOT NULL DEFAULT false,
  CHECK (eta IS NULL OR etd IS NULL OR eta >= etd OR needs_review)
);
CREATE UNIQUE INDEX ux_shipment_key ON core.shipment(season_id, etd, eta, coalesce(mode_code,'?'));
CREATE INDEX ON core.shipment(etd);

CREATE TABLE core.shipment_line (
  shipment_line_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  shipment_id      int NOT NULL REFERENCES core.shipment(shipment_id),
  soc_id           int NOT NULL REFERENCES core.style_order_color(soc_id),
  size_code        varchar(10) NOT NULL REFERENCES core.size(size_code),
  factory_id       int REFERENCES core.factory(factory_id),
  qty              int NOT NULL CHECK (qty > 0),     -- (P) negative adjustments seen? none observed
  source_file_id   bigint REFERENCES etl.source_file(file_id),
  source_cell_ref  text,
  UNIQUE (shipment_id, soc_id, size_code)
);
CREATE INDEX ON core.shipment_line(soc_id);

CREATE TABLE core.sample_dispatch (
  sample_dispatch_id int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id     int  NOT NULL REFERENCES core.style_order(style_order_id),
  sample_type        varchar(12) NOT NULL CHECK (sample_type IN ('SHIPPING','PHOTO','FPP','INLINE','TOP','REF','OTHER')),
  dispatch_dates     date[],
  destination        text,                          -- (P) KOREA / SMPL ROOM
  label_raw          text NOT NULL,
  source_file_id     bigint REFERENCES etl.source_file(file_id)
);
CREATE INDEX ON core.sample_dispatch(style_order_id);

CREATE TABLE core.sample_dispatch_line (
  sample_dispatch_id int NOT NULL REFERENCES core.sample_dispatch(sample_dispatch_id) ON DELETE CASCADE,
  soc_id             int NOT NULL REFERENCES core.style_order_color(soc_id),
  size_code          varchar(10) NOT NULL REFERENCES core.size(size_code),
  qty                int NOT NULL CHECK (qty > 0),
  PRIMARY KEY (sample_dispatch_id, soc_id, size_code)
);

-- ---------------------------------------------------------------------
-- CORE: materials
-- ---------------------------------------------------------------------
CREATE TABLE core.fabric (
  fabric_id    int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  supplier_id  int REFERENCES core.supplier(supplier_id),
  fabric_code  text,
  description  text NOT NULL,
  construction varchar(6) CHECK (construction IN ('WOVEN','KNIT')),   -- 우븐 / 다이마루
  composition  text,                                                 -- 'P95 PU5'
  width_inch   numeric(5,1),
  width_raw    text,
  UNIQUE (supplier_id, description)
);

CREATE TABLE core.style_fabric (                     -- snapshot per as_of_date
  style_fabric_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id      int  NOT NULL REFERENCES core.style_order(style_order_id),
  garment_color_id    int  REFERENCES core.color(color_id),
  fabric_color_raw    text,
  part_code           varchar(20),                    -- BODY, CONTRAST_1, LINING_1, POCKETING, PADDING_1 ...
  part_raw            text NOT NULL,                  -- 몸판, 배색1, 안감, 주머니감, 충전재 ...
  fabric_id           int  REFERENCES core.fabric(fabric_id),
  origin_country      char(2),                        -- KR, CN, VN
  unit_price          numeric(12,4),
  unit_price_raw      text,
  currency            char(3),                        -- (P) not present in source; inferred KRW for KR, USD for CN/VN?
  consumption_order   numeric(6,3),
  consumption_fpp     numeric(6,3),
  consumption_factory numeric(6,3),
  po_date             date,
  po_qty_yd           numeric(10,2),
  color_cfm_date      date,
  bt_submit_date      date,
  bt_reject_date      date,
  bt_cfm_date         date,
  exp_ship_date       date,
  etd                 date,
  eta                 date,
  shipped_yd          numeric(10,2),
  as_of_date          date NOT NULL,
  source_file_id      bigint NOT NULL REFERENCES etl.source_file(file_id),
  source_row          int NOT NULL,
  UNIQUE (source_file_id, as_of_date, source_row)
);
CREATE INDEX ON core.style_fabric(style_order_id, as_of_date);
CREATE INDEX ON core.style_fabric(fabric_id);

CREATE TABLE core.fabric_shipment (
  fabric_shipment_id int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  etd          date,
  mode_code    varchar(6) REFERENCES core.shipping_mode(mode_code),
  vessel_label text NOT NULL,                       -- 'ETD 0615 VESSEL KYLIN'
  suppliers_raw text,
  UNIQUE (etd, vessel_label)
);

CREATE TABLE core.fabric_shipment_line (
  fabric_shipment_id int    NOT NULL REFERENCES core.fabric_shipment(fabric_shipment_id),
  style_fabric_id    bigint NOT NULL REFERENCES core.style_fabric(style_fabric_id) ON DELETE CASCADE,
  qty_yd             numeric(10,2) NOT NULL,
  PRIMARY KEY (fabric_shipment_id, style_fabric_id)
);

-- ---------------------------------------------------------------------
-- CORE: commercial (PROVISIONAL — no data observed yet)
-- ---------------------------------------------------------------------
CREATE TABLE core.factory_price (                    -- (P)
  price_id       int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id int NOT NULL REFERENCES core.style_order(style_order_id),
  factory_id     int REFERENCES core.factory(factory_id),
  price_type     varchar(8) NOT NULL CHECK (price_type IN ('TARGET','FIXED','FINAL')),
  cmph           numeric(10,4),
  washing        numeric(10,4),
  embo           numeric(10,4),
  others         numeric(10,4),
  currency       char(3) NOT NULL DEFAULT 'USD',      -- (P)
  effective_date date,
  UNIQUE (style_order_id, price_type, effective_date)
);

CREATE TABLE core.trade_document (                   -- (P)
  doc_id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  style_order_id int NOT NULL REFERENCES core.style_order(style_order_id),
  doc_type       varchar(10) NOT NULL CHECK (doc_type IN ('PO_KR','PO_CN','CO','HS_CODE','INVOICE','BL')),
  doc_no         text,
  sent_date      date
);

-- ---------------------------------------------------------------------
-- MART: computed views (no stored totals in core)
-- ---------------------------------------------------------------------
CREATE VIEW mart.v_style_order_summary AS
SELECT so.style_order_id, se.season_code, c.collection_code, s.style_no, so.order_no,
       f.name_canonical AS current_factory, so.status_code, so.etd_vn, so.rdd_kr,
       coalesce(oq.order_qty,0)  AS order_qty,
       coalesce(sh.shipped,0)    AS shipped_qty,
       coalesce(sm.sample_qty,0) AS sample_qty,
       coalesce(sh.shipped,0) + coalesce(sm.sample_qty,0) - coalesce(oq.order_qty,0) AS balance_incl_samples
FROM core.style_order so
JOIN core.season se      ON se.season_id = so.season_id
JOIN core.collection c   ON c.collection_id = so.collection_id
JOIN core.style s        ON s.style_id = so.style_id
LEFT JOIN core.factory_assignment fa ON fa.style_order_id = so.style_order_id AND fa.valid_to IS NULL
LEFT JOIN core.factory f ON f.factory_id = fa.factory_id
LEFT JOIN (SELECT style_order_id, sum(order_qty) order_qty FROM core.style_order_color GROUP BY 1) oq
       ON oq.style_order_id = so.style_order_id
LEFT JOIN (SELECT soc.style_order_id, sum(sl.qty) shipped
           FROM core.shipment_line sl JOIN core.style_order_color soc USING (soc_id) GROUP BY 1) sh
       ON sh.style_order_id = so.style_order_id
LEFT JOIN (SELECT sd.style_order_id, sum(l.qty) sample_qty
           FROM core.sample_dispatch sd JOIN core.sample_dispatch_line l USING (sample_dispatch_id) GROUP BY 1) sm
       ON sm.style_order_id = so.style_order_id;

CREATE VIEW mart.v_reconciliation_reported_vs_computed AS
SELECT v.style_no, v.season_code, ps.as_of_date, ps.source_file_id,
       ps.shipped_qty_reported, v.shipped_qty AS shipped_computed, v.sample_qty,
       ps.shipped_qty_reported - v.shipped_qty AS diff_excl_samples,
       ps.shipped_qty_reported - (v.shipped_qty + v.sample_qty) AS diff_incl_samples
FROM core.production_snapshot ps
JOIN mart.v_style_order_summary v ON v.style_order_id = ps.style_order_id;
