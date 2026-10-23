"""PRODUCTION PLAN: one sheet per factory, one row per style, bilingual two-row header.

Title in A1: '27SS [DHG BPK-HAGACO]  PRODUCTION PLAN' or '26FW [ CHALLENGER - TAN BINH MINH ] …'
-> season, customer/brand tokens, factory. The plan date sits right of the 'DATE' cell in row 1.
Layouts seen (10/2026): header in rows 5-6 (DHG BPK, NEPA; FILE NO or SEASON in column C, sometimes an extra
'공장 출고일자 / EX-FACT' due column) or rows 9-10 below a status legend (CHALLENGER 26FW, MIZUNO 26FW). The header
row is the first row with 'STYLE' and 'Q'TY'; columns are found by their label in either header row, so the parser
survives inserted columns. Each file writes its own due rules under D) / E) / BAL ('RDD-14', 'RDD-3' or 'RDD-2',
'ETA+2' or 'ETA+1', 'ETD VN-ETD'): they are stored per row (due_etd_rule, due_eta_rule, bal_rule), not assumed.
BAL is recomputed with the file's own rule and compared, so a broken formula is reported instead of trusted.
A date that runs backwards by months against the previous step (cut 2026-12 -> due ETD 2026-02) is reported as
YEAR_SUSPECT, never corrected.
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
    ("cut_plan", ["재단 예정", "재단예정", "재단 에정"]),      # layouts write it with / without the space (and a typo)
    ("input_plan", ["투입 예정", "투입예정"]),
    ("finish_plan", ["완료 예정", "완료예정"]),
    ("exf_plan", ["A)"]),
    ("etd_plan", ["B)"]),
    ("eta_plan", ["C)"]),
    ("due_etd", ["D)"]),
    ("due_eta", ["E)"]),
    ("rdd", ["F)"]),
    ("bal_days", ["BUYER DEL", "납기차이"]),
    ("actual_exf", ["EXF-FACT"]),
    ("due_exf", ["공장 출고일자", "EX- F"]),
]
DATE_FIELDS = {"fabric_etd", "accs_etd", "accs_eta_factory", "cut_plan", "input_plan", "finish_plan", "exf_plan",
               "etd_plan", "eta_plan", "due_etd", "due_eta", "rdd", "actual_exf", "actual_etd", "actual_eta", "due_exf"}
RULE_RE = re.compile(r"(RDD|ETD|ETA)\s*([+-])\s*(\d+)")
# Plan steps in time order: a step months before the previous one is a typed year, not a plan.
STYLE_CELL_RE = re.compile(r"^(?=[A-Z0-9-]*[A-Z])(?=(?:[A-Z-]*\d){3})[A-Z0-9][A-Z0-9-]{4,}$")
G_TOTAL_RE = re.compile(r"^G\.\s*TOTAL\s*\((\d+)\s*STYLES?\)")
CHAIN = ["cut_plan", "input_plan", "finish_plan", "exf_plan", "etd_plan", "eta_plan"]


def _rule(label: str) -> str | None:
    """'DUE ETD / RDD-14 DAYS' -> 'RDD-14'; 'BAL / ETD VN-ETD' -> 'ETD VN-ETD'."""
    m = RULE_RE.search(label or "")
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    m = re.search(r"(ET[AD] VN\s*-\s*ET[AD])", label or "")
    return re.sub(r"\s+", "", m.group(1)).replace("VN-", " VN-") if m else None


def _bal_calc(rec: dict, rule: str | None) -> int | None:
    """BAL with the file's rule: ETA+N -> RDD - (ETA + N); ETD VN-ETD -> due ETD - planned ETD; ETA VN-ETA alike."""
    rule = rule or "ETA+2"
    if (m := RULE_RE.fullmatch(rule)) and m.group(1) == "ETA" and rec.get("rdd") and rec.get("eta_plan"):
        return (rec["rdd"] - (rec["eta_plan"] + dt.timedelta(days=int(m.group(2) + m.group(3))))).days
    if rule.startswith("ETD") and rec.get("due_etd") and rec.get("etd_plan"):
        return (rec["due_etd"] - rec["etd_plan"]).days
    if rule.startswith("ETA VN") and rec.get("due_eta") and rec.get("eta_plan"):
        return (rec["due_eta"] - rec["eta_plan"]).days
    return None


def _date(v):
    if isinstance(v, dt.datetime):
        return to_date(v)
    return to_date(v)


def _columns(ws, hr: int):
    """Column of each field from the two header rows hr / hr+1, and the file's due / BAL rules."""
    ncol = min(ws.max_column, 45)
    h5 = {c: norm_key(ws.cell(hr, c).value) for c in range(1, ncol + 1) if ws.cell(hr, c).value}
    h6 = {c: norm_key(ws.cell(hr + 1, c).value) for c in range(1, ncol + 1) if ws.cell(hr + 1, c).value}
    col = {}
    for out, labels in FIELDS:
        for c, v in [*h5.items(), *h6.items()]:
            if any(v.startswith(norm_key(l)) if l.endswith(")") else norm_key(l) in v for l in labels):
                if out == "style_no" and v != "STYLE":
                    continue
                col.setdefault(out, c)
    # actual ETD / ETA: plain 'ETD' / 'ETA' labels right of EXF-FACT
    for c, v in [*h5.items(), *h6.items()]:
        if v in ("ETD", "ETA") and c > col.get("actual_exf", 99):
            col.setdefault("actual_" + v.lower(), c)
    c_rmk = next((c for c, v in [*h6.items(), *h5.items()] if "비고" in v or v == "RMKS"), None)
    rules = {k: _rule(h6.get(col.get(f), "")) for k, f in (("due_etd_rule", "due_etd"), ("due_eta_rule", "due_eta"),
                                                            ("bal_rule", "bal_days"))}
    m_off = re.search(r"ETA\s*\+\s*(\d+)", rules["bal_rule"] or "")
    return col, rules, int(m_off.group(1)) if m_off else None, c_rmk


def _is_header(ws, r: int) -> bool:
    vals = [norm_key(v) for v in next(ws.iter_rows(min_row=r, max_row=r, max_col=45, values_only=True), ()) if v]
    return "STYLE" in vals and "ITEM" in vals and any("Q'TY" in v or v == "QTY" for v in vals)


def _header_row(ws) -> int | None:
    return next((r for r in range(1, 16) if _is_header(ws, r)), None)


def _sheet_totals(ws) -> dict:
    """Totals the sheet states itself: 'STYLES n / TOTAL Q'TY q' near the title, or a 'G.TOTAL (n STYLES)' row."""
    out = {}
    for row in ws.iter_rows(min_row=1, max_row=3, max_col=45, values_only=True):
        for i, v in enumerate(row):
            k = norm_key(v)
            if k in ("STYLES", "TOTAL Q'TY") and i + 1 < len(row) and to_int(row[i + 1]) is not None:
                out.setdefault("styles" if k == "STYLES" else "qty", to_int(row[i + 1]))
    return out


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
        for c in range(1, min(ws.max_column, 45) + 1):
            if norm_key(ws.cell(1, c).value) == "DATE":
                as_of = next((d for k in range(1, 5) if (d := to_date(ws.cell(1, c + k).value))), None)
                break
        as_of_max = max(filter(None, [as_of_max, as_of]), default=None)
        hr = _header_row(ws)
        if hr is None:
            ctx.issue("WARN", "PLAN_NO_STYLE_COL", ws.title, "No header row with STYLE and Q'TY in rows 1-15")
            continue
        col, rules, bal_offset, c_rmk = _columns(ws, hr)
        if "style_no" not in col:
            ctx.issue("WARN", "PLAN_NO_STYLE_COL", ws.title, f"STYLE column not found in row {hr}")
            continue
        totals, sheet_rows, bottom = _sheet_totals(ws), [], None
        empty, r = 0, hr + 1
        while r < ws.max_row and empty < 30:
            r += 1
            first = norm_key(ws.cell(r, 1).value)
            if m := G_TOTAL_RE.match(first):           # 'G.TOTAL (36 STYLES)' with the sheet total in Q'TY
                totals = dict(styles=int(m.group(1)), qty=to_int(ws.cell(r, col["qty"]).value) if "qty" in col else None)
                continue
            if _is_header(ws, r):                      # next block of the same sheet ('… / WINTER ORDER')
                hr = r
                col, rules, bal_offset, c_rmk = _columns(ws, hr)
                r += 1
                continue
            if first == "TOTAL" and "qty" in col:       # block subtotals; the last one is the sheet total
                bottom = to_int(ws.cell(r, col["qty"]).value)
                continue
            cell = norm_key(ws.cell(r, col["style_no"]).value)
            style, _, note = cell.partition(" ")         # 'CHF3WPT6745 (FAB ISSUE) BEFORE:400P', '32YA6F00 (=32MK0000)'
            if not STYLE_CELL_RE.match(style):          # empty, legend ('UNDER INPUTTING'), G.TTL rows
                empty += 0 if style else 1
                continue
            empty = 0
            remark = " | ".join(x for x in (text(ws.cell(r, c_rmk).value) if c_rmk else None, note) if x) or None
            rec = dict(customer=customer, brand=brand, season=season, factory_code=fac_code, factory_raw=fac_raw,
                       sheet=ws.title, row_no=r, as_of=as_of, style_no=style, bal_offset=bal_offset,
                       remark=remark, header_row=hr, **rules)
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
            rec["bal_calc"] = _bal_calc(rec, rules["bal_rule"])
            if rec["bal_calc"] is not None and rec.get("bal_days") is not None and rec["bal_calc"] != rec["bal_days"]:
                ctx.issue("WARN", "PLAN_BAL_MISMATCH", rec["style_no"],
                          f"BAL in file {rec['bal_days']} vs recomputed {rec['bal_calc']} ({rules['bal_rule'] or 'ETA+2'})",
                          f"{ws.title}!R{r}")
            prev = None
            for f in CHAIN + ["due_etd"]:
                d = rec.get(f)
                if f == "due_etd":
                    prev = ("cut_plan", rec.get("cut_plan")) if rec.get("cut_plan") else None
                if d and prev and (prev[1] - d).days > 120:
                    ctx.issue("WARN", "YEAR_SUSPECT", rec["style_no"], f"{f} {d} is {(prev[1] - d).days} days before "
                              f"{prev[0]} {prev[1]}: year typed wrong? (not corrected)", f"{ws.title}!R{r}")
                if d and f != "due_etd":
                    prev = (f, d)
            yy = 2000 + int(season[:2])
            for f in ("cut_plan", "input_plan", "finish_plan", "exf_plan", "rdd"):
                d = rec.get(f)
                if d and season.endswith("SS") and not ((yy - 1, 6) <= (d.year, d.month) <= (yy, 9)):
                    ctx.issue("WARN", "DATE_OUT_OF_SEASON", rec["style_no"], f"{f} {d} outside season {season}",
                              f"{ws.title}!R{r}")
            rows.append(rec)
            sheet_rows.append(rec)
            fams.add(f"{customer or '?'}|{brand or '?'}")
        n, q = len(sheet_rows), sum(x.get("qty") or 0 for x in sheet_rows)
        if bottom is not None and bottom != q:
            ctx.issue("WARN", "TOTAL_MISMATCH", ws.title, f"Last TOTAL row {bottom} pcs, rows give {q}", ws.title)
        if (totals.get("styles") not in (None, n)) or (totals.get("qty") not in (None, q)):
            ctx.issue("WARN", "TOTAL_MISMATCH", ws.title, f"Sheet states {totals.get('styles')} styles / "
                      f"{totals.get('qty')} pcs (title / G.TOTAL cells), rows give {n} / {q}", ws.title)
    family = "/".join(sorted(fams)) or None
    return dict(production_plan=rows), as_of_max, family
