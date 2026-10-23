"""Golden-number regression tests (GUIDELINES.md §7) + structural checks on the built DW.

Golden values are only asserted when the matching source file is loaded, so the suite also runs on a
partial raw-docs folder (missing sources are reported as SKIP)."""
from __future__ import annotations

import duckdb

from . import config

CHECKS = [
    # (name, required parser+season, sql returning one value, expected)
    ("ORDER RECAP 26FW: style blocks", ("order_recap", "26FW"),
     "SELECT count(*) FROM core.style_order WHERE season='26FW'", 113),
    ("ORDER RECAP 26FW: active styles", ("order_recap", "26FW"),
     "SELECT count(*) FROM core.style_order WHERE season='26FW' AND is_active", 110),
    ("ORDER RECAP 26FW: order qty (sum of colours)", ("order_recap", "26FW"),
     "SELECT sum(order_qty) FROM core.style_order WHERE season='26FW' AND is_active", 62131),
    ("ORDER RECAP 27SS: style blocks", ("order_recap", "27SS"),
     "SELECT count(*) FROM core.style_order WHERE season='27SS'", 143),
    ("ORDER RECAP 27SS: active styles", ("order_recap", "27SS"),
     "SELECT count(*) FROM core.style_order WHERE season='27SS' AND is_active", 137),
    ("ORDER RECAP 27SS: order qty (sum of colours)", ("order_recap", "27SS"),
     "SELECT sum(order_qty) FROM core.style_order WHERE season='27SS' AND is_active", 87940),
    ("Shipment Status: blocks", ("shipment_status", "26FW"),
     "SELECT count(*) FROM raw.shipment_block b JOIN etl.source_file f USING (file_id) WHERE f.is_current", 144),
    ("Shipment Status: blocks with data", ("shipment_status", "26FW"),
     "SELECT count(*) FROM raw.shipment_block b JOIN etl.source_file f USING (file_id) WHERE f.is_current AND has_data", 104),
    ("Shipment Status: blocks whose recomputed totals match the file", ("shipment_status", "26FW"),
     """SELECT count(*) FROM raw.shipment_block b JOIN etl.source_file f USING (file_id) WHERE f.is_current AND has_data
        AND order_ttl_reported IS NOT DISTINCT FROM order_ttl_computed
        AND shipped_smpl_reported IS NOT DISTINCT FROM shipped_smpl_computed""", 104),
    ("Production Status: styles", ("production_status", "26FW"),
     "SELECT count(*) FROM core.production_snapshot WHERE season='26FW'", 110),
    ("Production Status: order qty recomputed (file shows 106,681)", ("production_status", "26FW"),
     "SELECT sum(order_qty_reported) FROM core.production_snapshot WHERE season='26FW'", 62357),
    ("Production Status: broken grand total is flagged", ("production_status", "26FW"),
     "SELECT count(*) FROM etl.data_issue WHERE code='TOTAL_MISMATCH' AND entity='G.TTL' AND message LIKE '%106681%'", 1),
    ("Cross-file: styles with order qty mismatch", ("shipment_status", "26FW"),
     "SELECT count(*) FROM mart.reconciliation WHERE season='26FW' AND mismatch LIKE 'ORDER:%'", 4),
    ("Factory history CHF3MJK6301 (NATEXCO -> HA HIEU -> MTT)", ("order_recap", "26FW"),
     """SELECT string_agg(coalesce(factory_code, factory_hint), '>' ORDER BY event_date) FROM core.factory_event
        WHERE style_no='CHF3MJK6301'""", "NATEXCO>HA HIEU>MTT"),
    ("Alert W33 CHF4MPT6444 projected ~49 days late", ("production_status", "26FW"),
     "SELECT days_late FROM mart.style_360 WHERE style_no='CHF4MPT6444'", 49),
    # Prototype showed 79%; the DW also matches the 3 aliased style codes (Q05), giving 79.6%.
    ("26FW on-time shipment rate (first lot <= ETD + 7)", ("shipment_status", "26FW"),
     "SELECT ontime_pct FROM mart.season_kpi WHERE season='26FW'", 79.6),
    # structural rules
    ("No email change is applied without review", None,
     "SELECT count(*) FROM core.change_proposal WHERE review_status <> 'PENDING_REVIEW'", 0),
    ("Every core style row traces back to a source file", None,
     "SELECT count(*) FROM core.style_order o LEFT JOIN etl.source_file f USING (file_id) WHERE f.file_id IS NULL", 0),
    ("Prompt-injection sample did not alter data", None,
     """SELECT count(*) FROM core.change_proposal WHERE upper(evidence) LIKE '%IGNORE PREVIOUS%'
        OR (change_type IN ('QTY', 'QTY_PCT') AND proposed_qty = 0)""", 0),
    # ---- other customers (header-driven ORDER RECAP), production plan, history ----
    ("8 SECONDS 26FW: styles / qty", ("file", "261006. DUNG) DHG 8S 26FW"),
     "SELECT count(*) || ' / ' || sum(order_qty) FROM core.order_line_ext WHERE customer='DHG' AND brand='8 SECONDS' AND season='26FW'",
     "59 / 119392"),
    ("MIZUNO 27SS: styles / qty", ("file", "261019 HANG) 27SS MIZUNO"),
     "SELECT count(*) || ' / ' || sum(order_qty) FROM core.order_line_ext WHERE customer='DKM' AND season='27SS'", "26 / 43909"),
    ("JBEE 27SS: qty", ("file", "261019 MJ) 27SS JBEE"),
     "SELECT sum(order_qty) FROM core.order_line_ext WHERE customer='JBEE' AND season='27SS' AND is_active", 67100),
    ("KOFA 27SS: active qty (cancelled BLACKYAK blocks excluded)", ("file", "261015 MJ) 27SS KOFA"),
     "SELECT sum(order_qty) FROM core.order_line_ext WHERE customer='KOFA' AND is_active", 4000),
    ("Beanpole Kids 27SS current version = 261021: blocks / active / qty", ("file", "261021 DHG) BPK 27SS"),
     """SELECT count(*) || ' / ' || count(*) FILTER (WHERE is_active) || ' / ' || sum(order_qty) FILTER (WHERE is_active)
        FROM core.order_line_ext WHERE brand='BEANPOLE KIDS'""", "12 / 10 / 8880"),
    ("Production plan BPK: rows / qty", ("file", "261016 MJ_DHG BPK"),
     "SELECT count(*) || ' / ' || sum(qty) FROM core.production_plan WHERE brand='BEANPOLE KIDS'", "10 / 9270"),
    ("Production plan: LBV-27002 BAL = -5 (file) = recomputed", ("file", "261016 MJ_DHG BPK"),
     "SELECT bal_days || ' / ' || bal_calc FROM core.production_plan WHERE file_no='LBV-27002'", "-5 / -5"),
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
    con = duckdb.connect(str(db_path or config.DB_PATH), read_only=True)
    loaded = {(p, s) for p, s in con.execute(
        "SELECT parser, season FROM etl.source_file WHERE is_current").fetchall()}
    names = [n for (n,) in con.execute("SELECT file_name FROM etl.source_file WHERE status='LOADED'").fetchall()]
    docs = [n for (n,) in con.execute("SELECT file_name FROM core.document").fetchall()]
    ok = True
    print("Golden / structural checks")
    for name, need, sql, expected in CHECKS:
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
    failed = con.execute("SELECT file_name, message FROM etl.source_file WHERE status='FAILED'").fetchall()
    for f, m in failed:
        ok = False
        print(f"  FAIL  source failed to parse: {f}: {m}")
    con.close()
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    return ok
