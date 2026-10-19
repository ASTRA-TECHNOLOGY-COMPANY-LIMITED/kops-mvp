"""Shipment Status: one sheet per factory, a grid of 11-column blocks per style.

Block layout (label column = c):
  title row      c: 'n) STYLE PRODUCTION DETAIL SHIP STATUS'
  header row     c: 'S/NO', c+1 'COLOR', c+2..c+7 size codes, c+8 'TTL'
  ORDER rows     c: "ORDER Q'TY" on the first one; colour in c+1, qty per size
  'S/DATE' row   order totals
  shipment rows  c: lot label '8/12ETD-8/18ETA SEA' on the first row of each lot
  'TOTAL SHIPPED Q'TY+SMPL QTY', 'SMPL LIST', "BAL Q'TY" rows (reconciliation only)
  sample rows    c: '8/8 SHIPPING SMPL', '7/31 PHOTO SMPL (SMPL ROOM)'
"""
from __future__ import annotations

import re

from ..config import SHIPMENT_SHEET_FACTORY
from ..util import md_date, norm_key, text, to_int

TITLE_RE = re.compile(r"^\s*(\d+)\)\s*(?:([A-Z0-9]{6,})\s+)?PRODUCTION", re.I)
LOT_RE = re.compile(r"(\d{1,2}/\d{1,2})\s*ETD\s*-?\s*(\d{1,2}/\d{1,2})\s*ETA\s*([A-Z]+)?", re.I)
SIZE_ALIAS = {"XXL": "2XL", "FREE": "F"}


def parse(wb, season: str, ctx):
    cells, blocks = [], []
    for ws in wb.worksheets:
        sheet_code = re.sub(r"\(\d+\)$", "", ws.title).strip()
        factory = SHIPMENT_SHEET_FACTORY.get(norm_key(sheet_code))
        if not factory:
            ctx.issue("WARN", "FACTORY_UNKNOWN", ws.title, "Sheet name not mapped to a factory", ws.title)
        titles = []
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and TITLE_RE.match(c.value):
                    titles.append((c.row, c.column))
        cols = sorted({c for _, c in titles})
        for (r0, c0) in titles:
            below = [r for r, c in titles if c == c0 and r > r0]
            r_end = min(below) - 1 if below else ws.max_row
            blocks_cells, meta = _parse_block(ws, r0, c0, r_end, season)
            m = TITLE_RE.match(ws.cell(r0, c0).value)
            style_raw = norm_key(m.group(2)) or None
            b = dict(sheet=ws.title, factory=factory, block_no=int(m.group(1)), style_no_raw=style_raw,
                     title_row=r0, title_col=c0, has_data=bool(blocks_cells), **meta)
            blocks.append(b)
            for x in blocks_cells:
                x.update(sheet=ws.title, factory=factory, block_no=b["block_no"], style_no_raw=style_raw)
            cells.extend(blocks_cells)
            if blocks_cells:
                _reconcile(b, blocks_cells, ctx, ws.title)
        _ = cols
    return dict(shipment_block=blocks, shipment_cell=cells), None


def _parse_block(ws, r0, c0, r_end, season):
    hdr = r0 + 1
    sizes = {}
    for k in range(2, 8):
        v = norm_key(ws.cell(hdr, c0 + k).value)
        if v:
            sizes[c0 + k] = SIZE_ALIAS.get(v, v)
    out, section, label = [], "ORDER", None      # some blocks omit the "ORDER Q'TY" label
    meta = dict(order_ttl_reported=None, shipped_smpl_reported=None, smpl_reported=None)
    for r in range(hdr + 1, r_end + 1):
        lab = text(ws.cell(r, c0).value)
        key = norm_key(lab)
        if key.startswith("ORDER Q"):
            section, label = "ORDER", None
        elif key.startswith("S/DATE"):
            meta["order_ttl_reported"] = to_int(ws.cell(r, c0 + 8).value)
            section, label = "SHIPMENT", None
            continue
        elif key.startswith("TOTAL SHIPPED"):
            meta["shipped_smpl_reported"] = to_int(ws.cell(r, c0 + 8).value)
            section = "TOTALS"
            continue
        elif key.startswith("SMPL LIST"):
            meta["smpl_reported"] = to_int(ws.cell(r, c0 + 8).value)
            continue
        elif key.startswith("BAL Q"):
            section = "SAMPLE_WAIT"
            continue
        elif key in ("26FW ORDER", "27SS ORDER") or key.endswith(" ORDER"):
            break
        if section == "SHIPMENT" and lab:
            label = lab
        if section in ("SAMPLE_WAIT", "SAMPLE") and lab:
            section, label = "SAMPLE", lab
        if section not in ("ORDER", "SHIPMENT", "SAMPLE"):
            continue
        color = text(ws.cell(r, c0 + 1).value)
        if not color and section == "ORDER":
            continue                      # sample/shipment rows may omit the colour (single-colour lots)
        for col, size in sizes.items():
            q = to_int(ws.cell(r, col).value)
            if q:
                out.append(dict(section=section, label=label if section != "ORDER" else None,
                                color_raw=color, size_code=size, qty=q, row_no=r, col_no=col,
                                **_lot(label if section == "SHIPMENT" else None, season)))
    return out, meta


def _lot(label, season):
    if not label:
        return dict(lot_etd=None, lot_eta=None, ship_mode=None)
    m = LOT_RE.search(label)
    if not m:
        mode = next((x for x in ("SEA", "AIR", "HC") if x in label.upper()), None)
        return dict(lot_etd=md_date(label, season), lot_eta=None, ship_mode=mode)
    return dict(lot_etd=md_date(m.group(1), season), lot_eta=md_date(m.group(2), season),
                ship_mode=(m.group(3) or "").upper() or None)


def _reconcile(b, cells, ctx, sheet):
    loc = f"{sheet}!R{b['title_row']}C{b['title_col']}"
    order = sum(x["qty"] for x in cells if x["section"] == "ORDER")
    shipped = sum(x["qty"] for x in cells if x["section"] in ("SHIPMENT", "SAMPLE"))
    b["order_ttl_computed"] = order
    b["shipped_smpl_computed"] = shipped
    if b["order_ttl_reported"] is not None and b["order_ttl_reported"] != order:
        ctx.issue("WARN", "TOTAL_MISMATCH", b["style_no_raw"],
                  f"Order TTL {b['order_ttl_reported']} != computed {order}", loc)
    if b["shipped_smpl_reported"] is not None and b["shipped_smpl_reported"] != shipped:
        ctx.issue("WARN", "TOTAL_MISMATCH", b["style_no_raw"],
                  f"Shipped+smpl {b['shipped_smpl_reported']} != computed {shipped}", loc)
