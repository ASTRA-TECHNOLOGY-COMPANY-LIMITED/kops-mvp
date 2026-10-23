"""Third-party inspection data (M1-12, analys-docs/review_qc_third_party.md): INSPECTION/THIRD_PARTY/INPUT DATA.xlsx.

Sheet DATA: one inspection = one row with ORDER Q'TY / INSPECTION Q'TY / PASS / DEFECT QTY, followed by rows that only
add a defect code (their information columns hold '-'). Every row (the first one too) carries CODE + MINOR + MAJOR.
Sheet CODE: defect codes A01.. with Korean names; group = first letter (A-G).
The inspection result is not a column: REMARK 'REJECT ...' -> REJECT, otherwise PASS (assumption ASM-QC-02, Q25).
DEFECT QTY counts defect points; the rate is defects / inspected (ASM-QC-01, Q24). An inspection whose code counts do
not add up to DEFECT QTY is reported (QC_DEFECT_SUM_MISMATCH). The QC NAME column (inspectors) is never read.
"""
from __future__ import annotations

from ..util import norm_key, text, to_date, to_int

COLS = {"LOCATION": "location", "STYLE NO.": "style_no", "PO/ COLOR": "po_color", "SHIP TO": "ship_to",
        "NUMBER ORDER": "round_no", "ITEM": "item", "BRAND": "brand", "VENDOR": "vendor", "FACTORY": "factory_raw",
        "INSPECTION DATE": "inspect_date", "PRE-FINAL": "pre_final", "ORDER Q'TY": "order_qty",
        "INSPECTION Q'TY": "inspected_qty", "PASS": "pass_qty", "DEFECT QTY": "defect_qty", "CODE": "code",
        "MINOR": "minor", "MAJOR": "major", "DEFECT RATE": "defect_rate_file", "REMARK": "remark"}


def _n(v):
    return None if isinstance(v, str) and v.strip() in ("-", "") else to_int(v)


def parse(wb, season, ctx, file_name: str = ""):
    ws = wb["DATA"]
    it = ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True)
    header = [norm_key(v) for v in next(it)]
    col = {COLS[h]: i for i, h in enumerate(header) if h in COLS}
    inspections, defects, cur, seq = [], [], None, 0
    for r, row in enumerate(it, start=2):
        row = list(row) + [None] * 25
        g = lambda k: row[col[k]] if k in col else None           # noqa: E731
        if _n(g("order_qty")) is not None or _n(g("inspected_qty")) is not None:
            seq += 1
            remark = text(g("remark"))
            cur = dict(inspection_no=seq, row_no=r, location=text(g("location")), style_no=norm_key(g("style_no")) or None,
                       po_color=text(g("po_color")), ship_to=text(g("ship_to")), round_no=_n(g("round_no")),
                       item=text(g("item")), brand=norm_key(g("brand")) or None, vendor=norm_key(g("vendor")) or None,
                       factory_raw=text(g("factory_raw")), inspect_date=to_date(g("inspect_date")),
                       pre_final=text(g("pre_final")), order_qty=_n(g("order_qty")), inspected_qty=_n(g("inspected_qty")),
                       pass_qty=_n(g("pass_qty")), defect_qty=_n(g("defect_qty")), remark=remark,
                       result="REJECT" if remark and "REJECT" in remark.upper() else "PASS")
            inspections.append(cur)
        if cur is None:
            continue
        code = norm_key(g("code"))
        if code:
            defects.append(dict(inspection_no=cur["inspection_no"], row_no=r, code=code, minor=_n(g("minor")) or 0,
                                major=_n(g("major")) or 0))
    points = {}
    for d in defects:
        points[d["inspection_no"]] = points.get(d["inspection_no"], 0) + d["minor"] + d["major"]
    bad = [i for i in inspections if i["defect_qty"] is not None and points.get(i["inspection_no"], 0) != i["defect_qty"]]
    if bad:
        ctx.issue("WARN", "QC_DEFECT_SUM_MISMATCH", "DATA", f"{len(bad)} inspection(s): code counts do not add up to "
                  f"DEFECT QTY (first at row {bad[0]['row_no']})", "DATA")
    codes = []
    if "CODE" in wb.sheetnames:
        for r, row in enumerate(wb["CODE"].iter_rows(min_row=1, max_col=2, values_only=True), start=1):
            c = norm_key(row[0])
            if c and len(c) == 3 and c[0] in "ABCDEFG" and c[1:].isdigit():
                codes.append(dict(code=c, name_ko=text(row[1]), code_group=c[0], row_no=r))
    dates = [i["inspect_date"] for i in inspections if i["inspect_date"]]
    return dict(qc_inspection=inspections, qc_defect=defects, defect_code=codes), (max(dates) if dates else None)
