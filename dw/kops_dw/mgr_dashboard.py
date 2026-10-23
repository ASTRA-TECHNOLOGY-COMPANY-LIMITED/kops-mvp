"""Manager dashboard data (D-06): build/manager.html + build/data/mgr/{index,_common,<season>}.json + build/vendor/.

Same lazy, per-season layout as the analyst dashboard (H-11): the page loads _common.json and the season(s) being viewed
('Tất cả' loads every season file once). Every row says whether it is synthetic (dw/docs/assumptions.md) so the page can
hide synthetic data and label it. Chart library: ECharts, vendored in dw/templates/vendor (no CDN).
The files contain KLMAS data: they stay in build/ (git-ignored) and are served on 127.0.0.1 only.
"""
from __future__ import annotations

import datetime as dt
import shutil

import duckdb

from . import config, i18n, questions

TEMPLATE = config.DW_DIR / "templates" / "manager.html"
VENDOR = config.DW_DIR / "templates" / "vendor"

STYLE_NK = "s.customer || '|' || s.season || '|' || s.style_no"
# key -> SQL; tables with a 'season' column are split per season file, the others go to _common.json
QUERIES = {
    "styles": """SELECT style_nk, customer, brand, season, style_no, factory_code, order_qty, etd, rdd, is_active, style_syn,
                 style_asm, shipped, first_lot_etd, n_lots, ship_syn, ship_asm, delay_days, on_time, on_time_tol, output_qty,
                 out_syn, out_last, plan_bal, cut_plan, finish_plan, ready_date, forecast_confidence, inspected, passed, defects,
                 rejects, insp_syn, n_qty_changes, n_factory_changes, n_etd_changes, n_assort_changes, pending_proposals,
                 n_emails, risk_reason
                 FROM mart.mgr_style ORDER BY customer, season, style_no""",
    "weekly": "SELECT * FROM mart.mgr_weekly WHERE week_start IS NOT NULL ORDER BY week_start",
    "scurve": "SELECT * FROM mart.mgr_scurve ORDER BY day",
    "factory": "SELECT * FROM mart.mgr_factory",
    "changes": "SELECT * FROM mart.mgr_changes WHERE month IS NOT NULL",
    "milestones": f"""SELECT {STYLE_NK} AS style_nk, s.season, s.customer, s.brand, s.factory_code, m.milestone, m.event_date, m.source_kind, m.source_title,
                      m.sender_side, m.booking, m.review_status FROM fact.milestone m JOIN dim.style s USING (style_key)
                      WHERE NOT m.is_sample ORDER BY m.event_date""",
    "lots": f"""SELECT {STYLE_NK} AS style_nk, s.season, s.customer, s.brand, s.factory_code, l.lot_label, l.lot_etd, l.ship_mode, l.qty, f.file_name AS source,
                false AS is_synthetic, NULL AS assumption_id
                FROM fact.shipment_lot l JOIN dim.style s USING (style_key) LEFT JOIN etl.source_file f ON f.file_id = l.source_file_id
                UNION ALL
                SELECT coalesce({STYLE_NK}, 'SIM|' || x.customer || '|' || x.season || '|' || x.style_code), x.season, x.customer,
                       coalesce(s.brand, x.customer), x.factory_code, x.lot_label,
                       x.lot_etd, x.ship_mode, x.qty, 'SIM', true, x.assumption_id
                FROM sim.shipment_lot x LEFT JOIN dim.style s ON s.style_key = x.style_key""",
    "daily": f"""SELECT {STYLE_NK} AS style_nk, s.season, s.customer, s.brand, s.factory_code, d.fact_date, d.output_day, d.output_ttl, false AS is_synthetic
                 FROM fact.daily_output d JOIN dim.style s USING (style_key)
                 UNION ALL
                 SELECT {STYLE_NK}, s.season, s.customer, s.brand, s.factory_code, x.fact_date, x.output_day, x.output_ttl, true
                 FROM sim.daily_output x JOIN dim.style s ON s.style_key = x.style_key""",
    "style_changes": f"""SELECT {STYLE_NK} AS style_nk, s.season, s.customer, s.brand, s.factory_code, c.change_type, c.fact_date, c.before_v, c.after_v,
                         left(c.detail, 200) AS detail, c.source, c.source_ref, c.review_status
                         FROM fact.change c JOIN dim.style s USING (style_key)""",
    "style_emails": f"""SELECT {STYLE_NK} AS style_nk, s.season, s.customer, s.brand, s.factory_code, e.sent_at, e.subject, e.category, e.sender_email
                        FROM bridge.email_style b JOIN dim.style s USING (style_key) JOIN fact.email e USING (msg_key)
                        WHERE NOT e.is_sample""",
    "documents": f"""SELECT {STYLE_NK} AS style_nk, s.season, s.customer, s.brand, s.factory_code, d.file_name, d.doc_kind, d.stage, d.doc_date
                     FROM fact.document d JOIN dim.style s USING (style_key)""",
    "recon": "SELECT * FROM mart.mgr_recon",
    # F-05 charts
    "stage": "SELECT * EXCLUDE (is_active) FROM mart.mgr_style_stage WHERE is_active",
    "qty_bridge": "SELECT * FROM mart.mgr_qty_bridge",
    "trend_size": "SELECT * FROM mart.trend_size",
    "trend_color": "SELECT * FROM mart.trend_color",
    "trend_item": "SELECT * FROM mart.trend_item",
    "trend_fabric": "SELECT * FROM mart.trend_fabric",
    "actions": "SELECT * FROM mart.mgr_action ORDER BY severity, due_date, action_id",
    "funnel": f"""SELECT f.customer || '|' || f.season || '|' || f.style_no AS style_nk, f.* EXCLUDE (is_synthetic)
                  FROM mart.style_funnel f ORDER BY style_no, color, size_code""",
    # _common (no season column)
    "season_summary": "SELECT * EXCLUDE (season), season AS season_code FROM mart.mgr_season",
    "quality": "SELECT * EXCLUDE (season), season AS season_code FROM mart.mgr_quality",
    "pareto": "SELECT * FROM mart.mgr_defect_pareto ORDER BY points DESC",
    "complaints": "SELECT * EXCLUDE (msg_key) FROM mart.mgr_buyer_complaint ORDER BY sent_at DESC",
    "email_response": "SELECT * FROM mart.mgr_email_response ORDER BY month",
    "coverage": "SELECT * EXCLUDE (season), season AS season_code FROM mart.cycle_coverage",
    "freshness": "SELECT * EXCLUDE (season), season AS season_code FROM mart.factory_freshness",
    "orphans": """SELECT fact, customer, season AS season_code, reason, count(*) AS n, string_agg(DISTINCT style_code, ', ')
                  AS codes FROM etl.link_orphan GROUP BY ALL ORDER BY n DESC""",
    "link_rate": "SELECT * EXCLUDE (season), season AS season_code FROM mart.link_rate",
    "material": "SELECT * FROM mart.material_delay",
    "ship_events": "SELECT * EXCLUDE (source_ref) FROM fact.shipment_event WHERE NOT is_sample ORDER BY etd_new DESC",
    "factory_moves": """SELECT f.factory_code, count(*) FILTER (WHERE b.src = 'note') AS moves_in,
                        count(DISTINCT b.style_key) AS styles FROM bridge.style_factory b JOIN dim.factory f USING (factory_key)
                        GROUP BY 1""",
    "sources": """SELECT parser, count(*) AS files, max(coalesce(report_date, file_date)) AS latest FROM etl.source_file
                  WHERE status = 'LOADED' AND NOT is_sample GROUP BY 1""",
}


def _default(o):
    if isinstance(o, dt.datetime):
        return o.strftime("%Y-%m-%d %H:%M")
    if isinstance(o, dt.date):
        return o.isoformat()
    if hasattr(o, "__float__"):
        return float(o)
    raise TypeError(type(o))


def render(db_path=None, build_dir=None) -> dict:
    import json
    build = build_dir or config.BUILD_DIR
    con = duckdb.connect(str(db_path or config.DB_PATH), read_only=True)
    common, by_season = {}, {}
    for k, sql in QUERIES.items():
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        if "season" not in cols:
            common[k] = {"cols": cols, "rows": rows}
            continue
        i = cols.index("season")
        common[k] = {"cols": cols, "rows": [r for r in rows if r[i] is None]}
        for r in rows:
            if r[i] is not None:
                by_season.setdefault(r[i], {}).setdefault(k, {"cols": cols, "rows": []})["rows"].append(r)
    today = con.execute("SELECT rule_value FROM stg.rule WHERE rule_key = 'today'").fetchone()
    # running season (E-04): the one whose next ETD is the nearest in the future (real styles only)
    current = con.execute("""SELECT season FROM dim.style WHERE is_active AND etd >= core.today()
                             GROUP BY season ORDER BY min(etd) LIMIT 1""").fetchone()
    con.close()
    seasons = sorted(by_season, key=lambda s: (s[:2], s[2:] == "FW"))
    # written to data/mgr.new and swapped in at the end, so an open page polling index.json (E-08) never reads a half-written set
    ddir, final = build / "data" / "mgr.new", build / "data" / "mgr"
    shutil.rmtree(ddir, ignore_errors=True)
    ddir.mkdir(parents=True)
    sizes = {}
    dump = lambda o: json.dumps(o, default=_default, ensure_ascii=False, separators=(",", ":"))   # noqa: E731
    for name, obj in [("_common", common), *by_season.items()]:
        f = ddir / f"{name}.json"
        f.write_text(dump(obj), encoding="utf-8")
        sizes[name] = f.stat().st_size
    real = [s for s in seasons if not s.startswith("25")]
    current = current[0] if current and current[0] in seasons else None
    default = current or ("26FW" if "26FW" in seasons else (real[-1] if real else seasons[-1] if seasons else None))
    now = dt.datetime.now()
    index = dict(built_at=now.strftime("%Y-%m-%d %H:%M"), build_id=now.isoformat(timespec="microseconds"), today=today[0] if today else None,
                 seasons=seasons, default=default, current=current, sizes=sizes, sim=config.SIM, questions=questions.for_dashboard(),
                 weights=config.SCORECARD_WEIGHTS, ontime_tol_days=config.RULES["ontime_tolerance_days"],
                 ready_buffer=config.RULES["ready_buffer_days"], year_suspect_days=config.RULES["year_suspect_days"],
                 latest_file=max((str(r[2]) for r in common["sources"]["rows"] if r[2]), default=None))
    (ddir / "index.json").write_text(dump(index), encoding="utf-8")
    old = build / "data" / "mgr.old"
    shutil.rmtree(old, ignore_errors=True)
    if final.exists():
        final.rename(old)
    ddir.rename(final)
    shutil.rmtree(old, ignore_errors=True)
    (build / "vendor").mkdir(exist_ok=True)
    for f in VENDOR.glob("*.js"):
        shutil.copyfile(f, build / "vendor" / f.name)
    (build / "manager.html").write_text(i18n.embed(TEMPLATE.read_text(encoding="utf-8")), encoding="utf-8")   # VI / KO text
    return sizes
