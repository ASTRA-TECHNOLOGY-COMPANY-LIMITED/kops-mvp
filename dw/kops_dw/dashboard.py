"""Render the dashboard: build/dashboard.html + the mart tables as JSON, split by season (H-11 / N-08).

  build/data/index.json      seasons, default season, build time, file sizes
  build/data/_common.json    tables without a season + rows whose season is unknown (always loaded)
  build/data/<season>.json   rows of one season: the page loads only the season being viewed (season filter on
                             every tab); switching season fetches that file once
The page fetches these files, so it is opened through `python -m kops_dw serve` (local static server on
127.0.0.1) rather than from the file system. `python -m kops_dw dashboard --single` still writes one
self-contained HTML file with every season embedded (small data sets, offline copy).

The output contains KLMAS business data: it is written to build/ (git-ignored) and must not be
published outside the project."""
from __future__ import annotations

import datetime as dt
import decimal
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import duckdb

from . import config

TEMPLATE = config.DW_DIR / "templates" / "dashboard.html"

# Detail lists are cut to the first ROW_CAP rows of each data file (queries put the newest / most severe first);
# totals stay right because KPIs come from aggregated marts. The page says which lists were cut.
ROW_CAP = int(os.environ.get("KOPS_DASH_ROWS", 2000))
CAPPED = {"pstatus", "vchanges", "changes", "emails", "email_list", "threads", "issues", "lot_detail", "assortment",
          "style_events", "sched_recap", "plan", "sources"}
# Kept whole in _common.json: the season list / KPI header and the file lineage (overview counts every source).
GLOBAL = {"season_kpi", "sources"}
# Season of an email = the season most of the styles it mentions belong to (split of the dashboard data, H-11).
EMAIL_SEASON = "SELECT msg_key, mode(season) AS season FROM core.email_mention WHERE season IS NOT NULL GROUP BY msg_key"

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
    "emails": f"""SELECT message_id, sent_at, sender, subject, is_sample, left(body, 1200) AS body, s.season
                  FROM core.email LEFT JOIN ({EMAIL_SEASON}) s USING (msg_key) ORDER BY sent_at DESC NULLS LAST""",
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
    "email_list": f"""SELECT l.* EXCLUDE (msg_key, thread_key), s.season FROM mart.email_list l
                      LEFT JOIN ({EMAIL_SEASON}) s USING (msg_key) ORDER BY sent_at DESC NULLS LAST""",
    "email_weekly": f"""SELECT date_trunc('week', e.sent_at)::DATE AS week_start, e.category, s.season, count(*) AS n
                        FROM core.email e LEFT JOIN ({EMAIL_SEASON}) s USING (msg_key) WHERE e.sent_at IS NOT NULL
                        GROUP BY ALL ORDER BY week_start""",
    "threads": f"""SELECT t.* EXCLUDE (thread_key), s.season FROM core.email_thread t LEFT JOIN (
                     SELECT e.thread_key, mode(x.season) AS season FROM core.email e JOIN ({EMAIL_SEASON}) x USING (msg_key)
                     GROUP BY e.thread_key) s USING (thread_key) ORDER BY last_at DESC NULLS LAST""",
    "pstatus": "SELECT * EXCLUDE (msg_key) FROM core.proposal_file_status ORDER BY sent_at DESC",
    # style progress (milestones from emails / document names, shipment events)
    "timeline": "SELECT * FROM mart.style_timeline ORDER BY last_event DESC NULLS LAST",
    "style_events": "SELECT * FROM mart.style_event ORDER BY style_no, event_date, milestone",
    "ship_events": "SELECT * EXCLUDE (source_ref) FROM core.shipment_event ORDER BY etd_new DESC",
    "material_delay": "SELECT * FROM mart.material_delay ORDER BY delayed DESC, shipments DESC",
    "sched_recap": "SELECT * EXCLUDE (file_id, sheet, row_no) FROM mart.schedule_vs_recap ORDER BY recap_check NULLS LAST, style_no",
    "buyer_view": "SELECT * EXCLUDE (file_id) FROM mart.plan_vs_buyer_view ORDER BY brand, file_no",
}


def _default(o):
    if isinstance(o, dt.datetime):
        return o.strftime("%Y-%m-%d %H:%M")
    if isinstance(o, dt.date):
        return o.isoformat()
    if isinstance(o, decimal.Decimal):
        return float(o)
    raise TypeError(type(o))


def _tables(con) -> dict:
    data = {}
    for k, sql in QUERIES.items():
        cur = con.execute(sql)
        data[k] = {"cols": [d[0] for d in cur.description], "rows": cur.fetchall()}
    return data


def _dump(obj) -> str:
    return json.dumps(obj, default=_default, ensure_ascii=False, separators=(",", ":"))


def _default_season(data: dict, seasons: list[str]) -> str | None:
    kpi = [r[data["season_kpi"]["cols"].index("season")] for r in data["season_kpi"]["rows"]]
    return next((s for s in kpi if s.endswith("FW")), kpi[0] if kpi else (seasons[-1] if seasons else None))


def render(db_path=None, out_path=None, single: bool = False):
    con = duckdb.connect(str(db_path or config.DB_PATH), read_only=True)
    data = _tables(con)
    con.close()
    built_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = out_path or config.DASHBOARD_PATH
    template = TEMPLATE.read_text(encoding="utf-8")
    if single:
        payload = _dump({**data, "built_at": built_at}).replace("</", "<\\/")
        out.write_text(template.replace("/*__KOPS_DATA__*/null", payload), encoding="utf-8")
        print(f"Dashboard: {out} ({out.stat().st_size // 1024} KB, all seasons embedded)")
        return out
    common, by_season = {}, {}
    for k, t in data.items():
        if "season" not in t["cols"] or k in GLOBAL:
            common[k] = t
            continue
        i = t["cols"].index("season")
        common[k] = {"cols": t["cols"], "rows": [r for r in t["rows"] if r[i] is None]}
        for r in t["rows"]:
            if r[i] is not None:
                by_season.setdefault(r[i], {}).setdefault(k, {"cols": t["cols"], "rows": []})["rows"].append(r)
    seasons = sorted(by_season, key=lambda s: (s[:2], s[2:] == "FW"))
    ddir = out.parent / "data"
    ddir.mkdir(parents=True, exist_ok=True)
    for old in ddir.glob("*.json"):
        old.unlink()
    sizes = {}
    for name, obj in [("_common", common), *by_season.items()]:
        cut = {k: len(t["rows"]) for k, t in obj.items() if k in CAPPED and len(t["rows"]) > ROW_CAP}
        for k in cut:
            obj[k] = {"cols": obj[k]["cols"], "rows": obj[k]["rows"][:ROW_CAP]}
        obj["_cut"] = {"cols": ["dataset", "total", "kept"], "rows": [[k, n, ROW_CAP] for k, n in cut.items()]}
        f = ddir / f"{name}.json"
        f.write_text(_dump(obj), encoding="utf-8")
        sizes[name] = f.stat().st_size
    index = dict(built_at=built_at, seasons=seasons, default=_default_season(data, seasons), sizes=sizes)
    (ddir / "index.json").write_text(_dump(index), encoding="utf-8")
    out.write_text(template.replace("/*__KOPS_DATA__*/null", '{"lazy":true}'), encoding="utf-8")
    big = max(sizes.items(), key=lambda x: x[1])
    from . import mgr_dashboard
    msizes = mgr_dashboard.render(db_path, out.parent)
    print(f"Dashboard: {out} + {ddir}/ ({len(seasons)} seasons; largest {big[0]}.json {big[1] / 1e6:.1f} MB); "
          f"manager.html + data/mgr ({len(msizes) - 1} seasons, largest {max(msizes.values()) / 1e6:.1f} MB) "
          f"-> open with: python -m kops_dw serve")
    return out


class _Handler(SimpleHTTPRequestHandler):
    """Serves manager.html (start page), dashboard.html, data/**.json and vendor/*.js from build/, nothing else (the
    DB and the lake stay private)."""

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.path = "/manager.html"
        elif not (path in ("/dashboard.html", "/manager.html")
                  or (path.startswith("/data/") and path.endswith(".json") and ".." not in path)
                  or (path.startswith("/vendor/") and path.endswith(".js") and ".." not in path)):
            self.send_error(404)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        pass


def serve(argv: list[str]) -> int:
    """python -m kops_dw serve [--port 8765] [--open]: local static server for the dashboard (127.0.0.1 only)."""
    import functools
    import webbrowser
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    if not (config.BUILD_DIR / "data" / "index.json").exists():
        render()
    handler = functools.partial(_Handler, directory=str(config.BUILD_DIR))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Dashboard on {url} (Ctrl+C to stop; local only)")
    if "--open" in argv:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
