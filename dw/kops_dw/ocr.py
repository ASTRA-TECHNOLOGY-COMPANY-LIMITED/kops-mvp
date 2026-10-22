"""OCR queue for scanned PDF pages (H-08): tesseract kor+vie+eng, only pages without a text layer.

The build never runs OCR (it would make every build slow). When a PDF email page has no text but carries an image,
the parser records the page in the OCR queue (etl.ocr_queue) and reports PDF_NO_TEXT as before. Then:
  python -m kops_dw ocr [--workers N] [--limit N]    OCR the queued pages of the last build
  python -m kops_dw                                  rebuild: only those PDFs are parsed again, with the OCR text
Text is cached per file content and page in build/cache/ocr/<sha256>/p0001.txt (+ .done when the file is complete),
so a page is never OCR'd twice (re-runs, parser changes, the same PDF under another name).
Needs `tesseract` (+ language data kor, vie) and `pdftoppm` (poppler):
  macOS: brew install tesseract tesseract-lang poppler     Ubuntu: apt install tesseract-ocr-kor tesseract-ocr-vie poppler-utils
Missing tools are reported by the `ocr` command; the build itself does not need them.
OCR text can contain recognition errors: emails read from it carry text_source='ocr'.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config
from .util import MissingTool

LANGS = ("kor", "vie", "eng")
DPI = 300


def cache_dir(digest: str) -> Path:
    return config.CACHE_DIR / "ocr" / digest


def is_done(digest: str) -> bool:
    return (cache_dir(digest) / ".done").exists()


def cached_page(digest: str, page: int) -> str | None:
    f = cache_dir(digest) / f"p{page:04d}.txt"
    return f.read_text(encoding="utf-8") if f.exists() else None


def tools() -> tuple[str, str, str]:
    """-> (tesseract, pdftoppm, '+'-joined languages) or raises MissingTool with install hints."""
    tess, ppm = shutil.which("tesseract"), shutil.which("pdftoppm")
    if not tess or not ppm:
        missing = [n for n, p in (("tesseract", tess), ("pdftoppm (poppler)", ppm)) if not p]
        raise MissingTool(f"{', '.join(missing)} not installed: macOS `brew install tesseract tesseract-lang poppler`;"
                          " Ubuntu `apt install tesseract-ocr-kor tesseract-ocr-vie poppler-utils`")
    out = subprocess.run([tess, "--list-langs"], capture_output=True, text=True).stdout.split()
    langs = [lang for lang in LANGS if lang in out]
    if not langs:
        raise MissingTool("tesseract has none of the kor / vie / eng language data (brew install tesseract-lang)")
    return tess, ppm, "+".join(langs)


def ocr_page(pdf: Path, digest: str, page: int, tess: str, ppm: str, langs: str) -> str:
    target = cache_dir(digest) / f"p{page:04d}.txt"
    if target.exists():
        return target.read_text(encoding="utf-8")
    env = dict(os.environ, OMP_THREAD_LIMIT="1")          # one core per page; pages run in parallel
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "page"
        subprocess.run([ppm, "-f", str(page), "-l", str(page), "-r", str(DPI), "-gray", "-png", "-singlefile",
                        str(pdf), str(img)], check=True, capture_output=True, timeout=300)
        res = subprocess.run([tess, str(img) + ".png", "stdout", "-l", langs], check=True, capture_output=True,
                             timeout=600, env=env)
    text = res.stdout.decode("utf-8", "replace")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmpf = target.with_suffix(".tmp")
    tmpf.write_text(text, encoding="utf-8")
    os.replace(tmpf, target)
    return text


def queue() -> list[dict]:
    """Pending pages of the last build (etl.ocr_queue)."""
    import duckdb
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        rows = con.execute("SELECT file_name, path, sha256, pages FROM etl.ocr_queue WHERE status = 'PENDING'").fetchall()
    finally:
        con.close()
    return [dict(file_name=f, path=Path(p), sha256=s, pages=[int(x) for x in pages.split(",")]) for f, p, s, pages in rows]


def run(argv) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="kops_dw ocr")
    ap.add_argument("--workers", type=int, default=config.WORKERS)
    ap.add_argument("--limit", type=int, help="at most N files this run (the rest stays queued)")
    a = ap.parse_args(argv)
    try:
        tess, ppm, langs = tools()
    except MissingTool as e:
        print(f"OCR not available: {e}")
        return 1
    if "kor" not in langs or "vie" not in langs:
        print(f"WARNING: OCR languages available: {langs} (kor and vie recommended)")
    items = [q for q in queue() if not is_done(q["sha256"])][:a.limit]
    jobs = [(q, p) for q in items for p in q["pages"]]
    if not jobs:
        print("OCR queue is empty.")
        return 0
    t0, done_pages, errors = time.time(), 0, []
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:      # threads: the work runs in subprocesses
        futs = {ex.submit(ocr_page, q["path"], q["sha256"], p, tess, ppm, langs): (q, p) for q, p in jobs}
        for f, (q, p) in futs.items():
            try:
                f.result()
                done_pages += 1
            except Exception as e:
                errors.append(f"{q['file_name']} p{p}: {type(e).__name__}: {e}"[:300])
    failed = {e.split(" p")[0] for e in errors}
    for q in items:
        if q["file_name"] not in failed:
            (cache_dir(q["sha256"]) / ".done").write_text(",".join(map(str, q["pages"])) + f"\n{langs}\n")
    print(f"OCR {done_pages} page(s) of {len(items)} file(s) in {time.time() - t0:.1f}s ({langs}); "
          f"{len(errors)} error(s). Run the build again to load the text.")
    for e in errors[:20]:
        print("  " + e)
    return 1 if errors else 0
