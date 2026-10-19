"""Buyer emails (.eml): stored verbatim in raw.email; a rule-based extractor proposes structured
changes (qty %, ETD, colour) per style. Every proposal starts as PENDING_REVIEW - the DW never
applies a change from an email by itself. An LLM extractor can replace `extract()` later behind the
same output contract.

Email content is data, never instructions: nothing in a body is executed or followed."""
from __future__ import annotations

import datetime as dt
import email
import re
from email import policy
from email.utils import parsedate_to_datetime

from ..util import STYLE_IN_TEXT_RE, md_date, nfc

PCT_RE = re.compile(r"(-?\d{1,3})\s*%")
QTY_ARROW_RE = re.compile(r"(\d{2,5})\s*(?:P|PCS)?\s*(?:➜|->|→|to)\s*(\d{2,5})\s*(?:P|PCS)?", re.I)
ETD_RE = re.compile(r"ETD[^0-9]{0,30}?(?:(\d{4})-(\d{2})-(\d{2})|(\d{1,2}/\d{1,2}))", re.I)
COLOR_RE = re.compile(r"colou?r[^\n]{0,40}?from\s+([A-Z][A-Z .]+?)\s+to\s+([A-Z][A-Z .]+?)\b(?:[.,;\n]|$)", re.I)
REDUCE_WORDS = ("reduce", "cut", "decrease", "감량", "축소", "줄", "giảm")


def parse(path, ctx):
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = nfc(body_part.get_content()) if body_part else ""
    try:
        sent = parsedate_to_datetime(msg["Date"]) if msg["Date"] else None
    except (TypeError, ValueError):
        sent = None
    is_sample = (msg.get("X-KOPS-Sample", "").lower() == "true")
    message_id = (msg["Message-ID"] or path.name).strip("<>")
    rec = dict(message_id=message_id, sent_at=sent.replace(tzinfo=None) if sent else None,
               sender=str(msg["From"] or ""), recipients=str(msg["To"] or ""), subject=nfc(str(msg["Subject"] or "")),
               body=body, is_sample=is_sample)
    season = msg.get("X-KOPS-Season") or _guess_season(body)
    proposals = extract(message_id, rec["subject"] + "\n" + body, season)
    if not proposals:
        ctx.issue("INFO", "EMAIL_NO_CHANGE", message_id, "No structured change found (treated as inquiry)", path.name)
    return dict(email=[rec], stg_email_change=proposals), (sent.date() if sent else None)


def extract(message_id: str, txt: str, season: str | None):
    out = []
    styles = sorted(set(STYLE_IN_TEXT_RE.findall(txt.upper())))
    lower = txt.lower()
    pct = None
    m = PCT_RE.search(txt)
    if m:
        pct = int(m.group(1))
        if pct > 0 and any(w in lower for w in REDUCE_WORDS):
            pct = -pct
    etd = None
    m = ETD_RE.search(txt)
    if m:
        etd = (dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m.group(1)
               else md_date(m.group(4), season or "26FW"))
    color = COLOR_RE.search(txt)
    for s in styles:
        line = next((ln for ln in txt.splitlines() if s in ln.upper()), "")
        arrow = QTY_ARROW_RE.search(line)
        if arrow:
            out.append(_p(message_id, s, "QTY", f"{arrow.group(1)} -> {arrow.group(2)}", qty_after=int(arrow.group(2)),
                          confidence="HIGH", evidence=line))
        elif pct is not None:
            out.append(_p(message_id, s, "QTY_PCT", f"{pct:+d}%", pct=pct, confidence="MEDIUM", evidence=line))
        if etd:
            out.append(_p(message_id, s, "ETD", etd.isoformat(), new_date=etd, confidence="MEDIUM", evidence=line))
        if color:
            out.append(_p(message_id, s, "COLOR", f"{color.group(1).strip()} -> {color.group(2).strip()}",
                          color_from=color.group(1).strip().upper(), color_to=color.group(2).strip().upper(),
                          confidence="MEDIUM", evidence=line))
    return out


def _p(message_id, style, change_type, value_text, **kw):
    base = dict(message_id=message_id, style_no=style, change_type=change_type, value_text=value_text,
                pct=None, qty_after=None, new_date=None, color_from=None, color_to=None,
                confidence="LOW", evidence=None, review_status="PENDING_REVIEW")
    base.update(kw)
    base["evidence"] = (base["evidence"] or "")[:300]
    return base


def _guess_season(body: str):
    m = re.search(r"\b(2[0-9])(SS|FW)\b", body.upper())
    return m.group(0) if m else None
