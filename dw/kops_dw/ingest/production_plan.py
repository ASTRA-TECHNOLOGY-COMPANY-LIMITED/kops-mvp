"""PRODUCTION PLAN: one sheet per factory, one row per style (from row 7), bilingual header in rows 5-6.

Title in A1: '27SS [DHG BPK-HAGACO]  PRODUCTION PLAN' or '27SS [NEPA - GIA NGUYEN] PRODUCTION PLAN'
-> season, customer/brand tokens, factory. The plan date sits right of the 'DATE' cell in row 1.
Columns are found by their row-5 label (KR/EN) so the parser survives inserted columns.
BAL (column 'BUYER DEL', sub-label 'BAL / ETA+2') = RDD - (ETA Incheon + N days); it is recomputed and
compared so that a broken formula is reported instead of trusted.
"""
from __future__ import annotations

import datetime as dt
import re

from .. import config
from ..util import norm_key, text, to_date, to_int
from .order_recap_generic import brand_of, customer_of, factory_of

TITLE_RE = re.compile(r"(2\d)\s?(SS|FW)\s*\[([^\]]+)\]")
FIELDS = [  # (output column, row-5 label fragments (any), exact?)
    ("line_worker", ["LINE / WORKER", "LINE/WORKER"]),
    ("file_no", ["FILE NO"]),
    ("style_no", ["STYLE"]),
    ("item", ["ITEM"]),
    ("qty", ["Q'TY", "QTY"]),
    ("daily_target", ["DAILY & TARGET", "DAILY&TARGET"]),
    ("work_days", ["DETAIL"]),
    ("fabric_etd", ["원단 선적"]),
    ("accs_etd", ["부자재 선적"]),
    ("accs_eta_factory", ["부자재 공장도착"]),
    ("cut_plan", ["재단 예정"]),
    ("input_plan", ["투입 예정"]),
    ("finish_plan", ["완료 예정"]),
    ("exf_plan", ["A)"]),
    ("etd_plan", ["B)"]),
    ("eta_plan", ["C)"]),
    ("due_etd", ["D)"]),
    ("due_eta", ["E)"]),
    ("rdd", ["F)"]),
    ("bal_days", ["BUYER DEL"]),
    ("actual_exf", ["EXF-FACT"]),
]
DATE_FIELDS = {"fabric_etd", "accs_etd", "accs_eta_factory", "cut_plan", "input_plan", "finish_plan", "exf_plan",
               "etd_plan", "eta_plan", "due_etd", "due_eta", "rdd", "actual_exf", "actual_etd", "actual_eta"}


def _date(v):
    if isinstance(v, dt.datetime):
        return to_date(v)
    return to_date(v)


def parse(wb, season_hint, ctx, file_name: str = "", rel_path: str = ""):
    rows, as_of_max, fams = [], None, set()
    for ws in wb.worksheets:
        title = text(ws.cell(1, 1).value) or ""
        m = TITLE_RE.search(norm_key(title))
        if not m:
            ctx.issue("INFO", "PLAN_SHEET_SKIPPED", ws.title, f"No '<season> [..] PRODUCTION PLAN' title: '{title[:40]}'")
            continue
        season = f"{m.group(1)}{m.group(2)}"
        inner = m.group(3)
        left, _, fac_txt = inner.rpartition("-")
        if not left:
            left, fac_txt = inner, ws.title
        fac_code, fac_raw, _ = factory_of(fac_txt.strip())
        if not fac_code:
            fac_code, fac_raw, _ = factory_of(ws.title)
        tokens = norm_key(left).split()
        customer = customer_of(left, file_name) or customer_of(rel_path)
        brand = next((config.BRAND_ALIASES[t] for t in tokens if t in config.BRAND_ALIASES), None) or \
            next((t for t in tokens if t not in ("DHG", "KOFA", "JBEE", "DKM")), None)
        brand = brand_of(brand)
        as_of = None
        for c in range(1, min(ws.max_column, 40) + 1):
            if norm_key(ws.cell(1, c).value) == "DATE":
                as_of = to_date(ws.cell(1, c + 1).value)
                break
        as_of_max = max(filter(None, [as_of_max, as_of]), default=None)
        h5 = {c: norm_key(ws.cell(5, c).value) for c in range(1, min(ws.max_column, 40) + 1) if ws.cell(5, c).value}
        h6 = {c: norm_key(ws.cell(6, c).value) for c in range(1, min(ws.max_column, 40) + 1) if ws.cell(6, c).value}
        col = {}
        for out, labels in FIELDS:
            for c, v in h5.items():
                if any(v.startswith(norm_key(l)) if l.endswith(")") else norm_key(l) in v for l in labels):
                    if out == "style_no" and v != "STYLE":
                        continue
                    col.setdefault(out, c)
        # actual ETD / ETA: plain 'ETD' / 'ETA' labels right of EXF-FACT
        for c, v in h5.items():
            if v in ("ETD", "ETA") and c > col.get("actual_exf", 99):
                col.setdefault("actual_" + v.lower(), c)
        c_rmk = next((c for c, v in h6.items() if "비고" in v), None)
        bal_label = h6.get(col.get("bal_days"), "")
        m_off = re.search(r"ETA\s*\+\s*(\d+)", bal_label)
        bal_offset = int(m_off.group(1)) if m_off else 2
        if "style_no" not in col:
            ctx.issue("WARN", "PLAN_NO_STYLE_COL", ws.title, "STYLE column not found in row 5")
            continue
        empty = 0
        for r in range(7, ws.max_row + 1):
            style = text(ws.cell(r, col["style_no"]).value)
            if not style:
                empty += 1
                if empty >= 3:
                    break
                continue
            empty = 0
            rec = dict(customer=customer, brand=brand, season=season, factory_code=fac_code, factory_raw=fac_raw,
                       sheet=ws.title, row_no=r, as_of=as_of, style_no=norm_key(style), bal_offset=bal_offset,
                       remark=text(ws.cell(r, c_rmk).value) if c_rmk else None)
            for out, _ in FIELDS + [("actual_etd", None), ("actual_eta", None)]:
                if out == "style_no" or out not in col:
                    continue
                v = ws.cell(r, col[out]).value
                if out in DATE_FIELDS:
                    rec[out] = _date(v)
                    if rec[out] is None and text(v):
                        rec[out + "_txt"] = text(v)
                elif out in ("qty", "bal_days"):
                    rec[out] = to_int(v)
                elif out in ("daily_target", "work_days"):
                    rec[out] = float(v) if isinstance(v, (int, float)) else None
                else:
                    rec[out] = (norm_key(v) or None) if out == "file_no" else text(v)
            if rec.get("rdd") and rec.get("eta_plan"):
                rec["bal_calc"] = (rec["rdd"] - (rec["eta_plan"] + dt.timedelta(days=bal_offset))).days
                if rec.get("bal_days") is not None and rec["bal_calc"] != rec["bal_days"]:
                    ctx.issue("WARN", "PLAN_BAL_MISMATCH", rec["style_no"],
                              f"BAL in file {rec['bal_days']} vs recomputed {rec['bal_calc']}", f"{ws.title}!R{r}")
            yy = 2000 + int(season[:2])
            for f in ("cut_plan", "input_plan", "finish_plan", "exf_plan", "rdd"):
                d = rec.get(f)
                if d and season.endswith("SS") and not ((yy - 1, 6) <= (d.year, d.month) <= (yy, 9)):
                    ctx.issue("WARN", "DATE_OUT_OF_SEASON", rec["style_no"], f"{f} {d} outside season {season}",
                              f"{ws.title}!R{r}")
            rows.append(rec)
            fams.add(f"{customer or '?'}|{brand or '?'}")
    family = "/".join(sorted(fams)) or None
    return dict(production_plan=rows), as_of_max, family
