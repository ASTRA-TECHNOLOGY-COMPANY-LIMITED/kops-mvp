"""KLMAS inspection tracker (M1-06, spec analys-docs/mvp_phase1_spec.md §3.3): one sheet per factory ('TP ', 'HÀ HIẾU',
'FG', 'NATEXCO', 'MTTD'; hidden 'TP (2)'..'(5)' are earlier rounds, all loaded).

Row 2 is the header (FILE NO, STYLE NO, COLOR, QUANTITY ORDER, CUT QTY, OUT PUT QTY, DAILY INSPECTION ..., TTL KLMAS PASS,
SHIPPED OUT, Remark), row 3 the inspection dates under the daily columns. A style row ('CHF4WJK6801\\n- VEST -' = one
piece of a two-piece set) is followed by colour rows; a row without colour is the style subtotal (not loaded). At the
bottom, rows A-G per day: A passed, B pass / inspector, C inspected, D defects, E defect rate, F number of inspectors,
G inspector names. A, C, D and F are kept per factory and day; **G (names) is never read** (personal data).
'REQUEST ETD m/d' in the remark column becomes a change proposal (PENDING_REVIEW, source INSPECTION).
Defects (row D) are read as defect points and the rate as defects / inspected (assumption ASM-QC-01, question Q24).
"""
from __future__ import annotations

import datetime as dt
import re

from .. import config
from ..milestones import _md
from ..util import norm_key, text, to_date, to_int

PIECE_RE = re.compile(r"-\s*([A-Z ]+?)\s*-?\s*$")
REQUEST_RE = re.compile(r"REQUEST\s+ETD\s*[:.]?\s*(\d{1,2}/\d{1,2})", re.I)
TOTAL_ROWS = {"A": "passed_qty", "C": "inspected_qty", "D": "defect_qty", "F": "n_inspectors"}   # never G


def _factory(sheet: str) -> tuple[str | None, bool]:
    base = re.sub(r"\(\d+\)", "", sheet).strip()
    key = norm_key(base)
    return config.INSPECTION_SHEET_FACTORY.get(key) or config.FACTORY_ALIASES.get(key), "(" in sheet


def parse(wb, season, ctx, file_name: str = ""):
    cells, days, remarks = [], [], []
    for ws in wb.worksheets:
        fac, old_round = _factory(ws.title)
        if not fac:
            ctx.issue("WARN", "UNKNOWN_FACTORY", ws.title, f"Sheet '{ws.title}' is not a known factory", ws.title)
        grid = [list(r) + [None] * 5 for r in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=min(ws.max_column, 60),
                                                           values_only=True)]
        hdr = next((i for i, r in enumerate(grid[:6]) if "STYLE NO" in [norm_key(v) for v in r]), None)
        if hdr is None:
            ctx.issue("INFO", "SHEET_SKIPPED", ws.title, "No STYLE NO header", ws.title)
            continue
        labels = [norm_key(v) for v in grid[hdr]]
        col = {lab: c for c, lab in reversed(list(enumerate(labels))) if lab}
        c_style, c_color = col.get("STYLE NO"), col.get("COLOR")
        c_order = next((c for lab, c in col.items() if lab.startswith("QUANTITY ORDER")), None)
        c_ttl = next((c for lab, c in col.items() if lab.startswith("TTL KLMAS PASS")), None)
        c_remark = next((c for lab, c in col.items() if lab.startswith("REMARK")), None)
        dates = {c: d for c, v in enumerate(grid[hdr + 1]) if (d := to_date(v)) and isinstance(v, (dt.date, dt.datetime))}
        cur, piece = None, None
        for r in range(hdr + 2, len(grid)):
            row = grid[r]
            first = norm_key(row[0])
            if first in TOTAL_ROWS or first in ("B", "E", "G"):
                if first in TOTAL_ROWS:
                    for c, d in dates.items():
                        v = to_int(row[c])
                        if v is not None:
                            days.append(dict(sheet=ws.title, factory_code=fac, is_old_round=old_round, inspect_date=d,
                                             measure=TOTAL_ROWS[first], value=v, row_no=r + 1, col_no=c + 1))
                continue
            style_cell = text(row[c_style]) if c_style is not None else None
            if style_cell:
                head, _, rest = style_cell.partition("\n")
                cur = norm_key(head)
                m = PIECE_RE.search(norm_key(rest)) if rest else None
                piece = m.group(1).strip() if m else None
            color = norm_key(row[c_color]) if c_color is not None else ""
            if not cur or not color:
                continue                                  # style subtotal row
            order_qty = to_int(row[c_order]) if c_order is not None else None
            for c, d in dates.items():
                v = to_int(row[c])
                if v:
                    cells.append(dict(sheet=ws.title, factory_code=fac, is_old_round=old_round, style_no=cur, piece=piece,
                                      color=color, inspect_date=d, passed_qty=v, order_qty=order_qty, row_no=r + 1,
                                      col_no=c + 1))
            remark = text(row[c_remark]) if c_remark is not None else None
            if remark and (m := REQUEST_RE.search(remark)):
                last_day = max(dates.values(), default=None)
                remarks.append(dict(sheet=ws.title, factory_code=fac, style_no=cur, piece=piece, color=color,
                                    remark=remark[:300], request_etd=_md(m.group(1), last_day),
                                    ttl_pass=to_int(row[c_ttl]) if c_ttl is not None else None, row_no=r + 1))
    return dict(inspection_cell=cells, inspection_day=days, stg_inspection_remark=remarks), None
