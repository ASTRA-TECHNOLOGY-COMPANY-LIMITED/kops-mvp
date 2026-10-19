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
    # Prototype showed 79%; the DW also matches the 3 aliased style codes (Q3), giving 79.6%.
    ("26FW on-time shipment rate (first lot <= ETD + 7)", ("shipment_status", "26FW"),
     "SELECT ontime_pct FROM mart.season_kpi WHERE season='26FW'", 79.6),
    # structural rules
    ("No email change is applied without review", None,
     "SELECT count(*) FROM core.change_proposal WHERE review_status <> 'PENDING_REVIEW'", 0),
    ("Every core style row traces back to a source file", None,
     "SELECT count(*) FROM core.style_order o LEFT JOIN etl.source_file f USING (file_id) WHERE f.file_id IS NULL", 0),
    ("Prompt-injection sample did not alter data", None,
     "SELECT count(*) FROM core.change_proposal WHERE change_type NOT IN ('QTY','QTY_PCT','ETD','COLOR')", 0),
]


def run_checks(db_path=None) -> bool:
    con = duckdb.connect(str(db_path or config.DB_PATH), read_only=True)
    loaded = {(p, s) for p, s in con.execute(
        "SELECT parser, season FROM etl.source_file WHERE is_current").fetchall()}
    ok = True
    print("Golden / structural checks")
    for name, need, sql, expected in CHECKS:
        if need and need not in loaded:
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
