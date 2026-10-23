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
  family VARCHAR,    -- version family, e.g. 'DHG|8 SECONDS' (NULL = one family per parser + season)
  parse_key VARCHAR, from_cache BOOLEAN, parse_seconds DOUBLE,   -- lake key; rows read back from the lake
  template_fp VARCHAR, template_sheet VARCHAR, template_labels VARCHAR);   -- Excel header fingerprint (H-04)

-- Every file under the source roots (H-01). change: NEW | CHANGED | UNCHANGED | REMOVED vs the previous build.
CREATE TABLE etl.manifest (
  path VARCHAR, rel VARCHAR, size_bytes BIGINT, mtime TIMESTAMP, sha256 VARCHAR, change VARCHAR, first_seen VARCHAR);

-- One row per build (history kept in <lake>/_catalog/runs.parquet).
CREATE TABLE etl.run (
  run_id VARCHAR, started_at TIMESTAMP, seconds DOUBLE, n_files INTEGER, n_new INTEGER, n_changed INTEGER,
  n_removed INTEGER, n_hashed INTEGER, n_parsed INTEGER, n_cached INTEGER, n_failed INTEGER, n_quarantined INTEGER,
  workers INTEGER, scan_seconds DOUBLE, parse_seconds DOUBLE, load_seconds DOUBLE, sql_seconds DOUBLE,
  peak_rss_mb DOUBLE);

-- Files that were not loaded and need a person (H-03/H-04): reason PARSE_FAILED | PARSE_TIMEOUT | PARSE_CRASHED |
-- UNKNOWN_TEMPLATE | MISSING_TOOL; labels = header labels of an unknown template. Also written to build/quarantine.csv.
CREATE TABLE etl.quarantine (
  file_id INTEGER, file_name VARCHAR, rel_path VARCHAR, parser VARCHAR, status VARCHAR, reason VARCHAR,
  message VARCHAR, template_fp VARCHAR, labels VARCHAR, action VARCHAR);

-- Scanned PDF pages waiting for OCR (H-08): `python -m kops_dw ocr` processes the PENDING ones.
CREATE TABLE etl.ocr_queue (
  file_id INTEGER, file_name VARCHAR, path VARCHAR, sha256 VARCHAR, pages VARCHAR, status VARCHAR);

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
  in_reply_to VARCHAR, source_page INTEGER, llm_category VARCHAR, summary_vi VARCHAR, summary_ko VARCHAR,
  folder VARCHAR,    -- mailbox folder (.pst) or Gmail labels (.mbox)
  text_source VARCHAR);   -- PDF exports: 'text' (text layer) or 'ocr' (scanned page read by tesseract, H-08)

-- SHIPPING SCHEDULE (CHALLENGER export plan per style; ingest/shipping_schedule.py)
CREATE TABLE raw.shipping_schedule (
  file_id INTEGER, sheet VARCHAR, row_no INTEGER, block_no INTEGER, status VARCHAR, season VARCHAR, as_of DATE,
  style_no VARCHAR, type VARCHAR, item VARCHAR, input_plan DATE, input_plan_txt VARCHAR, sewing_finish_plan DATE,
  sewing_finish_plan_txt VARCHAR, order_qty INTEGER, etd_vn DATE, rdd DATE, shipped_qty INTEGER, ship_plan_qty INTEGER,
  bal_qty INTEGER, pcs_per_box DOUBLE, box_qty DOUBLE, remark VARCHAR, remark2 VARCHAR, factory_raw VARCHAR,
  factory_code VARCHAR, factory_moved BOOLEAN, fixed_exfact DATE, fixed_exfact_txt VARCHAR, fixed_etd DATE,
  fixed_etd_txt VARCHAR, fixed_eta DATE, fixed_eta_txt VARCHAR, ship_mode VARCHAR);
-- Buyer's own order status PDF (DHG '생산계획표 · 오더 현황표'; ingest/buyer_order_status.py): comparison only.
CREATE TABLE raw.buyer_order_status (
  file_id INTEGER, page INTEGER, line_no INTEGER, brand VARCHAR, season VARCHAR, printed_on DATE, file_no VARCHAR,
  style_no VARCHAR, item VARCHAR, factory_raw VARCHAR, factory_code VARCHAR, qty INTEGER, cut_plan DATE,
  input_plan DATE, finish_plan DATE, etd DATE, eta DATE, rdd DATE, margin_days INTEGER, status VARCHAR);
-- Daily production report (D-02 / M1-02): size rows of every day sheet; GRAND TOTAL rows kept to check them
CREATE TABLE raw.daily_prod_row (
  file_id INTEGER, customer VARCHAR, brand VARCHAR, season VARCHAR, factory_code VARCHAR, report_date DATE, sheet VARCHAR,
  sheet_hidden BOOLEAN, row_no INTEGER, style_raw VARCHAR, style_variant VARCHAR, style_note VARCHAR, line_no VARCHAR,
  workers INTEGER, etd DATE, rdd DATE, color VARCHAR, size_code VARCHAR, order_qty INTEGER, cut_today INTEGER,
  cut_ttl INTEGER, print_send_today INTEGER, print_send_ttl INTEGER, print_return_today INTEGER, print_return_ttl INTEGER,
  input_today INTEGER, input_ttl INTEGER, output_today INTEGER, output_ttl INTEGER);
CREATE TABLE raw.daily_prod_total (
  file_id INTEGER, sheet VARCHAR, report_date DATE, row_no INTEGER, factory_code VARCHAR, order_qty INTEGER, output_ttl INTEGER);
-- KLMAS inspection tracker (D-02 / M1-06): passed qty per style x piece x colour x day; factory x day totals A/C/D/F.
-- Inspector names (row G) are never loaded.
CREATE TABLE raw.inspection_cell (
  file_id INTEGER, sheet VARCHAR, factory_code VARCHAR, is_old_round BOOLEAN, style_no VARCHAR, piece VARCHAR,
  color VARCHAR, inspect_date DATE, passed_qty INTEGER, order_qty INTEGER, row_no INTEGER, col_no INTEGER);
CREATE TABLE raw.inspection_day (
  file_id INTEGER, sheet VARCHAR, factory_code VARCHAR, is_old_round BOOLEAN, inspect_date DATE, measure VARCHAR,
  value INTEGER, row_no INTEGER, col_no INTEGER);
CREATE TABLE stg.inspection_remark (
  file_id INTEGER, sheet VARCHAR, factory_code VARCHAR, style_no VARCHAR, piece VARCHAR, color VARCHAR, remark VARCHAR,
  request_etd DATE, ttl_pass INTEGER, row_no INTEGER);
-- Third-party inspections (D-02 / M1-12): INPUT DATA.xlsx, one row per inspection, one per defect code; code list
CREATE TABLE raw.qc_inspection (
  file_id INTEGER, inspection_no INTEGER, row_no INTEGER, location VARCHAR, style_no VARCHAR, po_color VARCHAR,
  ship_to VARCHAR, round_no INTEGER, item VARCHAR, brand VARCHAR, vendor VARCHAR, factory_raw VARCHAR, inspect_date DATE,
  pre_final VARCHAR, order_qty INTEGER, inspected_qty INTEGER, pass_qty INTEGER, defect_qty INTEGER, remark VARCHAR,
  result VARCHAR);
CREATE TABLE raw.qc_defect (file_id INTEGER, inspection_no INTEGER, row_no INTEGER, code VARCHAR, minor INTEGER, major INTEGER);
CREATE TABLE raw.defect_code (file_id INTEGER, code VARCHAR, name_ko VARCHAR, code_group VARCHAR, row_no INTEGER);
-- Milestone / shipment named by an email subject (N-03, milestones.py; rule-based hints, not facts).
CREATE TABLE stg.email_event (
  file_id INTEGER, msg_key VARCHAR, milestone VARCHAR, sent_at TIMESTAMP, factory VARCHAR, style_candidates VARCHAR,
  direction VARCHAR, etd_old DATE, etd_new DATE, eta DATE, ship_mode VARCHAR, load_type VARCHAR, customer VARCHAR,
  origin VARCHAR, booking VARCHAR, forwarder VARCHAR, is_delay BOOLEAN);
-- Documents recorded from their name only, never opened (N-02, docmeta.py): work sheets, comments, CAD patterns.
CREATE TABLE stg.document (
  file_id INTEGER, path_hash VARCHAR, file_name VARCHAR, ext VARCHAR, size_bytes BIGINT, sha256 VARCHAR,
  customer VARCHAR, style_candidates VARCHAR, factory VARCHAR, season VARCHAR, stage VARCHAR, doc_kind VARCHAR,
  doc_date DATE, meta_source VARCHAR);
-- Attachments listed in a message (.mhtml: names only, the files are not in the page). Big-file links expire.
CREATE TABLE raw.email_attachment (
  file_id INTEGER, msg_key VARCHAR, part_no INTEGER, file_name VARCHAR, size_text VARCHAR, size_bytes BIGINT,
  is_link BOOLEAN, expires_on DATE);
-- Mailbox messages not loaded as business email (H-06), kept to audit the rules: folder | date-range | automated:*
CREATE TABLE raw.email_filtered (
  file_id INTEGER, msg_key VARCHAR, message_id VARCHAR, sent_at TIMESTAMP, sender_email VARCHAR, subject VARCHAR,
  folder VARCHAR, reason VARCHAR);

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
  actual_eta DATE, remark VARCHAR,
  due_exf DATE,            -- '공장 출고일자 / EX-FACT' due column (some layouts)
  due_etd_rule VARCHAR, due_eta_rule VARCHAR, bal_rule VARCHAR,   -- the file's own rules: 'RDD-14', 'RDD-3', 'ETA+2' ...
  header_row INTEGER);

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
-- Linked model reference data (D-01): unconfirmed factory aliases, customer names, e-mail domain parties (local file)
CREATE TABLE stg.factory_alias_review (alias_key VARCHAR, factory_code VARCHAR, confidence VARCHAR, question VARCHAR);
CREATE TABLE stg.customer_ref (customer VARCHAR, name VARCHAR);
CREATE TABLE stg.party_domain (domain VARCHAR, party_type VARCHAR, ref_code VARCHAR);
CREATE TABLE stg.free_mail (domain VARCHAR);
CREATE TABLE stg.style_alias (alias_style VARCHAR, style_no VARCHAR, confirmed BOOLEAN);
CREATE TABLE stg.rule (rule_key VARCHAR, rule_value VARCHAR);
CREATE TABLE stg.requirement_coverage (
  req_no INTEGER, mvp_status VARCHAR, where_in_mvp VARCHAR, next_step VARCHAR);
