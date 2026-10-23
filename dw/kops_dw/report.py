"""PDF reports of the manager dashboard (E-06 / F-00), made on this machine only.

python -m kops_dw report --season 27SS --lang ko --out <dir> [--pages actions,overview] [--syn 0|1]

Starts the web app on 127.0.0.1 (random port, throw-away state DB, a temporary viewer session) in this process and
prints each page to PDF with headless Chromium through Playwright (print CSS: A4 landscape, data date, filters and the
synthetic-data label in the page header). The PDFs
contain KLMAS data: keep them on this machine / the KLMAS share, never in git or public links.
Chromium: KOPS_CHROME, else chromium / google-chrome on PATH (Docker image: Debian chromium), else Chrome on macOS.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import urlencode

from . import config

PAGES = ("actions", "overview")
MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def find_chrome() -> str | None:
    for c in (os.environ.get("KOPS_CHROME"), "chromium", "chromium-browser", "google-chrome", "google-chrome-stable", MAC_CHROME):
        if c and (shutil.which(c) or Path(c).is_file()):
            return shutil.which(c) or c
    return None


def _arg(argv: list[str], name: str, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def run(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright

    from app.local import local_app
    season, lang, out = _arg(argv, "--season"), _arg(argv, "--lang", "vi"), _arg(argv, "--out")
    pages = [p for p in _arg(argv, "--pages", ",".join(PAGES)).split(",") if p]
    syn = _arg(argv, "--syn")
    if not out or lang not in ("vi", "ko") or any(p not in PAGES for p in pages):
        print(__doc__.strip().splitlines()[2])
        return 2
    chrome = find_chrome()
    if not chrome:
        print("Chromium / Chrome not found: set KOPS_CHROME, or run inside the tools image (make report).")
        return 1
    if not (config.BUILD_DIR / "manager.html").exists():
        from .dashboard import render
        render()
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    with local_app("viewer") as app, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1060, "height": 750})
        ctx.add_cookies([app["cookie"]])
        page = ctx.new_page()
        for pg in pages:
            q = {"tab": pg, "lang": lang, "print": 1, "noanim": 1, "theme": "light", **({"season": season} if season else {}),
                 **({"syn": syn} if syn in ("0", "1") else {})}
            pdf = out_dir / f"kops_{pg}_{season or 'default'}_{lang}.pdf"
            page.goto(f"{app['url']}/?{urlencode(q)}")
            page.wait_for_selector("body[data-load-ms]", timeout=30000)
            page.emulate_media(media="print")
            page.wait_for_timeout(300)
            page.pdf(path=str(pdf), format="A4", landscape=True, print_background=True, prefer_css_page_size=True)
            if not pdf.is_file() or pdf.stat().st_size < 2000:
                print(f"FAILED {pg}: no PDF")
                return 1
            made.append(pdf)
            print(f"{pdf} ({pdf.stat().st_size / 1e3:.0f} kB)")
        browser.close()
    print(f"{len(made)} PDF(s); they contain KLMAS data, keep them local")
    return 0
