"""Automatic UI test of the manager dashboard (E-07): python -m kops_dw check-ui --out <dir> [--quick]  (make check-ui).

Playwright drives the system Chromium (tools image: Debian chromium; macOS: Google Chrome) against the web app started
on 127.0.0.1 with a throw-away state DB and a test account (app/local.py). Matrix on season 26FW (the season with real + synthetic data): every page x light / dark x
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
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import duckdb

from . import config
from .report import find_chrome

PAGES = ("overview", "actions", "notifications", "production", "ship", "quality", "factory", "trends", "change", "style", "health",
         "guide", "settings")
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
    from app.local import local_app
    app_cm = local_app("admin")
    app = app_cm.__enter__()
    base = app["url"]
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
                ctx.add_cookies([app["cookie"]])
                page = ctx.new_page()
                errors: list[str] = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                q = {"tab": page_id, "season": season, "lang": lang, "theme": theme, "syn": syn, "noanim": 1}
                name = f"{season} {page_id} {theme} {vp} {lang} syn={syn}"
                page.goto(f"{base}/?{urlencode(q)}")
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
            # ---- F-07: the real login form (first login -> forced password change -> start page with header / footer / logo)
            from app import auth as app_auth
            first_pw, new_pw = "First-login-pass-1", "Changed-pass-2026!"
            app_auth.create_user("ui-first", first_pw, "manager", must_change=True)
            lc = browser.new_context(viewport={"width": 1366, "height": 900})
            lp = lc.new_page()
            lerr: list[str] = []
            lp.on("pageerror", lambda e: lerr.append(str(e)))
            lp.goto(f"{base}/?tab=quality")
            check("Login: a page without session opens the login form", "/login" in lp.url and lp.is_visible("#fLogin"), lp.url)
            lp.fill("#u", "ui-first"); lp.fill("#p", first_pw); lp.click("#fLogin button[type=submit]")
            lp.wait_for_selector("#fChange", state="visible", timeout=10000)
            lp.fill("#n1", new_pw); lp.fill("#n2", new_pw); lp.click("#fChange button[type=submit]")
            lp.wait_for_selector("body[data-load-ms]", timeout=30000)
            lp.wait_for_timeout(300)
            shell = lp.evaluate("""() => ({tab: document.querySelector('aside nav button[aria-current=page]')?.dataset.t,
              logo: document.querySelector('#logo')?.naturalWidth || 0, kops: document.querySelector('.brand')?.textContent.includes('KOPS'),
              foot: document.querySelector('footer')?.textContent || '', bell: document.querySelector('#bellCount')?.textContent || '',
              chat: !document.querySelector('#chatBtn').hidden, user: document.querySelector('#userBtn')?.textContent || ''})""")
            check("Login: password changed at first login, back to the page asked for", shell["tab"] == "quality" and not lerr, f"{shell['tab']} {lerr[:2]}")
            check("Shell: header logo + KOPS, footer company / version / data date, user menu", shell["logo"] > 0 and shell["kops"] and
                  "©" in shell["foot"] and "KOPS " in shell["foot"] and "ui-first" in shell["user"], json.dumps(shell, ensure_ascii=False)[:200])
            api_unread = lp.evaluate("async () => (await (await fetch('/api/notifications/count')).json()).unread")
            check("Bell: unread count = notifications API", shell["bell"] == (str(api_unread) if api_unread else ""), f"bell {shell['bell']!r} / api {api_unread}")
            lp.goto(f"{base}/?tab=overview&lang=vi"); lp.wait_for_selector("body[data-load-ms]")
            check("Start page after login: Overview with top-10 actions and new notifications", lp.evaluate(
                "() => !!document.querySelector('#tTopAct') && !!document.querySelector('#newNotes')"), "")
            # chatbot: 5 sample questions, each answered with a source and the data date
            lp.click("#chatBtn"); lp.wait_for_selector(".chips button")
            qs = ["Style CHF3WJK6701 đang ở bước nào? Đã xuất bao nhiêu?", "BI7139UE1 có rủi ro gì? Vì sao?",
                  "Nhà máy nào không gửi báo cáo ngày quá 1 ngày làm việc?", "Màu nào được đặt nhiều nhất mùa FW, mùa SS?",
                  "Còn bao nhiêu đề xuất thay đổi chờ duyệt? Của khách nào?"]
            for i, qq in enumerate(qs, 1):
                lp.fill("#chatInput", qq); lp.press("#chatInput", "Enter")
                lp.wait_for_function(f"document.querySelectorAll('.chat-a .meta').length >= {i} && !document.getElementById('chatWait')", timeout=20000)
            metas = lp.evaluate("() => [...document.querySelectorAll('.chat-a .meta')].map(m => m.textContent)")
            check("Chatbot: 5 sample questions answered with source and data date", len(metas) == 5 and all("Nguồn" in m and "dữ liệu tới" in m for m in metas),
                  " | ".join(m[:60] for m in metas))
            lc.close()
            # replace the logo (branding/ folder): the page shows the new file without a rebuild
            import tempfile
            old_brand = config.BRANDING_DIR
            with tempfile.TemporaryDirectory(prefix="kops-brand-") as bd:
                (Path(bd) / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="32"><rect width="64" height="32" fill="#e34948"/>'
                                                   '<!-- ui-test-logo --></svg>', encoding="utf-8")
                config.BRANDING_DIR = Path(bd)
                try:
                    bctx = browser.new_context(viewport={"width": 1366, "height": 900}, color_scheme="light")
                    bctx.add_cookies([app["cookie"]])
                    bp = bctx.new_page()
                    bp.goto(f"{base}/?theme=light&noanim=1"); bp.wait_for_selector("body[data-load-ms]")
                    got = bp.evaluate("async () => [(await (await fetch('/branding/logo.svg')).text()).includes('ui-test-logo'), document.querySelector('#logo').naturalWidth]")
                    check("Branding: a replaced branding/logo.svg shows without rebuild", got[0] and got[1] == 64, str(got))
                    bctx.close()
                finally:
                    config.BRANDING_DIR = old_brand
            # no session: pages go to the login page, data answers 401 (full route list: security check, F-07)
            anon = browser.new_context()
            r = anon.request.get(f"{base}/api/data/mgr/index.json")
            check("No session: data API answers 401", r.status == 401, str(r.status))
            pg = anon.new_page()
            pg.goto(f"{base}/?tab=overview")
            check("No session: dashboard redirects to /login", "/login" in pg.url, pg.url)
            anon.close()
            # main KPIs against the marts
            kctx = browser.new_context(viewport={"width": 1366, "height": 900})
            kctx.add_cookies([app["cookie"]])
            page = kctx.new_page()
            for q, keys in ((dict(tab="overview", season="26FW", customer="CHALLENGER", syn="0"), ("order", "shipped_pct", "ontime_pct")),
                            (dict(tab="actions", season="27SS", syn="0"), ("actions",))):
                page.goto(f"{base}/?{urlencode({**q, 'noanim': 1})}")
                page.wait_for_selector("body[data-load-ms]", timeout=30000)
                kpi = page.evaluate(PROBE)["kpi"]
                for k in keys:
                    got = float(kpi.get(k) or "nan")
                    check(f"KPI {q['tab']} {q['season']} {k} = mart", abs(got - exp[k]) < 0.05, f"page {got} / mart {exp[k]:.2f}")
            # new data while the page stays open (E-08): render again, the page picks it up without a reload
            from .mgr_dashboard import render
            page.goto(f"{base}/?tab=overview&noanim=1")
            page.wait_for_selector("body[data-load-ms]", timeout=30000)
            before = page.evaluate("() => [IDX.build_id, performance.getEntriesByType('navigation').length]")
            render()
            page.evaluate("() => pollNewData()")
            page.wait_for_timeout(500)
            after = page.evaluate("() => [IDX.build_id, performance.getEntriesByType('navigation').length, document.querySelector('#built.fresh') != null]")
            check("New build picked up by the open page without reload", after[0] != before[0] and after[1] == before[1] and after[2],
                  f"{before} -> {after}")
            browser.close()
    finally:
        app_cm.__exit__(None, None, None)
    ok = sum(1 for r in results if r[1])
    print(f"UI checks: {ok}/{len(results)} passed, {len(loads)} page loads, {time.time() - t0:.0f} s; screenshots in {out}")
    print("ALL PASS" if ok == len(results) else "SOME UI CHECKS FAILED")
    return 0 if ok == len(results) else 1
