"""ORDER RECAP of customers other than CHALLENGER (DHG / 8 SECONDS, Beanpole Kids, XEXYMIX, JBEE, KOFA, DKM / MIZUNO).

Same template family as CHALLENGER (legend in rows 1-2, header in rows 3-4, one block of rows per style
starting with a number in column B) but the columns move between customers, so everything is located by
header label, never by position:
  row 3: Brand, S/NO, FILE NO, COLOR, ORDER Q'TY, ETD VIET, RDD KOREA / ETA KOREA
  row 4: BUYER, ITEM, FACT, KOREA ... TTL, GROSS TTL / GRAND TTL, 'RDD (-20DAY)' (the ETD rule), ACTUAL RDD
The factory is either in the FACT column on the first block row (JBEE, KOFA, MIZUNO) or on the last block row
of column E (DHG). The sheet DETAIL (when present) is only used to confirm cancellations: it is a summary with
formulas that break when rows are inserted (seen in BPK 261021).
"""
from __future__ import annotations

import re

from .. import config
from ..excel import fill_key
from ..util import norm_key, text, to_date, to_int

BLOCK_START_RE = re.compile(r"^\d{1,3}[A-Z]?$")
CANCEL_RE = re.compile(r"\bCANC(?:EL|LE|ED|ELED)?\b|MOVE TO CHINA", re.I)
SEASON_RE = re.compile(r"\b(2\d)\s?(SS|FW)\b")
LEGEND_WORDS = ("NOT FIXED", "ON PRODUCTION", "KOREA SHIP OUT", "UPDATE", "FIXED PRICE", "SEWING FINISHED",
                "CANCEL", "PENDING STYLE", "MOVE TO CHINA", "TARGET RDD")


def _hdr(ws, row: int) -> dict[int, str]:
    return {c: norm_key(ws.cell(row, c).value) for c in range(1, min(ws.max_column, 80) + 1)
            if ws.cell(row, c).value not in (None, "")}


def _find(h: dict[int, str], *labels, exact=False):
    for c, v in h.items():
        for lab in labels:
            if (v == lab) if exact else (lab in v):
                return c
    return None


def _main_sheet(wb):
    for ws in wb.worksheets:
        if "RECAP" in norm_key(ws.title) and ws.sheet_state == "visible":
            return ws
    return wb.worksheets[0]


def customer_of(*texts) -> str | None:
    blob = " ".join(norm_key(t) for t in texts if t)
    for key, code in config.CUSTOMER_KEYS:
        if key in blob:
            return code
    return None


def brand_of(raw) -> str | None:
    k = norm_key(raw)
    return config.BRAND_ALIASES.get(k, k or None)


def factory_of(raw):
    """Return (factory_code or None, raw text or None, is_cancel)."""
    t = text(raw)
    if not t:
        return None, None, False
    first = t.split("\n")[0].strip()
    if CANCEL_RE.search(first):
        return None, first, True
    k = norm_key(re.sub(r"^\d{6}\s*", "", first))
    if not re.search(r"[A-Z]", k) or k.startswith("#") or len(k) < 2:
        return None, None, False             # ',', '0', '#N/A' and other formula leftovers
    if k in config.FACTORY_ALIASES:
        return config.FACTORY_ALIASES[k], first, False
    return None, first, False


def _legend(ws) -> dict:
    out = {}
    for r in (1, 2):
        for c in range(1, min(ws.max_column, 60) + 1):
            label = norm_key(ws.cell(r, c).value)
            if label and any(w in label for w in LEGEND_WORDS):
                f = fill_key(ws.cell(r, c))
                if f:
                    out[f] = "CANCEL" if CANCEL_RE.search(label) else label
    return out


def _detail(wb):
    """(cancelled keys, {style/file no -> factory}) from the DETAIL summary sheet, when it has a FACTORY column."""
    cancels, factories = set(), {}
    if "DETAIL" not in wb.sheetnames:
        return cancels, factories
    ws = wb["DETAIL"]
    c_fac = keys = None
    for r in range(1, min(ws.max_row, 400) + 1):
        vals = [text(ws.cell(r, c).value) or "" for c in range(1, min(ws.max_column, 30) + 1)]
        if c_fac is None and "FACTORY" in [norm_key(v) for v in vals]:
            hdr = [norm_key(v) for v in vals]
            c_fac = hdr.index("FACTORY")
            keys = [i for i, v in enumerate(hdr) if v in ("STYLE NO", "FILE NO")]
            continue
        if any(CANCEL_RE.search(v) for v in vals):
            cancels.update(norm_key(v) for v in vals[:6] if v)
        if c_fac is not None:
            code, raw, _ = factory_of(vals[c_fac])
            if code:
                for i in keys:
                    if vals[i]:
                        factories[norm_key(vals[i])] = code
    return cancels, factories


CODE_RE = re.compile(r"[A-Z0-9][A-Z0-9-]{3,}")
ALIAS_RE = re.compile(r"\(=\s*([A-Z0-9-]+)")
FILE_NO_RE = re.compile(r"^[A-Z0-9]{1,6}[)\-][A-Z0-9\-]{3,}$")


def split_style(raw: str):
    """'32YA7B00 (=32YA7B01) (=32MK7B00)' -> ('32YA7B00', '32YA7B01,32MK7B00');
    '1BYHDMW901M (KOR PO)\n7BYETMW003M (GER PO)' -> ('1BYHDMW901M', '7BYETMW003M')."""
    up = norm_key(raw.replace("\n", " "))
    codes = CODE_RE.findall(up)
    if not codes:
        return up, None
    main = codes[0]
    aliases = ALIAS_RE.findall(up) + [c for c in codes[1:] if re.search(r"\d{3}", c) and len(c) >= 7]
    aliases = [a for a in dict.fromkeys(aliases) if a != main]
    return main, (",".join(aliases) or None)


def _in_season(d, season: str) -> bool:
    yy = 2000 + int(season[:2])
    if season.endswith("SS"):
        return (yy - 1, 7) <= (d.year, d.month) <= (yy, 9)
    return (yy, 1) <= (d.year, d.month) <= (yy + 1, 3)


def parse(wb, season_hint: str | None, ctx, file_name: str = "", rel_path: str = ""):
    ws = _main_sheet(wb)
    title = text(ws.cell(1, 2).value) or text(ws.cell(1, 1).value) or ""
    m = SEASON_RE.search(norm_key(title))
    season = f"{m.group(1)}{m.group(2)}" if m else season_hint
    if not season:
        raise ValueError("Season not found in sheet title or file name")
    if season_hint and m and season != season_hint:
        ctx.issue("WARN", "SEASON_NAME_MISMATCH", file_name,
                  f"File name says {season_hint}, sheet title says {season} (title wins)", f"{ws.title}!B1")
    customer = customer_of(title, file_name) or customer_of(rel_path)
    if not customer:
        ctx.issue("WARN", "CUSTOMER_UNKNOWN", file_name, "Customer not recognised from title, file name or folder")
    report_date = to_date(ws.cell(2, 4).value)

    h3, h4 = _hdr(ws, 3), _hdr(ws, 4)
    c_brand = _find(h3, "BRAND") or 3
    c_style = _find(h3, "S/NO", exact=True) or 4
    c_file = _find(h3, "FILE NO")
    c_fact = c_file if (c_file and "FACT" in h4.get(c_file, "")) else None
    if c_fact:
        c_file = None                       # JBEE / KOFA / MIZUNO: column E is the factory, no file no column
    c_color = _find(h3, "COLOR", exact=True)
    c_qty = _find(h4, "GROSS TTL", "GRAND TTL")
    c_first_qty = _find(h3, "ORDER Q'TY", "ORDER QTY")
    c_etd = _find(h3, "ETD VIET")
    c_rdd = _find(h3, "RDD KOREA", "ETA KOREA")
    etd_rule = text(ws.cell(4, c_etd).value) if c_etd else None
    if c_etd and (not etd_rule or "RDD" not in norm_key(etd_rule)):
        etd_rule = text(ws.cell(3, c_etd).value)
    if c_rdd and "ETD" in norm_key(ws.cell(3, c_rdd).value) and "RDD" not in norm_key(etd_rule):
        etd_rule = text(ws.cell(3, c_rdd).value)          # MIZUNO: 'ETA KOREA (etd +10)'
    etd_rule = re.sub(r"\s+", " ", etd_rule).strip() if etd_rule else None
    legend = _legend(ws)
    detail_cancel, detail_factory = _detail(wb)

    starts = [r for r in range(5, ws.max_row + 1)
              if BLOCK_START_RE.match(str(ws.cell(r, 2).value or "").strip()) and text(ws.cell(r, c_style).value)]
    rows, seen = [], set()
    for i, s in enumerate(starts):
        last = min((starts[i + 1] - 1) if i + 1 < len(starts) else s + 7, s + 11)
        style_raw = text(ws.cell(s, c_style).value)
        style_no, aliases = split_style(style_raw)
        file_no = text(ws.cell(s, c_file).value) if c_file else None
        if not file_no:                         # JBEE / MIZUNO: file no on the 4th block row of the style column
            cand = norm_key(text(ws.cell(s + 3, c_style).value))
            file_no = cand if FILE_NO_RE.match(cand or "") else None
        brand = brand_of(ws.cell(s, c_brand).value) or None
        if c_fact:
            fac_code, fac_raw, fac_cancel = factory_of(ws.cell(s, c_fact).value)
            if not fac_raw:
                fac_code, fac_raw, fac_cancel = factory_of(ws.cell(last, 5).value)
        else:
            fac_code, fac_raw, fac_cancel = factory_of(ws.cell(last, 5).value)
        if not fac_code and not fac_cancel:
            alt = detail_factory.get(style_no) or detail_factory.get(norm_key(file_no))
            if alt:
                fac_code, fac_raw = alt, fac_raw or f"(DETAIL) {alt}"
        q_cell = ws.cell(s, c_qty).value if c_qty else None
        qty = to_int(q_cell)
        qty_src = "TTL"
        if not qty and c_color and c_first_qty:     # KOFA: total cell empty/0, quantities typed as '1500P'
            vals = [to_int(ws.cell(r, c_first_qty).value) for r in range(s, last + 1) if text(ws.cell(r, c_color).value)]
            if any(v for v in vals if v):
                qty, qty_src = sum(v for v in vals if v), "SUM_COLORS"
                ctx.issue("INFO", "QTY_FROM_COLORS", style_no, f"Total cell '{q_cell}', summed colour rows = {qty}",
                          f"{ws.title}!{c_qty}:{s}")
        etd_cell = ws.cell(s, c_etd).value if c_etd else None
        rdd_cell = ws.cell(s, c_rdd).value if c_rdd else None
        etd, rdd = to_date(etd_cell), to_date(rdd_cell)
        fill = fill_key(ws.cell(s, c_style)) or fill_key(ws.cell(s, 2))
        status = legend.get(fill, "NO STATUS" if fill is None else "UNMAPPED")
        block_txt = " ".join(text(ws.cell(r, c).value) or "" for r in range(s, last + 1) for c in (2, 3, 4, 5))
        cancel = (status == "CANCEL" or fac_cancel or bool(CANCEL_RE.search(block_txt))
                  or style_no in detail_cancel or norm_key(file_no) in detail_cancel)
        if cancel:
            status = "CANCEL"
        for label, d, cell in (("ETD", etd, etd_cell), ("RDD", rdd, rdd_cell)):
            if d and not _in_season(d, season) and not cancel:
                ctx.issue("WARN", "DATE_OUT_OF_SEASON", style_no, f"{label} {d} outside season {season}",
                          f"{ws.title}!R{s}")
            elif d is None and text(cell):
                ctx.issue("WARN", "DATE_UNPARSED", style_no, f"{label} text '{text(cell)}'", f"{ws.title}!R{s}")
        if fac_raw and not fac_code and not fac_cancel:
            ctx.issue("INFO", "FACTORY_UNMAPPED", style_no, f"Factory text '{fac_raw}'", f"{ws.title}!E")
        key = (style_no, norm_key(file_no))
        if key in seen:
            ctx.issue("WARN", "DUPLICATE_STYLE_ROW", style_no, "Same style + file no twice in one file", f"{ws.title}!B{s}")
        seen.add(key)
        rows.append(dict(customer=customer, brand=brand, season=season, row_no=s, order_no=text(ws.cell(s, 2).value),
                         style_no=style_no, style_raw=style_raw, style_aliases=aliases, file_no=norm_key(file_no) or None,
                         factory_code=fac_code, factory_raw=fac_raw, order_qty=qty, qty_raw=text(q_cell),
                         qty_source=qty_src, etd=etd, etd_raw=text(etd_cell), rdd=rdd, rdd_raw=text(rdd_cell),
                         etd_rule=etd_rule, status_fill=fill, status_label=status, is_active=not cancel,
                         report_date=report_date, sheet=ws.title))
    brands = [r["brand"] for r in rows if r["brand"]]
    main_brand = max(set(brands), key=brands.count) if brands else None
    for r in rows:
        r["brand"] = r["brand"] or main_brand         # blank brand cell on a block -> brand of the file
    family = f"{customer or '?'}|{main_brand or '?'}"
    return dict(order_line_ext=rows), report_date, family
