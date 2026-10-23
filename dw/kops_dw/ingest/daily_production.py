"""Daily production report (M1-02, spec analys-docs/mvp_phase1_spec.md §3.1-3.2): one sheet per day, one workbook
per factory (each new file repeats the earlier days).

Header on two rows found by label, never by position: a group row (CUTTING, SEND PRINTING, RETURNED PRINTING, IN PUT,
OUT PUT) and a sub row (TODAY, TTL, BAL). CHALLENGER files have 47-48 columns with print / embroidery; HAGACO (DHG)
has 41, no print, plus FINAL ETD HAI PHONG / RDD / RMKS. The first row of a style carries style, line, workers, ETD,
RDD, colour; size rows follow; colour 'TTL' rows and rows without size are totals (not loaded, the 'GRAND TOTAL' row
is checked against the size rows). BAL columns are formulas and are not loaded.

Report date (§3.2): the date cell in a sheet is not trusted. The sheet name gives it: 'dd.mm' when any sheet of the
file starts above 12 (TBM), else 'm.d'; the year is the season's (SS: July-December are the year before); a date more
than 30 days before the previous sheet takes that sheet's month (REPORT_DATE_FIXED: TBM '13.01' after '12.10').
Sheets whose name is not a date are skipped (SHEET_SKIPPED); a date cell that differs from the name by more than one
day is reported (REPORT_DATE_CONFLICT). Excel error values become NULL (EXCEL_ERROR, one issue per sheet).
"""
from __future__ import annotations

import datetime as dt
import re

from .. import config
from ..util import norm_key, text, to_date, to_int
from .order_recap_generic import customer_of, factory_of

GROUPS = [("cut", ("CUTTING", "SL CAT")), ("print_send", ("SEND PRINT",)), ("print_return", ("RETURNED PRINT",)),
          ("input", ("IN PUT", "INPUT")), ("output", ("OUT PUT", "OUTPUT"))]
SHEET_RE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\s*$")
ERR_RE = re.compile(r"^#(REF!|DIV/0!|VALUE!|N/A|NAME\?|NUM!|NULL!)")
SIZE_ALIAS = {"XXL": "2XL", "XXXL": "3XL"}


def _sheet_dates(names: list[str], season: str, ctx) -> dict[str, dt.date]:
    parsed = {n: SHEET_RE.match(n) for n in names}
    dmy = any(m and int(m.group(1)) > 12 for m in parsed.values())
    yy = 2000 + int(season[:2])
    out = []
    for n, m in parsed.items():
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        day, month = (a, b) if dmy else (b, a)
        year = yy - 1 if season.endswith("SS") and month >= 7 else yy
        try:
            out.append((n, dt.date(year, month, day)))
        except ValueError:
            continue
    # the order of the sheets in the workbook is the order of the days (either way round)
    pos = {n: i for i, n in enumerate(names)}
    out.sort(key=lambda x: pos[x[0]])
    ups = sum(b[1] > a[1] for a, b in zip(out, out[1:]))
    if ups < (len(out) - 1) / 2:                 # newest sheet first (TRUONG PHUC, HAGACO)
        out.reverse()
    fixed, prev = {}, None
    for n, d in out:
        if prev and (prev - d).days > 30:
            try:
                nd = d.replace(month=prev.month, year=prev.year)
            except ValueError:
                nd = d
            ctx.issue("INFO", "REPORT_DATE_FIXED", n, f"Sheet '{n}' read as {d}, before {prev}: month typed wrong, "
                      f"taken as {nd}", n)
            d = nd
        fixed[n] = d
        prev = d
    return fixed


def _header(rows) -> tuple[int, dict] | None:
    for i, row in enumerate(rows[:10]):
        labels = [norm_key(v) for v in row]
        if any(lab.startswith("S/NO") for lab in labels) and any(lab == "SIZE" for lab in labels):
            return i, labels
    return None


def _columns(labels: list[str], sub: list[str]) -> dict:
    col = {}
    for c, lab in enumerate(labels):
        if lab.startswith("S/NO"):
            col.setdefault("style", c)
        elif lab.startswith("LINE NO"):
            col.setdefault("line", c)
        elif lab.startswith("WORKERS"):
            col.setdefault("workers", c)
        elif lab.startswith("FINAL ETD") or lab == "ETD":
            col.setdefault("etd", c)
        elif lab == "RDD":
            col.setdefault("rdd", c)
        elif lab.startswith("COLOR"):
            col.setdefault("color", c)
        elif lab == "SIZE":
            col.setdefault("size", c)
        elif lab.replace(" ", "").replace("/", "") in ("ORDERQTY",):
            col.setdefault("order", c)
        elif lab.startswith("RMKS"):
            col.setdefault("remark", c)
    starts = []
    for c, lab in enumerate(labels):
        for name, keys in GROUPS:
            if any(lab.startswith(k) for k in keys) and name not in [s[0] for s in starts]:
                starts.append((name, c))
    starts.sort(key=lambda x: x[1])
    for i, (name, c0) in enumerate(starts):
        c1 = starts[i + 1][1] if i + 1 < len(starts) else c0 + 3
        for c in range(c0, min(c1, len(sub))):
            s = sub[c]
            if s.startswith("TODAY"):
                col.setdefault(f"{name}_today", c)
            elif s.startswith("TTL"):
                col.setdefault(f"{name}_ttl", c)
    return col


def _num(v, errs):
    if isinstance(v, str) and ERR_RE.match(v.strip()):
        errs[0] += 1
        return None
    return to_int(v)


def parse(wb, season: str, ctx, file_name: str = ""):
    customer = customer_of(file_name) or "CHALLENGER"
    if not season:                               # 'DHG-HAGACO DAILY PRODUCTION REPORT': season in the sheet title
        first = wb[wb.sheetnames[0]].cell(1, 1).value
        m = re.search(r"(2\d)'?\s*(SS|FW)", norm_key(first))
        season = m.group(1) + m.group(2) if m else None
        if not season:
            raise ValueError("SEASON_UNKNOWN: no season in file name or sheet title")
    brand = config.VENDOR_BRAND.get(customer, customer)
    names = wb.sheetnames
    dates = _sheet_dates(names, season, ctx)
    rows_out, totals, factories = [], [], set()
    for name in names:
        ws = wb[name]
        if name not in dates:
            ctx.issue("INFO", "SHEET_SKIPPED", name, f"Sheet name '{name}' is not a date", name)
            continue
        rows = [list(r) for r in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=60, values_only=True)]
        hdr = _header(rows)
        if not hdr:
            ctx.issue("INFO", "SHEET_SKIPPED", name, "No header row with S/NO and SIZE", name)
            continue
        hi, labels = hdr
        sub = [norm_key(v) for v in rows[hi + 1]] if hi + 1 < len(rows) else []
        col = _columns(labels, sub)
        title = text(rows[0][0]) if rows and rows[0] else ""
        fac = factory_of(re.sub(r"^\s*\d{2}'?\s*(SS|FW)\s*-?", "", norm_key(title)).strip(" -"))[0] or \
            factory_of(_paren_factory(file_name))[0]
        factories.add(fac)
        cell_date = to_date(rows[1][2]) if len(rows) > 1 and len(rows[1]) > 2 else None
        rdate = dates[name]
        if isinstance(rows[1][2] if len(rows) > 1 and len(rows[1]) > 2 else None, dt.datetime) and cell_date and \
                abs((cell_date - rdate).days) > 1:
            ctx.issue("INFO", "REPORT_DATE_CONFLICT", name, f"Date cell {cell_date} vs sheet name {rdate}", f"{name}!C2")
        errs, cur = [0], {}
        for r in range(hi + 2, len(rows)):
            row = rows[r] + [None] * 60
            first = " ".join(norm_key(v) for v in row[:12] if v is not None)
            if "GRAND" in first:
                totals.append(dict(sheet=name, report_date=rdate, row_no=r + 1, factory_code=fac,
                                   order_qty=_num(row[col["order"]], errs) if "order" in col else None,
                                   output_ttl=_num(row[col["output_ttl"]], errs) if "output_ttl" in col else None))
                continue
            style_txt = text(row[col["style"]]) if "style" in col else None
            if style_txt:
                head, _, note = style_txt.partition("\n")
                code, _, variant = norm_key(head).partition("#")          # 8 SECONDS 'LEV-24059 #424939LYD'
                cur = dict(style_raw=code.strip(), style_variant=variant.strip() or None, style_note=text(note),
                           line_no=text(row[col.get("line", 59)]),
                           workers=to_int(row[col.get("workers", 59)]), etd=to_date(row[col.get("etd", 59)]),
                           rdd=to_date(row[col.get("rdd", 59)]), color=None)
            color = text(row[col["color"]]) if "color" in col else None
            if color:
                cur["color"] = norm_key(color)
            size = norm_key(row[col["size"]]) if "size" in col else ""
            if not cur.get("style_raw") or not size or cur.get("color") == "TTL" or norm_key(color) == "TTL":
                continue
            rec = dict(cur, customer=customer, brand=brand, season=season, factory_code=fac, report_date=rdate,
                       sheet=name, sheet_hidden=ws.sheet_state != "visible", row_no=r + 1,
                       size_code=SIZE_ALIAS.get(size, size), order_qty=_num(row[col["order"]], errs) if "order" in col else None)
            for g, _ in GROUPS:
                for k in ("today", "ttl"):
                    c = col.get(f"{g}_{k}")
                    rec[f"{g}_{k}"] = _num(row[c], errs) if c is not None else None
            rows_out.append(rec)
        if errs[0]:
            ctx.issue("INFO", "EXCEL_ERROR", name, f"{errs[0]} cell(s) with an Excel error value read as empty", name)
    fam = "/".join(sorted(f for f in factories if f)) or None
    last = max(dates.values(), default=None)
    return dict(daily_prod_row=rows_out, daily_prod_total=totals), last, fam


def _paren_factory(name: str) -> str:
    m = re.search(r"\(\s*[^()-]*-\s*([^()]+?)\s*\)", name) or re.search(r"DHG-([A-Z ]+?)\s+DAILY", name.upper())
    return re.sub(r"\bFACT\b", "", m.group(1)).strip() if m else ""
