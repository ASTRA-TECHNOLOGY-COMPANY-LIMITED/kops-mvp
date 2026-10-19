"""ORDER RECAP (season master): 4-row block per style, status encoded in cell fill.

Columns used (see analys-docs/source_to_target_mapping.csv):
  row1: B order no, C brand, D style no, E factory, H/J colour+qty, K grand ttl, L ETD VN, M RDD
  row2: B/C progress + line, D description EN
  row3: D name KR
  row4: C collection, D main fabric, E factory history note
  colour rows (H colour, I change note, J qty) live in the 4 rows of the block.
"""
from __future__ import annotations

import re

from ..excel import fill_key
from ..util import md_date, norm_key, text, to_date, to_int, yymmdd

SHEET = "ORDER RECAP"
LEGEND_LABELS = {"NOT FIXED", "ON PRODUCTION", "KOREA SHIP OUT", "UPDATE", "FIXED PRICE",
                 "SEWING FINISHED", "CANCEL", "PENDING STYLE"}
QTY_CHANGE_RE = re.compile(r"(\d{6})\s*(REDUCED|REVISED|INCREASED|ADDED|CHANGED)?\s*(\d+)\s*P?\s*(?:➜|->|→|>)\s*(\d+)\s*P?", re.I)
FACT_NOTE_RE = re.compile(r"(\d{6})\s*(FIXED|MOVED|CHANGED)\s*FACT(?:ORY)?\s*(?:\(([^)]*)\))?", re.I)


def parse(wb, season: str, ctx):
    ws = wb[SHEET]
    legend = _legend(ws)
    report_date = to_date(ws.cell(2, 4).value)
    styles, colors, qty_changes, fact_moves = [], [], [], []

    starts = [r for r in range(3, ws.max_row + 1)
              if norm_key(ws.cell(r, 3).value) not in ("", "BRAND") and ws.cell(r, 2).value
              and re.match(r"^[A-Z]{1,2}\d{1,3}$", str(ws.cell(r, 2).value).strip())
              and ws.cell(r, 4).value]
    for i, s in enumerate(starts):
        style_no = norm_key(ws.cell(s, 4).value)
        last = _block_last_row(ws, s, starts[i + 1] if i + 1 < len(starts) else ws.max_row + 1)
        if not re.match(r"^CH[A-Z0-9]{9,11}$", style_no):
            continue
        factory_raw = text(ws.cell(s, 5).value)
        fill = fill_key(ws.cell(s, 4)) or fill_key(ws.cell(s, 2))
        status = legend.get(fill, "NO STATUS" if fill is None else f"UNMAPPED:{fill}")
        if status.startswith("UNMAPPED"):
            ctx.issue("WARN", "STATUS_FILL_UNMAPPED", style_no, f"Fill {fill} not in legend", f"{SHEET}!D{s}")
        if "CANCEL" in norm_key(factory_raw):
            status = "CANCEL"
        etd_cell = ws.cell(s, 12).value
        etd = to_date(etd_cell)
        etd_raw = text(etd_cell) if etd is None else None
        if etd is None and etd_raw:
            ctx.issue("WARN", "DATE_UNPARSED", style_no, f"ETD VN text '{etd_raw}'", f"{SHEET}!L{s}")
        if etd is None:
            alt = text(ws.cell(s + 1, 12).value)          # e.g. '8/9->8/16' written under the date
            if alt and "->" in alt:
                etd = md_date(alt.split("->")[-1], season)
                etd_raw = alt
        if etd and not _in_season(etd, season):
            ctx.issue("WARN", "ETD_OUT_OF_SEASON", style_no, f"ETD {etd} outside season {season}", f"{SHEET}!L{s}")
        fact_note = text(ws.cell(last, 5).value)
        progress = " | ".join(t for t in (text(ws.cell(r, 2).value) for r in range(s + 1, last + 1)) if t)
        styles.append(dict(
            season=season, row_no=s, order_no=text(ws.cell(s, 2).value), brand=norm_key(ws.cell(s, 3).value),
            style_no=style_no, factory_raw=factory_raw, factory_note=fact_note, status_fill=fill,
            status_label=status, grand_ttl_reported=to_int(ws.cell(s, 11).value), etd_raw=etd_raw, etd_vn=etd,
            rdd_kr=to_date(ws.cell(s, 13).value), line_raw=text(ws.cell(s + 1, 3).value),
            collection_raw=text(ws.cell(last, 3).value), description_en=text(ws.cell(s + 1, 4).value),
            name_kr=text(ws.cell(s + 2, 4).value), main_fabric=text(ws.cell(last, 4).value),
            progress_notes=progress or None, report_date=report_date))
        for r in range(s, last + 1):
            c_raw = text(ws.cell(r, 8).value)
            if not c_raw or norm_key(c_raw).startswith("BEFORE"):
                continue
            lines = c_raw.split("\n")
            q_raw = ws.cell(r, 10).value
            qty = to_int(q_raw)
            note = text(ws.cell(r, 9).value)
            # A quantity typed as text ('170P') is excluded by the file's own SUM: these are colours that were
            # cancelled/deleted (or not yet confirmed). Keep the number, exclude it from the active order.
            is_text = isinstance(q_raw, str)
            if q_raw not in (None, "") and qty is None:
                ctx.issue("WARN", "QTY_UNPARSED", style_no, f"Qty '{q_raw}'", f"{SHEET}!J{r}")
            elif is_text and qty is not None:
                ctx.issue("INFO", "QTY_TEXT_EXCLUDED", style_no,
                          f"{lines[0].strip()}: qty '{q_raw}' is text, excluded from order total (note: {note or '-'})",
                          f"{SHEET}!J{r}")
            colors.append(dict(season=season, row_no=r, style_no=style_no, color_raw=lines[0].strip(),
                               color_note="\n".join(lines[1:]).strip() or None, change_note=note,
                               qty_raw=text(q_raw), order_qty=qty, is_active=not is_text))
            for m in QTY_CHANGE_RE.finditer(note or ""):
                qty_changes.append(dict(season=season, style_no=style_no, color_raw=lines[0].strip(),
                                        change_date=yymmdd(m.group(1)), kind=(m.group(2) or "CHANGED").upper(),
                                        qty_before=int(m.group(3)), qty_after=int(m.group(4)),
                                        note_raw=note, location=f"{SHEET}!I{r}"))
        for m in FACT_NOTE_RE.finditer(fact_note or ""):
            fact_moves.append(dict(season=season, style_no=style_no, event_date=yymmdd(m.group(1)),
                                   action=m.group(2).upper(), factory_hint=(m.group(3) or "").strip() or None,
                                   note_raw=fact_note, location=f"{SHEET}!E{last}"))
        reported = to_int(ws.cell(s, 11).value)
        computed = sum((c["order_qty"] or 0) for c in colors if c["style_no"] == style_no and c["is_active"])
        if status != "CANCEL" and reported is not None and reported != computed:
            ctx.issue("WARN", "TOTAL_MISMATCH", style_no,
                      f"GRAND TTL {reported} != sum of colours {computed}", f"{SHEET}!K{s}")
    return dict(order_recap_style=styles, order_recap_color=colors,
                stg_qty_change=qty_changes, stg_factory_event=fact_moves), report_date


def _block_last_row(ws, s: int, next_start: int) -> int:
    """Blocks are 4 rows, longer when a style has more than 4 colours. Stop at page headers, subtotals or
    placeholder blocks (order no in B without a style)."""
    last = s + 3
    for r in range(s + 1, next_start):
        b = norm_key(ws.cell(r, 2).value)
        if re.match(r"^[A-Z]{1,2}\d{1,3}$", b) or b.startswith(("SUB TOTAL", "GRAND TOTAL", "UP DATE")) or b == "NO" \
                or "ORDER RECAP" in b:
            break
        if ws.cell(r, 8).value not in (None, ""):
            last = max(last, r)
    return min(last, next_start - 1)


def _legend(ws) -> dict:
    out = {}
    for r in (1, 2):
        for c in range(1, 40):
            label = norm_key(ws.cell(r, c).value)
            if label in LEGEND_LABELS:
                f = fill_key(ws.cell(r, c))
                if f:
                    out[f] = label
    return out


def _in_season(d, season: str) -> bool:
    yy = 2000 + int(season[:2])
    return (yy - 1, 7) <= (d.year, d.month) <= (yy, 12) if season.endswith("SS") else d.year == yy
