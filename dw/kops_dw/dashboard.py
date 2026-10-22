"""Render build/dashboard.html: a single offline HTML file with the mart tables embedded as JSON.

The output contains KLMAS business data: it is written to build/ (git-ignored) and must not be
published outside the project."""
from __future__ import annotations

import datetime as dt
import decimal
import json

import duckdb

from . import config

TEMPLATE = config.DW_DIR / "templates" / "dashboard.html"

QUERIES = {
    "season_kpi": "SELECT * FROM mart.season_kpi ORDER BY season",
    "styles": """SELECT season, style_no, order_no, status, health, is_active, factory_code, collection, description_en,
                 name_kr, fabric_supplier, etd_vn, rdd_kr, order_qty, n_colors, order_qty_ship_file, order_qty_prod_file,
                 shipped_qty, sample_qty, balance_qty, ship_pct, output_qty, output_pct, inspected_qty, daily_output,
                 projected_ready, days_late, first_lot_etd, n_lots, has_air, shipped_on_time, n_factory_moves,
                 factory_history, n_qty_changes, n_issues, as_of, fpp_cfmd, cutting_plan, input_plan,
                 sewing_finish_plan, file_id, row_no
                 FROM mart.style_360 ORDER BY season, style_no""",
    "factory_kpi": "SELECT * FROM mart.factory_kpi ORDER BY season, order_qty DESC",
    "supplier": "SELECT * FROM mart.supplier_styles ORDER BY season, styles DESC",
    "ship_weekly": "SELECT * FROM mart.shipment_weekly ORDER BY week_start",
    "lots": "SELECT * FROM mart.shipment_lot ORDER BY lot_etd",
    "assortment": "SELECT * FROM mart.assortment",
    "lot_detail": "SELECT * FROM mart.lot_detail",
    "recon": "SELECT * FROM mart.reconciliation WHERE mismatch IS NOT NULL ORDER BY season, style_no",
    "changes": "SELECT * FROM mart.change_log ORDER BY event_date DESC NULLS LAST",
    "proposals": "SELECT * FROM core.change_proposal ORDER BY sent_at",
    "emails": "SELECT message_id, sent_at, sender, subject, is_sample, left(body, 1200) AS body FROM core.email ORDER BY sent_at",
    "issues": """SELECT i.severity, i.code, i.entity, i.message, i.location, f.file_name
                 FROM etl.data_issue i LEFT JOIN etl.source_file f USING (file_id)
                 ORDER BY CASE i.severity WHEN 'ERROR' THEN 0 WHEN 'WARN' THEN 1 ELSE 2 END, i.code""",
    "sources": "SELECT * FROM mart.source_lineage ORDER BY file_id",
    "requirements": "SELECT * FROM core.requirement ORDER BY req_no",
    "actions": "SELECT * FROM core.action_item",
    "decisions": "SELECT * FROM core.decision ORDER BY no NULLS FIRST",
    "meeting": "SELECT * FROM core.meeting",
    "rules": "SELECT * FROM stg.rule",
    # all customers, plans, history, email analytics
    "portfolio": "SELECT * FROM mart.customer_portfolio ORDER BY order_qty DESC NULLS LAST",
    "factory_all": "SELECT * FROM mart.factory_load_all ORDER BY order_qty DESC",
    "etd_all": "SELECT * FROM mart.etd_weekly_all ORDER BY week_start",
    "plan": "SELECT * FROM mart.plan_risk ORDER BY bal_days NULLS LAST",
    "versions": "SELECT * FROM mart.file_version ORDER BY parser, family, season, version_no",
    "vchanges": "SELECT * FROM mart.version_change ORDER BY to_file DESC, kind, style_no",
    "vsummary": "SELECT * FROM mart.version_change_summary ORDER BY to_file",
    "email_kpi": "SELECT * FROM mart.email_kpi",
    "email_list": "SELECT * EXCLUDE (msg_key, thread_key) FROM mart.email_list ORDER BY sent_at DESC NULLS LAST",
    "email_weekly": "SELECT * FROM mart.email_weekly ORDER BY week_start",
    "threads": "SELECT * EXCLUDE (thread_key) FROM core.email_thread ORDER BY last_at DESC NULLS LAST",
    "pstatus": "SELECT * EXCLUDE (msg_key) FROM core.proposal_file_status ORDER BY sent_at DESC",
}


def _default(o):
    if isinstance(o, dt.datetime):
        return o.strftime("%Y-%m-%d %H:%M")
    if isinstance(o, dt.date):
        return o.isoformat()
    if isinstance(o, decimal.Decimal):
        return float(o)
    raise TypeError(type(o))


def render(db_path=None, out_path=None):
    con = duckdb.connect(str(db_path or config.DB_PATH), read_only=True)
    data = {}
    for k, sql in QUERIES.items():
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        data[k] = {"cols": cols, "rows": cur.fetchall()}
    data["built_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    con.close()
    payload = json.dumps(data, default=_default, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__KOPS_DATA__*/null", payload)
    out = out_path or config.DASHBOARD_PATH
    out.write_text(html, encoding="utf-8")
    print(f"Dashboard: {out} ({out.stat().st_size // 1024} KB)")
    return out
