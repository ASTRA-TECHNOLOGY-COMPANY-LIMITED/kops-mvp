"""Production & Shipping Status: flat table, header on row 5, style rows grouped by factory with
'TOTAL n STYLES' subtotal rows (whose SUM ranges overlap - totals are never loaded, only checked)."""
from __future__ import annotations

import re

from ..util import norm_key, text, to_date, to_int

HEADER_ROW = 5
COLS = dict(order_no=1, mode=2, type=3, style_no=4, items=5, factory_raw=6, etd_vn=7, rdd=8, fpp_cfmd=9,
            inline_raw=10, top_smpl=11, order_qty=12, one_day=13, output_qty=14, inspected_qty=16,
            shipped_qty=18, logo_status=20, mtr_eta_raw=21, cutting_plan=23, input_plan=24,
            sewing_finish_plan=25, exfact_est=26, etd_est=27, eta_est=28)
DATE_COLS = {"etd_vn", "rdd", "fpp_cfmd", "cutting_plan", "input_plan", "sewing_finish_plan",
             "exfact_est", "etd_est", "eta_est", "top_smpl"}
INT_COLS = {"order_qty", "one_day", "output_qty", "inspected_qty", "shipped_qty"}


def parse(wb, season: str, ctx):
    ws = wb.worksheets[0]
    if norm_key(ws.cell(HEADER_ROW, 4).value) != "STYLE NO":
        raise ValueError("TEMPLATE_CHANGED: expected 'STYLE NO' in D5")
    as_of = to_date(ws.cell(1, 29).value)
    rows, totals = [], []
    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        style = norm_key(ws.cell(r, 4).value)
        label = norm_key(ws.cell(r, 2).value) or norm_key(ws.cell(r, 1).value)
        if not style:
            if label.startswith("TOTAL") or label.startswith("G.TTL"):
                totals.append(dict(row_no=r, label=label, factory_raw=text(ws.cell(r, 6).value),
                                   order_qty=to_int(ws.cell(r, 12).value), output_qty=to_int(ws.cell(r, 14).value),
                                   inspected_qty=to_int(ws.cell(r, 16).value), shipped_qty=to_int(ws.cell(r, 18).value)))
            continue
        if not re.match(r"^CH[A-Z0-9]{9,11}$", style):
            continue
        rec = dict(season=season, row_no=r, as_of=as_of)
        for k, c in COLS.items():
            v = ws.cell(r, c).value
            if k in DATE_COLS:
                d = to_date(v)
                rec[k] = d
                rec[k + "_txt"] = None if d or v is None else text(v)
            elif k in INT_COLS:
                rec[k] = to_int(v)
            else:
                rec[k] = text(v)
        rec["style_no"] = style
        rows.append(rec)
    computed = sum(x["order_qty"] or 0 for x in rows)
    for t in totals:
        if t["label"].startswith("G.TTL") and t["order_qty"] != computed:
            ctx.issue("ERROR", "TOTAL_MISMATCH", "G.TTL",
                      f"Grand total ORDER {t['order_qty']} != sum of style rows {computed} (overlapping SUM ranges)",
                      f"{ws.title}!L{t['row_no']}")
    return dict(production_status=rows, production_status_total=totals), as_of
