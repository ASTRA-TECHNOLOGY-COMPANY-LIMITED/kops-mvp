"""SHIPPING SCHEDULE (CHALLENGER, first seen 261015): the official export plan per style.

Sheets 'SHIPPING SCHEDULE' (styles still to ship) and 'SHIPPED STYLES' (done). Each sheet holds one block per
factory: a header row (NO | TYPE | STYLE NO | … | FACTORY | FIXED EX-FACT | FIXED ETD | FIXED ETA | SHIP MODE | RMKS),
style rows, then 'TOTAL N STYLES' with the block totals. Columns are found by their label. The block totals are
recomputed from the style rows and a difference is reported (TOTAL_MISMATCH), never used as data.
The plan date is the date cell right of 'KẾ HOẠCH XUẤT CHÍNH THỨC' in row 2.
"""
from __future__ import annotations

import re

from ..util import norm_key, text, to_date, to_int
from .order_recap_generic import factory_of

FIELDS = {  # output column -> header label (normalised, exact)
    "type": "TYPE", "style_no": "STYLE NO", "item": "ITEMS", "input_plan": "INPUT PLAN",
    "sewing_finish_plan": "SEWING FINISH PLAN", "order_qty": "ORDER Q'TY", "etd_vn": "ETD VN", "rdd": "RDD",
    "shipped_qty": "SHIPPED Q'TY", "ship_plan_qty": "SHIP(PLAN) Q'TY", "bal_qty": "BAL", "pcs_per_box": "PCS/BOX",
    "box_qty": "BOX Q'TY", "remark": "RMKS", "factory_raw": "FACTORY", "fixed_exfact": "FIXED EX-FACT",
    "fixed_etd": "FIXED ETD", "fixed_eta": "FIXED ETA", "ship_mode": "SHIP MODE",
}
DATES = {"input_plan", "sewing_finish_plan", "etd_vn", "rdd", "fixed_exfact", "fixed_etd", "fixed_eta"}
QTYS = {"order_qty", "shipped_qty", "ship_plan_qty", "bal_qty"}
TOTAL_RE = re.compile(r"^TOTAL\s+(\d+)\s+STYLES?")


def parse(wb, season, ctx):
    rows, as_of = [], None
    for ws in wb.worksheets:
        status = "SHIPPED" if "SHIPPED" in norm_key(ws.title) else "TO_SHIP"
        grid = list(ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=min(ws.max_column, 30), values_only=True))
        for r, line in enumerate(grid[:4], start=1):
            for c, v in enumerate(line):
                if "KE HOACH XUAT" in norm_key(v):
                    as_of = as_of or next((d for v2 in line[c + 1:] if (d := to_date(v2))), None)
        col, block, block_rows = {}, 0, []
        for r, line in enumerate(grid, start=1):
            labels = [norm_key(v) for v in line]
            if "STYLE NO" in labels and "ORDER Q'TY" in labels:
                col, block, block_rows = {}, block + 1, []
                for c, lab in enumerate(labels):
                    for out, want in FIELDS.items():
                        if lab == want and out not in col:
                            col[out] = c
                    if lab == "RMKS" and col.get("remark") not in (None, c):
                        col["remark2"] = c
                continue
            if not col:
                continue
            first = norm_key(line[col["type"]]) if "type" in col else ""
            if m := TOTAL_RE.match(first):
                _check_total(ctx, ws.title, r, int(m.group(1)), line, col, block_rows)
                continue
            style = text(line[col["style_no"]]) if "style_no" in col else None
            if not style:
                continue
            rec = dict(sheet=ws.title, row_no=r, block_no=block, status=status, season=season, as_of=as_of,
                       style_no=norm_key(style))
            for out, c in col.items():
                if out == "style_no":
                    continue
                v = line[c] if c < len(line) else None
                if out in DATES:
                    rec[out] = to_date(v)
                    if rec[out] is None and text(v):
                        rec[out + "_txt"] = text(v)
                elif out in QTYS:
                    rec[out] = to_int(v)
                elif out in ("pcs_per_box", "box_qty"):
                    rec[out] = float(v) if isinstance(v, (int, float)) else None
                else:
                    rec[out] = text(v)
            # 'HH>>MTT', 'NATEXCO>FG BG >MTT (260922)': moved between factories; the last one ships
            last = re.sub(r"\(\d{6}\)", "", re.split(r">+", rec.get("factory_raw") or "")[-1]).strip()
            rec["factory_code"] = factory_of(last)[0]
            rec["factory_moved"] = ">" in (rec.get("factory_raw") or "")
            if rec["factory_raw"] and not rec["factory_code"]:
                ctx.issue("WARN", "UNKNOWN_FACTORY", last, f"Factory '{rec['factory_raw']}': '{last}' not in aliases",
                          f"{ws.title}!R{r}")
            rows.append(rec)
            block_rows.append(rec)
    for rec in rows:
        rec["as_of"] = as_of
    return dict(shipping_schedule=rows), as_of


def _check_total(ctx, sheet, r, n_styles, line, col, block_rows):
    if n_styles != len(block_rows):
        ctx.issue("WARN", "TOTAL_MISMATCH", f"{sheet} block", f"Total row says {n_styles} styles, block has "
                  f"{len(block_rows)}", f"{sheet}!R{r}")
    for f in ("order_qty", "shipped_qty", "ship_plan_qty"):
        shown = to_int(line[col[f]]) if f in col else None
        calc = sum(x.get(f) or 0 for x in block_rows)
        if shown is not None and shown != calc:
            ctx.issue("WARN", "TOTAL_MISMATCH", f"{sheet} {f}", f"Total row {shown} vs sum of styles {calc}",
                      f"{sheet}!R{r}")
