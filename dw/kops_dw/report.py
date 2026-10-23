"""PDF reports of the manager dashboard (E-06), made on this machine only.

python -m kops_dw report --season 27SS --lang ko --out <dir> [--pages actions,overview] [--syn 0|1]

Starts the dashboard server on 127.0.0.1 (random port) in this process and prints each page to PDF with headless
Chromium (print CSS: A4 landscape, data date, filters and the synthetic-data label in the page header). The PDFs
contain KLMAS data: keep them on this machine / the KLMAS share, never in git or public links.
Chromium: KOPS_CHROME, else chromium / google-chrome on PATH (Docker image: Debian chromium), else Chrome on macOS.
"""
from __future__ import annotations

import functools
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import ThreadingHTTPServer
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


def start_server() -> tuple[ThreadingHTTPServer, int]:
    """Dashboard server on 127.0.0.1, random port, in a background thread (render first if needed)."""
    from .dashboard import _Handler, render
    if not (config.BUILD_DIR / "manager.html").exists():
        render()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Handler, directory=str(config.BUILD_DIR)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def run(argv: list[str]) -> int:
    season, lang, out = _arg(argv, "--season"), _arg(argv, "--lang", "vi"), _arg(argv, "--out")
    pages = [p for p in _arg(argv, "--pages", ",".join(PAGES)).split(",") if p]
    syn = _arg(argv, "--syn")
    if not out or lang not in ("vi", "ko") or any(p not in PAGES for p in pages):
        print(__doc__.strip().splitlines()[2])
        return 2
    chrome = find_chrome()
    if not chrome:
        print("Chromium / Chrome not found: set KOPS_CHROME, or run inside the Docker image (make report).")
        return 1
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    httpd, port = start_server()
    made = []
    try:
        with tempfile.TemporaryDirectory(prefix="kops-chrome-") as profile:
            for page in pages:
                q = {"tab": page, "lang": lang, "print": 1, "noanim": 1, "theme": "light", **({"season": season} if season else {}),
                     **({"syn": syn} if syn in ("0", "1") else {})}
                pdf = out_dir / f"kops_{page}_{season or 'default'}_{lang}.pdf"
                cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run", "--hide-scrollbars", "--window-size=1060,750",
                       f"--user-data-dir={profile}", "--no-pdf-header-footer", "--virtual-time-budget=15000",
                       f"--print-to-pdf={pdf}", f"http://127.0.0.1:{port}/?{urlencode(q)}"]
                subprocess.run(cmd, check=False, capture_output=True, timeout=180)
                if not pdf.is_file() or pdf.stat().st_size < 2000:
                    print(f"FAILED {page}: no PDF from {chrome}")
                    return 1
                made.append(pdf)
                print(f"{pdf} ({pdf.stat().st_size / 1e3:.0f} kB)")
    finally:
        httpd.shutdown()
    print(f"{len(made)} PDF(s); they contain KLMAS data, keep them local")
    return 0
