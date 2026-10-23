"""Automatic UI test of the manager dashboard (E-07): python -m kops_dw check-ui --out <dir> [--quick]  (make check-ui).

Playwright drives the system Chromium (Docker image: Debian chromium; macOS: Google Chrome) against the dashboard
served on 127.0.0.1. Matrix on season 26FW (the season with real + synthetic data): every page x light / dark x
desktop / mobile x VI / KO x synthetic off / on, plus every page of the running season 27SS (real data only).
Each load must have:
  - no console error / page error, and no render error banner;
  - every chart drawn, or the "no data yet" message (never empty axes);
  - synthetic-data chips (.syn.sim) present with syn=1 on the pages that show synthetic data, absent with syn=0;
  - no horizontal page scroll (mobile 390 px);
and the main KPIs equal the marts (DuckDB, read only): CHALLENGER 26FW order qty / shipped % / on-time %, 27SS action
count. Screenshots go to <dir> (outside the repo: they show KLMAS data).
"""
from __future__ import annotations

import itertools
import time
from pathlib import Path
from urllib.parse import urlencode

import duckdb

from . import config
from .report import find_chrome, start_server

PAGES = ("actions", "overview", "production", "ship", "quality", "factory", "change", "style", "health")
SIM_PAGES = ("overview", "production", "ship", "quality", "factory")       # 26FW pages that show synthetic data
VIEWPORTS = {"desktop": (1366, 900), "mobile": (390, 844)}

PROBE = """() => {
  const charts = [...document.querySelectorAll('.chart')];
  const bad = charts.filter(c => c.dataset.empty ? !c.querySelector('.empty') : !(c.querySelector('svg') && c.querySelector('svg').childElementCount > 0));
  const err = [...document.querySelectorAll('#main .banner')].some(b => b.dataset.error === '1');
  return {charts: charts.length, empty: charts.filter(c => c.dataset.empty).length, bad: bad.map(c => c.id),
          sim: document.querySelectorAll('.syn.sim').length, lang: document.documentElement.lang, renderError: err,
          overflow: document.documentElement.scrollWidth - window.innerWidth,
          kpi: Object.fromEntries([...document.querySelectorAll('[data-kpi]')].map(k => [k.dataset.kpi, k.dataset.v]))};
}"""


def _expected() -> dict:
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    o, sh, ot, j = con.execute("""SELECT sum(order_qty), sum(shipped_real), sum(on_time_real), sum(judged_real) FROM mart.mgr_season
                                  WHERE customer = 'CHALLENGER' AND season = '26FW'""").fetchone()
    acts = con.execute("SELECT count(*) FROM mart.mgr_action WHERE season = '27SS' OR season IS NULL").fetchone()[0]
    con.close()
    return {"order": float(o), "shipped_pct": 100.0 * sh / o, "ontime_pct": 100.0 * ot / j, "actions": float(acts)}


def run(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else None
    if not out:
        print("usage: python -m kops_dw check-ui --out <dir outside the repo> [--quick]")
        return 2
    if (config.REPO_DIR / ".git").exists() and out.resolve().is_relative_to(config.REPO_DIR.resolve()):
        print(f"--out {out} is inside the repo: screenshots show KLMAS data, use a folder outside it")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    if not chrome:
        print("Chromium / Chrome not found: set KOPS_CHROME or run `make check-ui` (Docker image)")
        return 1
    quick = "--quick" in argv
    exp = _expected()
    httpd, port = start_server()
    results: list[tuple[str, bool, str]] = []
    t0 = time.time()

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        if not ok:
            print(f"  FAIL  {name}: {detail}", flush=True)

    loads = [("26FW", pg, th, vp, lg, syn) for pg, th, vp, lg, syn in itertools.product(
        PAGES, ("light", "dark"), VIEWPORTS, ("vi", "ko"), ("0", "1"))]
    if quick:
        loads = [x for x in loads if x[2] == "light" and x[4] == "vi"] + [x for x in loads if x[3] == "mobile" and x[5] == "1"]
    loads += [("27SS", pg, "light", "desktop", "vi", "0") for pg in PAGES]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"])
            for (season, page_id, theme, vp, lang, syn) in loads:
                w, h = VIEWPORTS[vp]
                ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=vp == "mobile", has_touch=vp == "mobile",
                                          color_scheme=theme)
                page = ctx.new_page()
                errors: list[str] = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                q = {"tab": page_id, "season": season, "lang": lang, "theme": theme, "syn": syn, "noanim": 1}
                name = f"{season} {page_id} {theme} {vp} {lang} syn={syn}"
                page.goto(f"http://127.0.0.1:{port}/?{urlencode(q)}")
                page.wait_for_selector("body[data-load-ms]", timeout=30000)
                page.wait_for_timeout(150)
                r = page.evaluate(PROBE)
                check(f"{name}: no console / page errors", not errors, "; ".join(errors[:3]))
                check(f"{name}: page rendered", not r["renderError"])
                check(f"{name}: every chart drawn or 'no data yet'", not r["bad"], ", ".join(r["bad"]))
                check(f"{name}: language", r["lang"] == lang, r["lang"])
                check(f"{name}: no horizontal scroll", r["overflow"] <= 1, f"{r['overflow']} px")
                if syn == "0":
                    check(f"{name}: no synthetic-data chip", r["sim"] == 0, f"{r['sim']} chip(s)")
                elif season == "26FW" and page_id in SIM_PAGES:
                    check(f"{name}: synthetic-data chips shown", r["sim"] > 0, "0 chip")
                page.screenshot(path=str(out / f"{season}_{page_id}_{theme}_{vp}_{lang}_syn{syn}.png"), full_page=True)
                ctx.close()
            # main KPIs against the marts
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            for q, keys in ((dict(tab="overview", season="26FW", customer="CHALLENGER", syn="0"), ("order", "shipped_pct", "ontime_pct")),
                            (dict(tab="actions", season="27SS", syn="0"), ("actions",))):
                page.goto(f"http://127.0.0.1:{port}/?{urlencode({**q, 'noanim': 1})}")
                page.wait_for_selector("body[data-load-ms]", timeout=30000)
                kpi = page.evaluate(PROBE)["kpi"]
                for k in keys:
                    got = float(kpi.get(k) or "nan")
                    check(f"KPI {q['tab']} {q['season']} {k} = mart", abs(got - exp[k]) < 0.05, f"page {got} / mart {exp[k]:.2f}")
            browser.close()
    finally:
        httpd.shutdown()
    ok = sum(1 for r in results if r[1])
    print(f"UI checks: {ok}/{len(results)} passed, {len(loads)} page loads, {time.time() - t0:.0f} s; screenshots in {out}")
    print("ALL PASS" if ok == len(results) else "SOME UI CHECKS FAILED")
    return 0 if ok == len(results) else 1
