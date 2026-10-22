-- KOPS DW MVP - landing layers.
-- etl : source registry + data issues (lineage for every number)
-- raw : source content as close to the original as possible (one table per source template)
-- stg : structured facts extracted by the Python parsers (notes, emails, meeting tables)
CREATE SCHEMA IF NOT EXISTS etl;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE TABLE etl.source_file (
  file_id INTEGER PRIMARY KEY, file_name VARCHAR, rel_path VARCHAR, source_type VARCHAR, parser VARCHAR,
  season VARCHAR, file_date DATE, report_date DATE, sha256 VARCHAR, size_bytes BIGINT, is_sample BOOLEAN,
  status VARCHAR, is_current BOOLEAN, rows_loaded INTEGER, message VARCHAR, loaded_at TIMESTAMP,
  family VARCHAR);   -- version family, e.g. 'DHG|8 SECONDS' (NULL = one family per parser + season)

CREATE TABLE etl.data_issue (
  file_id INTEGER, severity VARCHAR, code VARCHAR, entity VARCHAR, message VARCHAR, location VARCHAR);

CREATE TABLE raw.order_recap_style (
  file_id INTEGER, season VARCHAR, row_no INTEGER, order_no VARCHAR, brand VARCHAR, style_no VARCHAR,
  factory_raw VARCHAR, factory_note VARCHAR, status_fill VARCHAR, status_label VARCHAR, grand_ttl_reported INTEGER,
  etd_raw VARCHAR, etd_vn DATE, rdd_kr DATE, line_raw VARCHAR, collection_raw VARCHAR, description_en VARCHAR,
  name_kr VARCHAR, main_fabric VARCHAR, progress_notes VARCHAR, report_date DATE);

CREATE TABLE raw.order_recap_color (
  file_id INTEGER, season VARCHAR, row_no INTEGER, style_no VARCHAR, color_raw VARCHAR, color_note VARCHAR,
  change_note VARCHAR, qty_raw VARCHAR, order_qty INTEGER, is_active BOOLEAN);

CREATE TABLE raw.shipment_block (
  file_id INTEGER, sheet VARCHAR, factory VARCHAR, block_no INTEGER, style_no_raw VARCHAR, title_row INTEGER,
  title_col INTEGER, has_data BOOLEAN, order_ttl_reported INTEGER, shipped_smpl_reported INTEGER,
  smpl_reported INTEGER, order_ttl_computed INTEGER, shipped_smpl_computed INTEGER);

CREATE TABLE raw.shipment_cell (
  file_id INTEGER, sheet VARCHAR, factory VARCHAR, block_no INTEGER, style_no_raw VARCHAR, section VARCHAR,
  label VARCHAR, color_raw VARCHAR, size_code VARCHAR, qty INTEGER, row_no INTEGER, col_no INTEGER,
  lot_etd DATE, lot_eta DATE, ship_mode VARCHAR);

CREATE TABLE raw.production_status (
  file_id INTEGER, season VARCHAR, row_no INTEGER, as_of DATE, order_no VARCHAR, mode VARCHAR, type VARCHAR,
  style_no VARCHAR, items VARCHAR, factory_raw VARCHAR, etd_vn DATE, etd_vn_txt VARCHAR, rdd DATE, rdd_txt VARCHAR,
  fpp_cfmd DATE, fpp_cfmd_txt VARCHAR, inline_raw VARCHAR, top_smpl DATE, top_smpl_txt VARCHAR,
  order_qty INTEGER, one_day INTEGER, output_qty INTEGER, inspected_qty INTEGER, shipped_qty INTEGER,
  logo_status VARCHAR, mtr_eta_raw VARCHAR, cutting_plan DATE, cutting_plan_txt VARCHAR, input_plan DATE,
  input_plan_txt VARCHAR, sewing_finish_plan DATE, sewing_finish_plan_txt VARCHAR, exfact_est DATE,
  exfact_est_txt VARCHAR, etd_est DATE, etd_est_txt VARCHAR, eta_est DATE, eta_est_txt VARCHAR);

CREATE TABLE raw.production_status_total (
  file_id INTEGER, row_no INTEGER, label VARCHAR, factory_raw VARCHAR, order_qty INTEGER, output_qty INTEGER,
  inspected_qty INTEGER, shipped_qty INTEGER);

CREATE TABLE raw.doc_block (
  file_id INTEGER, doc_title VARCHAR, seq INTEGER, section VARCHAR, kind VARCHAR, text VARCHAR, table_json VARCHAR);

-- One row per message found in a file (a PDF export can hold a whole thread). msg_key = same message across files.
CREATE TABLE raw.email (
  file_id INTEGER, message_id VARCHAR, msg_key VARCHAR, thread_key VARCHAR, channel VARCHAR, part_no INTEGER,
  is_quoted BOOLEAN, sent_at TIMESTAMP, sender VARCHAR, sender_email VARCHAR, recipients VARCHAR, cc VARCHAR,
  subject VARCHAR, lang VARCHAR, categories VARCHAR, attachments VARCHAR, body VARCHAR, is_sample BOOLEAN,
  in_reply_to VARCHAR, source_page INTEGER, llm_category VARCHAR, summary_vi VARCHAR, summary_ko VARCHAR);

-- ORDER RECAP of customers other than CHALLENGER (header-driven parser, one row per style block)
CREATE TABLE raw.order_line_ext (
  file_id INTEGER, customer VARCHAR, brand VARCHAR, season VARCHAR, sheet VARCHAR, row_no INTEGER, order_no VARCHAR,
  style_no VARCHAR, style_raw VARCHAR, style_aliases VARCHAR, file_no VARCHAR, factory_code VARCHAR,
  factory_raw VARCHAR, order_qty INTEGER, qty_raw VARCHAR, qty_source VARCHAR, etd DATE, etd_raw VARCHAR, rdd DATE,
  rdd_raw VARCHAR, etd_rule VARCHAR, status_fill VARCHAR, status_label VARCHAR, is_active BOOLEAN, report_date DATE);

-- PRODUCTION PLAN: one sheet per factory, one row per style
CREATE TABLE raw.production_plan (
  file_id INTEGER, customer VARCHAR, brand VARCHAR, season VARCHAR, factory_code VARCHAR, factory_raw VARCHAR,
  sheet VARCHAR, row_no INTEGER, as_of DATE, style_no VARCHAR, file_no VARCHAR, item VARCHAR, qty INTEGER,
  line_worker VARCHAR, daily_target DOUBLE, work_days DOUBLE, fabric_etd DATE, accs_etd DATE, accs_eta_factory DATE,
  cut_plan DATE, input_plan DATE, finish_plan DATE, exf_plan DATE, etd_plan DATE, eta_plan DATE, due_etd DATE,
  due_eta DATE, rdd DATE, bal_days INTEGER, bal_offset INTEGER, bal_calc INTEGER, actual_exf DATE, actual_etd DATE,
  actual_eta DATE, remark VARCHAR);

CREATE TABLE stg.qty_change (
  file_id INTEGER, season VARCHAR, style_no VARCHAR, color_raw VARCHAR, change_date DATE, kind VARCHAR,
  qty_before INTEGER, qty_after INTEGER, note_raw VARCHAR, location VARCHAR);

CREATE TABLE stg.factory_event (
  file_id INTEGER, season VARCHAR, style_no VARCHAR, event_date DATE, action VARCHAR, factory_hint VARCHAR,
  note_raw VARCHAR, location VARCHAR);

CREATE TABLE stg.meeting (file_id INTEGER, title VARCHAR, meeting_date VARCHAR, location VARCHAR);
CREATE TABLE stg.attendee (file_id INTEGER, company VARCHAR, name VARCHAR, title VARCHAR, role VARCHAR);
CREATE TABLE stg.requirement (
  file_id INTEGER, req_no INTEGER, req_group VARCHAR, text_kr VARCHAR, text_vi VARCHAR, raised_by VARCHAR);
CREATE TABLE stg.action_item (file_id INTEGER, owner VARCHAR, item_kr VARCHAR, item_vi VARCHAR, due VARCHAR);
CREATE TABLE stg.decision (
  file_id INTEGER, no INTEGER, topic VARCHAR, text VARCHAR, raised_by VARCHAR, section VARCHAR);

CREATE TABLE stg.email_change (
  file_id INTEGER, message_id VARCHAR, style_no VARCHAR, change_type VARCHAR, value_text VARCHAR, pct INTEGER,
  qty_after INTEGER, new_date DATE, color_from VARCHAR, color_to VARCHAR, confidence VARCHAR, evidence VARCHAR,
  review_status VARCHAR, msg_key VARCHAR);

-- Reference data maintained in code (config.py) and loaded each build.
CREATE TABLE stg.factory_alias (alias_key VARCHAR, factory_code VARCHAR);
CREATE TABLE stg.style_alias (alias_style VARCHAR, style_no VARCHAR, confirmed BOOLEAN);
CREATE TABLE stg.rule (rule_key VARCHAR, rule_value VARCHAR);
CREATE TABLE stg.requirement_coverage (
  req_no INTEGER, mvp_status VARCHAR, where_in_mvp VARCHAR, next_step VARCHAR);
