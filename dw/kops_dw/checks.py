"""Golden-number regression tests (GUIDELINES.md §7) + structural checks on the built DW.

Golden values are only asserted when the matching source file is loaded, so the suite also runs on a
partial raw-docs folder (missing sources are reported as SKIP).

Golden numbers belong to one version of a file (N-05). A golden check names the files it was measured on
(pins): it runs on a snapshot DB built from the lake in which those files are the current version of their
report family (pipeline.build(pins=...); nothing is parsed again). A newer version therefore never turns an old
golden red; the new version gets its own golden, taken from the total cells of that file (cited in the name)."""
from __future__ import annotations

import duckdb

from . import config

# Files current when the golden numbers of GUIDELINES §7 were set (checks green on 22/10/2026).
GOLDEN_2210 = ("261015 MJ) 26FW CHALLENGER ORDER RECAP", "261015 MJ) 27SS CHALLENGER ORDER RECAP",
               "261014R2 MJ) 26FW CHALLENGER ALL STYLES SHIPMENT STATUS",
               "261012 HUONG) 26FW CLGR PRODUCTION AND SHIPPING STATUS", "261016 MJ_DHG BPK -ALL 27SS PRODUCTION PLAN",
               "261021 DHG) BPK 27SS ORDER RECAP", "261009. DUNG) DHG 8S 26FW", "261019 HANG) 27SS MIZUNO",
               "261021 MJ) 27SS JBEE", "261015 MJ) 27SS KOFA")
# Versions received 22-23/10/2026 (new-docs).
GOLDEN_2310 = ("261022 MJ) 26FW CHALLENGER ORDER RECAP", "261022 MJ) 27SS CHALLENGER ORDER RECAP",
               "261021 HUONG) 26FW CLGR PRODUCTION AND SHIPPING STATUS")
_R26, _R27 = ("file", GOLDEN_2210[0]), ("file", GOLDEN_2210[1])
_SH, _PS = ("file", GOLDEN_2210[2]), ("file", GOLDEN_2210[3])
_CLGR = "f.is_current AND f.family = 'CHALLENGER'"     # MIZUNO status files are current too (own family)

CHECKS = [
    # (name, required parser+season / ("file", prefix), sql returning one value, expected[, pinned files])
    ("ORDER RECAP 26FW: style blocks", _R26,
     "SELECT count(*) FROM core.style_order WHERE season='26FW'", 113, GOLDEN_2210),
    ("ORDER RECAP 26FW: active styles", _R26,
     "SELECT count(*) FROM core.style_order WHERE season='26FW' AND is_active", 110, GOLDEN_2210),
    ("ORDER RECAP 26FW: order qty (sum of colours)", _R26,
     "SELECT sum(order_qty) FROM core.style_order WHERE season='26FW' AND is_active", 62131, GOLDEN_2210),
    ("ORDER RECAP 27SS: style blocks", _R27,
     "SELECT count(*) FROM core.style_order WHERE season='27SS'", 143, GOLDEN_2210),
    ("ORDER RECAP 27SS: active styles", _R27,
     "SELECT count(*) FROM core.style_order WHERE season='27SS' AND is_active", 137, GOLDEN_2210),
    ("ORDER RECAP 27SS: order qty (sum of colours)", _R27,
     "SELECT sum(order_qty) FROM core.style_order WHERE season='27SS' AND is_active", 87940, GOLDEN_2210),
    ("Shipment Status: blocks", _SH,
     f"SELECT count(*) FROM raw.shipment_block b JOIN etl.source_file f USING (file_id) WHERE {_CLGR}", 144, GOLDEN_2210),
    ("Shipment Status: blocks with data", _SH,
     f"SELECT count(*) FROM raw.shipment_block b JOIN etl.source_file f USING (file_id) WHERE {_CLGR} AND has_data", 104,
     GOLDEN_2210),
    ("Shipment Status: blocks whose recomputed totals match the file", _SH,
     f"""SELECT count(*) FROM raw.shipment_block b JOIN etl.source_file f USING (file_id) WHERE {_CLGR} AND has_data
        AND order_ttl_reported IS NOT DISTINCT FROM order_ttl_computed
        AND shipped_smpl_reported IS NOT DISTINCT FROM shipped_smpl_computed""", 104, GOLDEN_2210),
    ("Production Status: styles", _PS,
     "SELECT count(*) FROM core.production_snapshot WHERE season='26FW'", 110, GOLDEN_2210),
    ("Production Status: order qty recomputed (file shows 106,681)", _PS,
     "SELECT sum(order_qty_reported) FROM core.production_snapshot WHERE season='26FW'", 62357, GOLDEN_2210),
    ("Production Status: broken grand total is flagged", _PS,
     """SELECT count(*) FROM etl.data_issue i JOIN etl.source_file f USING (file_id) WHERE f.is_current
        AND i.code='TOTAL_MISMATCH' AND i.entity='G.TTL' AND i.message LIKE '%106681%'""", 1, GOLDEN_2210),
    ("Cross-file: styles with order qty mismatch", _SH,
     "SELECT count(*) FROM mart.reconciliation WHERE season='26FW' AND mismatch LIKE 'ORDER:%'", 4, GOLDEN_2210),
    ("Factory history CHF3MJK6301 (NATEXCO -> HA HIEU -> MTT)", _R26,
     """SELECT string_agg(coalesce(factory_code, factory_hint), '>' ORDER BY event_date) FROM core.factory_event
        WHERE style_no='CHF3MJK6301'""", "NATEXCO>HA HIEU>MTT", GOLDEN_2210),
    ("Alert W33 CHF4MPT6444 projected ~49 days late", _PS,
     "SELECT days_late FROM mart.style_360 WHERE style_no='CHF4MPT6444'", 49, GOLDEN_2210),
    # Prototype showed 79%; the DW also matches the 3 aliased style codes (Q05), giving 79.6%.
    ("26FW on-time shipment rate (first lot <= ETD + 7)", _SH,
     "SELECT ontime_pct FROM mart.season_kpi WHERE season='26FW'", 79.6, GOLDEN_2210),
    # ---- golden of the versions received 22-23/10, from the file's own total cells (N-05) ----
    ("ORDER RECAP 261022 26FW: active styles / qty = 'ORDER RECAP'!M631 'G.TTL(26FW)' / K594 'GRAND TOTAL'",
     ("file", GOLDEN_2310[0]),
     "SELECT count(*) || ' / ' || sum(order_qty) FROM core.style_order WHERE season='26FW' AND is_active", "110 / 62131",
     GOLDEN_2310),
    ("ORDER RECAP 261022 27SS: qty = 'ORDER RECAP'!K731 'GRAND TOTAL'", ("file", GOLDEN_2310[1]),
     "SELECT sum(order_qty) FROM core.style_order WHERE season='27SS' AND is_active", 87940, GOLDEN_2310),
    ("PRODUCTION STATUS 261021: styles = '26FW-CLGR'!B122 'G.TTL (TTL 110 STYLES)'", ("file", GOLDEN_2310[2]),
     "SELECT count(*) FROM core.production_snapshot WHERE season='26FW'", 110, GOLDEN_2310),
    ("PRODUCTION STATUS 261021: factory subtotals that add up = L34 / L48 / L121", ("file", GOLDEN_2310[2]),
     """SELECT string_agg(factory_code || ' ' || n || ' / ' || q, ', ' ORDER BY factory_code) FROM (
          SELECT factory_code, count(*) AS n, sum(order_qty_reported) AS q FROM core.production_snapshot
          WHERE season='26FW' AND factory_code IN ('DONG MY', 'MTT', 'TAN BINH MINH') GROUP BY factory_code)""",
     "DONG MY 28 / 17790, MTT 13 / 5620, TAN BINH MINH 37 / 19770", GOLDEN_2310),
    ("PRODUCTION STATUS 261021: grand total L122 (106,681) flagged / recomputed qty", ("file", GOLDEN_2310[2]),
     """SELECT (SELECT count(*) FROM etl.data_issue i JOIN etl.source_file f USING (file_id) WHERE f.is_current
                 AND i.code='TOTAL_MISMATCH' AND i.entity='G.TTL' AND i.message LIKE '%106681%') || ' / ' ||
               (SELECT sum(order_qty_reported) FROM core.production_snapshot WHERE season='26FW')""", "1 / 62357",
     GOLDEN_2310),
    # structural rules
    ("No email change is applied without review", None,
     "SELECT count(*) FROM core.change_proposal WHERE review_status <> 'PENDING_REVIEW'", 0),
    ("Every core style row traces back to a source file", None,
     "SELECT count(*) FROM core.style_order o LEFT JOIN etl.source_file f USING (file_id) WHERE f.file_id IS NULL", 0),
    ("Prompt-injection sample did not alter data", None,
     """SELECT count(*) FROM core.change_proposal WHERE upper(evidence) LIKE '%IGNORE PREVIOUS%'
        OR (change_type IN ('QTY', 'QTY_PCT') AND proposed_qty = 0)""", 0),
    # ---- other customers (header-driven ORDER RECAP), production plan, history ----
    ("8 SECONDS 26FW: styles / qty", ("file", "261009. DUNG) DHG 8S 26FW"),
     "SELECT count(*) || ' / ' || sum(order_qty) FROM core.order_line_ext WHERE customer='DHG' AND brand='8 SECONDS' AND season='26FW'",
     "59 / 119392", GOLDEN_2210),
    ("MIZUNO 27SS: styles / qty", ("file", "261019 HANG) 27SS MIZUNO"),
     "SELECT count(*) || ' / ' || sum(order_qty) FROM core.order_line_ext WHERE customer='DKM' AND season='27SS'", "26 / 43909", GOLDEN_2210),
    ("JBEE 27SS: qty", ("file", "261021 MJ) 27SS JBEE"),
     "SELECT sum(order_qty) FROM core.order_line_ext WHERE customer='JBEE' AND season='27SS' AND is_active", 67100, GOLDEN_2210),
    ("KOFA 27SS: active qty (cancelled BLACKYAK blocks excluded)", ("file", "261015 MJ) 27SS KOFA"),
     "SELECT sum(order_qty) FROM core.order_line_ext WHERE customer='KOFA' AND is_active", 4000, GOLDEN_2210),
    ("Beanpole Kids 27SS current version = 261021: blocks / active / qty", ("file", "261021 DHG) BPK 27SS"),
     """SELECT count(*) || ' / ' || count(*) FILTER (WHERE is_active) || ' / ' || sum(order_qty) FILTER (WHERE is_active)
        FROM core.order_line_ext WHERE brand='BEANPOLE KIDS'""", "12 / 10 / 8880", GOLDEN_2210),
    ("Production plan BPK: rows / qty", ("file", "261016 MJ_DHG BPK"),
     "SELECT count(*) || ' / ' || sum(qty) FROM core.production_plan WHERE brand='BEANPOLE KIDS'", "10 / 9270", GOLDEN_2210),
    ("Production plan: LBV-27002 BAL = -5 (file) = recomputed", ("file", "261016 MJ_DHG BPK"),
     "SELECT bal_days || ' / ' || bal_calc FROM core.production_plan WHERE file_no='LBV-27002'", "-5 / -5", GOLDEN_2210),
    ("History CHALLENGER 27SS 261005 -> 261015: factory changes", ("file", "261005 MJ) 27SS CHALLENGER"),
     """SELECT count(*) FROM mart.version_change WHERE family='CHALLENGER|CHALLENGER' AND season='27SS'
        AND from_file LIKE '261005%' AND to_file LIKE '261015%' AND kind='FACTORY'""", 27),
    ("History CHALLENGER 27SS 261015 -> 261020: only CHG1MPT7131 ETD", ("file", "261020 MJ) 27SS CHALLENGER"),
     """SELECT string_agg(style_no || ':' || kind, ',') FROM mart.version_change WHERE family='CHALLENGER|CHALLENGER'
        AND season='27SS' AND from_file LIKE '261015%' AND to_file LIKE '261020%' AND kind IN ('ETD','QTY','FACTORY','STATUS')""",
     "CHG1MPT7131:ETD"),
    ("History JBEE 261006 -> 261019: factory assignments", ("file", "261006 MJ) 27SS JBEE"),
     "SELECT count(*) FROM mart.version_change WHERE family='JBEE|NEPA' AND kind='FACTORY'", 8),
    # ---- new / new-version files (N-04) ----
    ("Production plans: every file read with a known layout", None,
     "SELECT count(*) FILTER (WHERE status <> 'LOADED') FROM etl.source_file WHERE parser = 'production_plan'", 0),
    ("Production plans: due / BAL rules kept per file (not hard-coded)", ("file", "261022R 27SS NEPA PRODUCTION PLAN"),
     """SELECT string_agg(DISTINCT bal_rule, ',' ORDER BY bal_rule) || ' | ' || string_agg(DISTINCT due_eta_rule, ',' ORDER BY due_eta_rule)
        FROM raw.production_plan""", "ETA VN-ETA,ETA+1,ETA+2,ETD VN-ETD | ETD+7,RDD-2,RDD-3"),
    ("Production plan GIA NGUYEN: year typo reported, not corrected", ("file", "261020_NEPA - GIA NGUYEN"),
     """SELECT (SELECT count(*) FROM etl.data_issue WHERE code = 'YEAR_SUSPECT' AND entity = '7N30613') || ' / ' ||
        (SELECT any_value(exf_plan) FROM raw.production_plan WHERE style_no = '7N30613')""", "2 / 2026-02-08"),
    ("SHIPPING SCHEDULE: SHIPPED STYLES order qty = total row (SHIPPED STYLES!G134)", ("file", "261015) 26FW CHALLENGER SHIPPING SCHEDULE"),
     "SELECT sum(order_qty) FROM core.shipping_schedule WHERE status = 'SHIPPED'", 74447),
    ("SHIPPING SCHEDULE: styles with RDD = ETD VN + 12 (Q20 evidence)", ("file", "261015) 26FW CHALLENGER SHIPPING SCHEDULE"),
     "SELECT count(*) FILTER (WHERE rdd_minus_etd = 12) || ' of ' || count(*) FROM core.shipping_schedule", "137 of 138"),
    ("Buyer order status PDF: styles / pcs = page totals ('이 장 합계')", ("file", "오더리캡 현황"),
     """SELECT string_agg(brand || ' ' || n || ' / ' || q, ', ' ORDER BY brand) FROM (
          SELECT brand, count(*) AS n, sum(qty) AS q FROM core.buyer_order_status GROUP BY brand)""",
     "8 SECONDS 17 / 28600, BEANPOLE KIDS 12 / 10370"),
    # ---- phase-1 parsers (D-02): spec analys-docs/mvp_phase1_spec.md §8 (G1-G12) + total cells of the files ----
    ("G1 daily production files found / loaded", ("file", "261016  26FW (CHALLENGER - TBM) DAILY"),
     """SELECT count(*) || ' / ' || count(*) FILTER (WHERE status = 'LOADED') FROM etl.source_file
        WHERE parser = 'daily_production'""", "7 / 7"),
    ("G2 last daily report per factory", ("file", "261016  26FW (CHALLENGER - TBM) DAILY"),
     """SELECT string_agg(factory_code || ' ' || strftime(d, '%d/%m'), ', ' ORDER BY factory_code) FROM (
          SELECT factory_code, max(report_date) AS d FROM core.daily_row GROUP BY 1)""",
     "DONG MY 28/09, HA HIEU 28/09, HAGACO 15/10, MTT 02/10, NATEXCO 08/09, TAN BINH MINH 15/10, TRUONG PHUC 14/10"),
    ("G3 TBM sheets 13.01 / 14.01 / 15.01 read as 13-15/10 (REPORT_DATE_FIXED)", ("file", "261016  26FW (CHALLENGER - TBM) DAILY"),
     """SELECT (SELECT count(*) FROM etl.data_issue WHERE code = 'REPORT_DATE_FIXED' AND entity IN ('13.01', '14.01', '15.01'))
        || ' / ' || (SELECT string_agg(DISTINCT strftime(report_date, '%d/%m'), ',' ORDER BY strftime(report_date, '%d/%m'))
                     FROM core.daily_row WHERE sheet IN ('13.01', '14.01', '15.01'))""", "3 / 13/10,14/10,15/10"),
    ("G4 CHALLENGER styles in daily reports / found in ORDER RECAP", ("file", "261016  26FW (CHALLENGER - TBM) DAILY"),
     """SELECT count(DISTINCT d.style_no) || ' / ' || count(DISTINCT o.style_no) FROM core.daily_row d
        LEFT JOIN core.style_order o ON o.style_no = d.style_no WHERE d.customer = 'CHALLENGER'""", "101 / 101"),
    # G5 counts running (active) styles without any daily report; mart.style_freshness also leaves out styles already
    # shipped in full (CHF4WJK6803: 451 / 450 in Shipment Status 261021R1), so it shows 8 there.
    ("G5 CHALLENGER 26FW running styles with no daily report (NO_REPORT)", ("file", "261016  26FW (CHALLENGER - TBM) DAILY"),
     """SELECT count(*) FROM core.style_order WHERE season = '26FW' AND is_active
        AND style_no NOT IN (SELECT style_no FROM core.daily_row)""", 9),
    ("G6 CHF4MPT6444 output last-seen / rate / ready / days late", ("file", "261016  26FW (CHALLENGER - TBM) DAILY"),
     """SELECT output_ttl || ' / ' || CAST(rate AS INT) || ' / ' || ready_date || ' / ' || days_late FROM mart.style_forecast
        WHERE style_no = 'CHF4MPT6444'""", "190 / 50 / 2026-10-25 / 18"),
    ("G7 CHF4WPT6846 output / ready / days late", ("file", "261016  26FW (CHALLENGER - TBM) DAILY"),
     "SELECT output_ttl || ' / ' || ready_date || ' / ' || days_late FROM mart.style_forecast WHERE style_no = 'CHF4WPT6846'",
     "290 / 2026-10-21 / 14"),
    ("G8 freshness on 2026-10-19: NATEXCO / TAN BINH MINH / TRUONG PHUC", ("file", "260908 - 26FW  - (CHALLENGER - NATEXCO)"),
     """SELECT string_agg(factory_code || ' ' || mart.freshness_level(d, DATE '2026-10-19'), ', ' ORDER BY factory_code) FROM (
          SELECT factory_code, max(report_date) AS d FROM core.daily_row
          WHERE factory_code IN ('NATEXCO', 'TAN BINH MINH', 'TRUONG PHUC') GROUP BY 1)""",
     "NATEXCO DARK, TAN BINH MINH FRESH, TRUONG PHUC FRESH"),
    ("G12 HAGACO sheet 15/10: GRAND TOTAL rows / ORDER / OUT PUT (file cells) = size rows", ("file", "261015. DHG-HAGACO"),
     """SELECT (SELECT count(*) || ' / ' || sum(order_qty) || ' / ' || sum(output_ttl) FROM raw.daily_prod_total t
                JOIN etl.source_file f USING (file_id) WHERE f.file_name LIKE '261015. DHG-HAGACO%' AND t.sheet = '10.15')
        || ' = ' || (SELECT sum(order_qty) || ' / ' || sum(output_ttl) FROM raw.daily_prod_row r
                JOIN etl.source_file f USING (file_id) WHERE f.file_name LIKE '261015. DHG-HAGACO%' AND r.sheet = '10.15')""",
     "8 / 12740 / 10230 = 12740 / 10230"),
    ("Daily output: per factory the daily series adds up to no more than the last-seen TTL", ("file", "261016  26FW (CHALLENGER - TBM) DAILY"),
     """SELECT count(*) FROM (SELECT s.factory_code, sum(s.output_day) AS days,
                                   (SELECT sum(output_ttl) FROM core.daily_progress p WHERE p.factory_code = s.factory_code) AS ttl
                            FROM core.daily_output_series s GROUP BY s.factory_code) WHERE days > ttl""", 0),
    ("G9 inspection rows dropped: sheet factory differs from ORDER RECAP", ("file", "260727 HOA) 26SS CHALLENGER"),
     "SELECT count(DISTINCT (sheet, row_no)) FROM core.inspection_cell WHERE factory_mismatch", 12),
    ("G10 PASSED_GT_ORDER", ("file", "260727 HOA) 26SS CHALLENGER"),
     """SELECT string_agg(style_no || coalesce('-' || piece, '') || ' ' || passed || '/' || ordered, ', ' ORDER BY style_no)
        FROM mart.inspection_style WHERE passed_gt_order""", "CHF4WJK6801-JACKET 392/350, CHF4WJK6991 1381/1000"),
    ("G11 ETD change requests from the tracker remark (PENDING_REVIEW)", ("file", "260727 HOA) 26SS CHALLENGER"),
     "SELECT count(*) || ' ' || min(review_status) FROM core.inspection_proposal", "8 PENDING_REVIEW"),
    ("Inspection tracker sheet 'TP ': passed cells = row A total (H26:J26 = 378)", ("file", "260727 HOA) 26SS CHALLENGER"),
     """SELECT (SELECT sum(passed_qty) FROM raw.inspection_cell WHERE sheet = 'TP ') || ' / ' ||
               (SELECT sum(value) FROM raw.inspection_day WHERE sheet = 'TP ' AND measure = 'passed_qty')""", "378 / 378"),
    ("No inspector name column anywhere", None,
     """SELECT count(*) FROM information_schema.columns WHERE table_schema IN ('raw', 'stg', 'core', 'mart', 'fact', 'dim')
        AND (column_name ILIKE '%inspector_name%' OR column_name ILIKE '%qc_name%')""", 0),
    ("Third party (M1-12): inspections / inspected / defects / defect points / A08+A37 % / sum mismatches",
     ("file", "INPUT DATA"),
     """SELECT count(*) || ' / ' || sum(inspected_qty) || ' / ' || sum(defect_qty) || ' / ' ||
               (SELECT sum(minor + major) FROM core.qc_defect) || ' / ' ||
               (SELECT round(100.0 * sum(minor + major) FILTER (WHERE code IN ('A08', 'A37')) / sum(minor + major), 1)
                FROM core.qc_defect) || ' / ' ||
               (SELECT regexp_extract(message, '^(\\d+)', 1) FROM etl.data_issue WHERE code = 'QC_DEFECT_SUM_MISMATCH')
        FROM core.qc_inspection""", "3124 / 315745 / 68678 / 68653 / 42.9 / 285"),
    # ---- cycle coverage and synthetic data (D-04) ----
    ("Cycle coverage: CHALLENGER 26FW is a complete cycle (real data)", _R26,
     "SELECT is_complete FROM mart.cycle_complete WHERE customer = 'CHALLENGER' AND season = '26FW'", True),
    ("Synthetic data never in fact tables (is_synthetic = false everywhere)", None,
     """SELECT (SELECT count(*) FROM fact.order_line WHERE is_synthetic) + (SELECT count(*) FROM fact.shipment_lot WHERE is_synthetic)
        + (SELECT count(*) FROM fact.inspection WHERE is_synthetic) + (SELECT count(*) FROM fact.daily_output WHERE is_synthetic)""", 0),
    ("Every synthetic row has a documented assumption_id (dw/docs/assumptions.md)", None,
     """SELECT count(*) FROM (SELECT assumption_id FROM sim.style UNION ALL SELECT assumption_id FROM sim.shipment_lot
          UNION ALL SELECT assumption_id FROM sim.daily_output UNION ALL SELECT assumption_id FROM sim.inspection
          UNION ALL SELECT assumption_id FROM sim.defect)
        WHERE assumption_id NOT IN ('ASM-SIM-01', 'ASM-SIM-02', 'ASM-SIM-03', 'ASM-SIM-04', 'ASM-SIM-05')""", 0),
    ("Synthetic styles never reuse a real style code", None,
     "SELECT count(*) FROM sim.style s JOIN dim.style_alias a ON a.alias_code = s.style_code", 0),
    # ---- manager metrics (D-05): same numbers as the existing marts where they overlap ----
    ("Manager metrics: CHALLENGER 26FW shipped real = Shipment Status lots (no synthetic)", _R26,
     """SELECT shipped_real || ' / ' || order_qty || ' / ' || coalesce(shipped_syn, 0) FROM mart.mgr_season
        WHERE customer = 'CHALLENGER' AND season = '26FW'""", "60357 / 62131 / 0"),
    ("Manager metrics: on time with +7 days = mart.season_kpi (current version)", _R26,
     """SELECT (SELECT round(100.0 * on_time_tol_real / judged_real, 1) FROM mart.mgr_season
                WHERE customer = 'CHALLENGER' AND season = '26FW')
              = (SELECT ontime_pct FROM mart.season_kpi WHERE season = '26FW')""", True),
    ("Manager metrics: synthetic seasons carry no real measure", None,
     """SELECT coalesce(sum(coalesce(shipped_real, 0) + coalesce(inspected_real, 0) + judged_real), 0)
        FROM mart.mgr_season WHERE season_syn""", 0),
    # ---- linked model (D-01): style link rate, no fuzzy match ----
    ("Linked model: CHALLENGER 26FW fact rows linked to dim.style >= 98%", _R26,
     """SELECT CASE WHEN link_pct >= 98 THEN 'OK' ELSE link_pct::VARCHAR END FROM mart.link_rate
        WHERE customer = 'CHALLENGER' AND season = '26FW'""", "OK"),
    ("Linked model: other customers (all seasons) linked >= 90%", None,
     """SELECT coalesce(string_agg(customer || ' ' || pct, ', '), 'OK') FROM (
          SELECT customer, round(100.0 * sum(linked) / nullif(sum(rows_with_style) - sum(no_master), 0), 1) AS pct
          FROM mart.link_rate WHERE customer NOT IN ('CHALLENGER', '?') GROUP BY customer) WHERE pct < 90""", "OK"),
    ("Linked model: every unlinked fact row has a reason", None,
     "SELECT count(*) FROM etl.link_orphan WHERE reason IS NULL", 0),
    ("Linked model: every fact row with a factory text has a factory_key or is listed", None,
     """SELECT count(*) FROM fact.plan WHERE factory_key IS NULL AND coalesce(factory_code, factory_raw) IS NOT NULL""", 0),
    # ---- technical documents: name only (N-02) ----
    ("No report above KOPS_MAX_PARSE_MB was opened", None,
     f"""SELECT count(*) FROM etl.source_file WHERE size_bytes > {config.MAX_PARSE_MB} * 1e6
         AND parser NOT IN ('emails', 'mailbox') AND status IN ('LOADED', 'FAILED', 'UNKNOWN_TEMPLATE')""", 0),
    ("No technical document is quarantined", None,
     """SELECT count(*) FROM etl.quarantine q JOIN etl.source_file f USING (file_id) WHERE f.source_type = 'document'""", 0),
    ("Document CHF3WJK6701 FPP CFMD: style / factory / stage / date", ("doc", "260629 (CHALLENGER - TRUONG PHUC) CHF3WJK6701"),
     """SELECT any_value(style_no || ' / ' || factory || ' / ' || stage || ' / ' || doc_date) FROM core.document
        WHERE file_name LIKE '260629 (CHALLENGER - TRUONG PHUC) CHF3WJK6701%' AND ext = '.xlsx'""",
     "CHF3WJK6701 / TRUONG PHUC / FPP_CFMD / 2026-06-29"),
    # ---- style milestones / shipment events from real emails (N-03; event date = day the mail was sent) ----
    ("Milestones CHF3WJK6701 from emails", ("file", "KLMAS CO., LTD 메일 - 0514) CHF3WJK6701"),
     """SELECT string_agg(milestone || ':' || strftime(d, '%m-%d'), ',' ORDER BY d, milestone) FROM (
          SELECT DISTINCT milestone, event_date AS d FROM core.style_milestone
          WHERE style_no = 'CHF3WJK6701' AND source_kind = 'email' AND milestone <> 'FINAL_INSPECTION')""",
     "FPP_REQUEST:05-14,FPP_REQUEST:05-18,FPP_CMT:06-24,FPP_CFMD:06-29,FABRIC_INSPECTION:07-07,ASSORT_CHANGE:07-20,"
     "DM_APPROVAL:08-10,INLINE_CMT:08-12,SHIPMENT:08-17"),
    ("Milestone CHF3WJK6701 ASSORT_CHANGE: buyer mail then KLMAS -> factory", ("file", "KLMAS CO., LTD 메일 - 0720) CHF3WJK6701"),
     """SELECT string_agg(strftime(event_at, '%H:%M') || ' ' || sender_side, ', ' ORDER BY event_at) FROM core.style_milestone
        WHERE style_no = 'CHF3WJK6701' AND milestone = 'ASSORT_CHANGE' AND source_kind = 'email'""", "07:27 EXTERNAL, 09:33 KLMAS"),
    ("Shipment event ABKHPH2608058: direction / ETD / factory / customer", ("file", "KLMAS CO., LTD 메일 - 260819ETD"),
     "SELECT any_value(direction || ' / ' || etd_new || ' / ' || factory || ' / ' || customer) FROM core.shipment_event WHERE booking = 'ABKHPH2608058'",
     "outbound / 2026-08-19 / TRUONG PHUC / CHALLENGER"),
    ("Shipment event JAKEHPH2609051 (9/27->9/29 ETD): direction / old / new / factory / first mail",
     ("file", "KLMAS CO., LTD 메일 - 9_27-_9_29ETD"),
     """SELECT any_value(direction || ' / ' || etd_old || ' / ' || etd_new || ' / ' || factory || ' / ' || CAST(first_sent_at AS DATE))
        FROM core.shipment_event WHERE booking = 'JAKEHPH2609051'""", "inbound_material / 2026-09-27 / 2026-09-29 / B85 / 2026-09-30"),
    ("Milestones and shipment events cover every customer with emails", ("file", "KLMAS CO., LTD 메일 - 0514) CHF3WJK6701"),
     """SELECT string_agg(DISTINCT c, ',' ORDER BY c) FROM (
          SELECT customer AS c FROM core.style_milestone WHERE source_kind = 'email' AND NOT is_sample
          INTERSECT SELECT customer FROM core.shipment_event WHERE NOT is_sample)""", "CHALLENGER,DHG,DKM,JBEE"),
    # Same (email, style) pairs as the former strpos join (N-07); LBV-26002 is not in the style dictionary yet
    # (no BEANPOLE KIDS 26FW ORDER RECAP / plan received), so neither method finds it.
    ("Email mentions by token: CHF3WJK6701 / LBV-26002 / LEV-26111 (messages)", ("file", "KLMAS CO., LTD 메일 - 0514) CHF3WJK6701"),
     """SELECT string_agg(k || ' ' || (SELECT count(DISTINCT m.msg_key) FROM core.email_mention m JOIN core.style_dictionary d
                ON d.style_no = m.style_no WHERE d.key = k), ' / ' ORDER BY k)
        FROM (VALUES ('CHF3WJK6701'), ('LBV-26002'), ('LEV-26111')) v(k)""", "CHF3WJK6701 13 / LBV-26002 0 / LEV-26111 16"),
    # ---- emails (SAMPLE files in dw/samples/inbox) ----
    ("Email: same message in .eml and quoted in a PDF counted once", ("file", "08_buyer_original_duplicate"),
     "SELECT count(*) || ' / ' || max(n_copies) FROM core.email WHERE thread_key='[sample] 26fw chf4mpt6444 delivery'", "2 / 2"),
    ("Email: Korean PDF header parsed (보낸 날짜 → 2026-10-14 14:05)", ("file", "06_korean_qty_sample"),
     "SELECT strftime(sent_at, '%Y-%m-%d %H:%M') FROM core.email WHERE sender_email='sujin.lee@dhg-sample.kr'",
     "2026-10-14 14:05"),
    ("Email: scanned PDF without text is reported, not guessed", ("file", "09_scanned_no_text"),
     "SELECT count(*) FROM etl.data_issue WHERE code='PDF_NO_TEXT'", 1),
    ("Email: Gmail .mhtml thread: messages / first sent / expiring link attachments", ("file", "10_gmail_saved_thread"),
     """SELECT count(*) FILTER (WHERE NOT is_quoted) || ' / ' || strftime(min(sent_at), '%Y-%m-%d %H:%M') || ' / ' ||
        (SELECT count(*) FILTER (WHERE is_link AND expires_on = DATE '2026-08-19') || ' of ' || count(*)
         FROM raw.email_attachment a JOIN etl.source_file f USING (file_id) WHERE f.file_name LIKE '10_gmail%')
        FROM raw.email e JOIN etl.source_file f USING (file_id) WHERE f.file_name LIKE '10_gmail%'""", "2 / 2026-07-20 07:27 / 1 of 3"),
]


def run_checks(db_path=None) -> bool:
    main = str(db_path or config.DB_PATH)
    groups: dict[tuple, list] = {}
    for check in CHECKS:
        groups.setdefault(tuple(check[4]) if len(check) > 4 else (), []).append(check[:4])
    ok = True
    print("Golden / structural checks")
    for pins, checks in groups.items():
        db = main
        if pins:
            from .pipeline import build
            name = "snapshot_" + min(pins)[:6]
            print(f"  -- golden pinned to: {', '.join(pins)}")
            db = str(build(verbose=False, pins=list(pins), db_path=config.BUILD_DIR / f"{name}.duckdb"))
        ok &= _run(db, checks)
    con = duckdb.connect(main, read_only=True)
    failed = con.execute("SELECT file_name, message FROM etl.source_file WHERE status='FAILED'").fetchall()
    con.close()
    for f, m in failed:
        ok = False
        print(f"  FAIL  source failed to parse: {f}: {m}")
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    return ok


def _run(db: str, checks: list) -> bool:
    con = duckdb.connect(db, read_only=True)
    loaded = {(p, s) for p, s in con.execute(
        "SELECT parser, season FROM etl.source_file WHERE is_current").fetchall()}
    names = [n for (n,) in con.execute("SELECT file_name FROM etl.source_file WHERE status='LOADED'").fetchall()]
    docs = [n for (n,) in con.execute("SELECT file_name FROM core.document").fetchall()]
    ok = True
    for name, need, sql, expected in checks:
        if need and need[0] in ("file", "doc"):
            if not any(n.startswith(need[1]) for n in (names if need[0] == "file" else docs)):
                print(f"  SKIP  {name}  (source not loaded)")
                continue
        elif need and need not in loaded:
            print(f"  SKIP  {name}  (source not loaded)")
            continue
        got = con.execute(sql).fetchone()[0]
        good = (float(got) == float(expected)) if isinstance(expected, (int, float)) and got is not None else got == expected
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: {got}" + ("" if good else f" (expected {expected})"))
    con.close()
    return ok
