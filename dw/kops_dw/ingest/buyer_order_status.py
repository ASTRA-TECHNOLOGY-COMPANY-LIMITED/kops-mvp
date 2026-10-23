"""'DHG 생산계획표 · 오더 현황표' PDF printed by Daehan Global (8 SECONDS, BEANPOLE KIDS; first seen 2026-10-21).

The buyer's own view of the plan: per style FILE NO · STYLE, item, factory code (B85/HGC/SH/XT), qty, CUT / IN PUT /
FINISH, ETD 해상, ETA 인천, RDD (month-day), 납기 여유 (= RDD - ETA Incheon, days) and 상태. Kept for comparison only
(mart.plan_vs_buyer_view): the DW's plan numbers still come from KLMAS's PRODUCTION PLAN.
Read with pdftotext -layout (poppler). The header gives season and print date; a 'MM-DD' takes the year closest to
the print date. Each page states its total ('이 장 합계 20,300 pcs'), checked against the rows (TOTAL_MISMATCH).
The person who printed the page is not stored.
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
from pathlib import Path

from ..milestones import _md
from ..util import MissingTool, nfc, norm_key
from .order_recap_generic import factory_of

HEADER_RE = re.compile(r"·\s*(2\d(?:SS|FW))\s*·\s*(\d{4}-\d{2}-\d{2})\s*인쇄")
ROW_RE = re.compile(r"^\s*(?P<no>\d+)\s+(?P<file_no>[A-Z0-9][A-Z0-9-]*)\s*·\s*(?P<style>\S+)\s+(?P<item>.+?)\s{2,}"
                    r"(?P<fac>[A-Z0-9]{1,6})\s+(?P<qty>[\d,]+)\s+(?P<rest>.*)$")
DAY_RE = re.compile(r"^(?:\d{2}-\d{2}|-)$")
PAGE_TOTAL_RE = re.compile(r"이 장 합계\s*([\d,]+)\s*pcs")
BRANDS = {"8 SECONDS": "8 SECONDS", "8SECONDS": "8 SECONDS", "빈폴키즈": "BEANPOLE KIDS", "BEANPOLE KIDS": "BEANPOLE KIDS"}


def is_buyer_status(name: str) -> bool:
    n = nfc(name).replace(" ", "")
    return n.lower().endswith(".pdf") and (("오더" in n and "현황" in n) or "생산계획표" in n)   # '오더리캡 현황 · DHG 빈폴키즈'



def _pages(path: Path) -> list[str]:
    exe = shutil.which("pdftotext")
    if not exe:
        raise MissingTool("pdftotext (poppler) is needed to read buyer order status PDFs: brew install poppler")
    out = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, timeout=120, check=True)
    pages = nfc(out.stdout.decode("utf-8", "replace")).split("\f")
    return [p for p in pages if p.strip()]


def parse(path: Path, ctx):
    pages = _pages(path)
    brand = next((b for k, b in BRANDS.items() if k in nfc(path.name).upper() or k in nfc(path.name)), None)
    season = printed = None
    rows = []
    for pno, page in enumerate(pages, start=1):
        if m := HEADER_RE.search(page):
            season, printed = m.group(1), dt.date.fromisoformat(m.group(2))
        if not brand:
            first = norm_key(page.strip().splitlines()[0])
            brand = BRANDS.get(first)
        page_rows = []
        for ln in page.splitlines():
            m = ROW_RE.match(ln)
            if not m:
                continue
            rest = m.group("rest").split()
            days, k = [], 0
            while k < len(rest) and len(days) < 6 and DAY_RE.match(rest[k]):
                days.append(None if rest[k] == "-" else _md(rest[k].replace("-", ""), printed))
                k += 1
            days += [None] * (6 - len(days))
            tail = rest[k:]
            margin = int(tail[0][:-1]) if tail and re.fullmatch(r"[+-]\d+일", tail[0]) else None
            status = (" ".join(x for x in tail[1:] if x != "-") or None) if tail else None
            fac_code, fac_raw, _ = factory_of(m.group("fac"))
            rec = dict(page=pno, line_no=int(m.group("no")), brand=brand, season=season, printed_on=printed,
                       file_no=m.group("file_no"), style_no=m.group("style"), item=m.group("item").strip(),
                       factory_raw=fac_raw or m.group("fac"), factory_code=fac_code,
                       qty=int(m.group("qty").replace(",", "")), cut_plan=days[0], input_plan=days[1],
                       finish_plan=days[2], etd=days[3], eta=days[4], rdd=days[5], margin_days=margin, status=status)
            if rec["rdd"] and rec["eta"] and margin is not None and (rec["rdd"] - rec["eta"]).days != margin:
                ctx.issue("WARN", "MARGIN_MISMATCH", rec["file_no"], f"납기 여유 {margin} vs RDD - ETA "
                          f"{(rec['rdd'] - rec['eta']).days}", f"{path.name} p{pno}")
            page_rows.append(rec)
        if t := PAGE_TOTAL_RE.search(page):
            shown, calc = int(t.group(1).replace(",", "")), sum(r["qty"] for r in page_rows)
            if shown != calc:
                ctx.issue("WARN", "TOTAL_MISMATCH", f"page {pno}", f"Page total {shown} vs sum of rows {calc}",
                          f"{path.name} p{pno}")
        rows += page_rows
    for r in rows:
        r["brand"], r["season"] = r["brand"] or brand, r["season"] or season
    if not rows:
        ctx.issue("WARN", "NO_ROWS", path.name, "No style row recognised (layout changed?)", path.name)
    return dict(buyer_order_status=rows), printed, brand
