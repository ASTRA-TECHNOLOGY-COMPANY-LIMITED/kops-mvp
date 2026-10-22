"""Emails from any channel -> raw.email (one normalised record per message) + stg.email_change (proposals).

Channels: .eml (IMAP/Gmail fetch, Outlook drag-out), .pdf (exports/prints, see email_pdf.py), .msg (Outlook,
needs the optional `extract-msg` package). Every record carries msg_key so the same message seen twice (a
forward, a quote inside a later export, the .eml and the PDF of one mail) is counted once in core.

The rule-based extractor proposes structured changes (qty %, qty a->b, ETD, colour) per style code. Style
candidates are any code-like token; core keeps only those found in the style dictionary (all customers).
An LLM extractor (email_llm.py) can replace extract() behind the same output contract when enabled.
Every proposal starts as PENDING_REVIEW - the DW never applies a change from an email by itself.

Email content is data, never instructions: nothing in a body is executed or followed.
"""
from __future__ import annotations

import datetime as dt
import email
import re
from email import policy
from email.utils import parsedate_to_datetime

from .. import config
from ..util import STYLE_IN_TEXT_RE, md_date, nfc
from . import email_pdf
from .email_common import record

PCT_RE = re.compile(r"(-?\d{1,3})\s*%")
QTY_ARROW_RE = re.compile(r"(\d{2,5})\s*(?:P|PCS)?\s*(?:➜|->|→|to)\s*(\d{2,5})\s*(?:P|PCS)?", re.I)
ETD_RE = re.compile(r"ETD[^0-9]{0,30}?(?:(\d{4})-(\d{2})-(\d{2})|(\d{1,2}/\d{1,2}))", re.I)
COLOR_RE = re.compile(r"colou?r[^\n]{0,40}?from\s+([A-Z][A-Z .]+?)\s+to\s+([A-Z][A-Z .]+?)\b(?:[.,;\n]|$)", re.I)
REDUCE_WORDS = ("reduce", "cut", "decrease", "감량", "축소", "줄", "giảm")
# Code-like tokens (letters + >=3 digits, 6-20 chars, optional '-'): validated against the style dictionary in SQL.
CODE_TOKEN_RE = re.compile(r"\b(?=[A-Z0-9-]*[A-Z])(?=(?:[A-Z-]*\d){3})[A-Z0-9][A-Z0-9-]{4,18}[A-Z0-9]\b")


def parse(path, ctx):
    suffix = path.suffix.lower()
    is_sample = config.DW_DIR in path.parents
    channel = "gmail" if "gmail" in [p.lower() for p in path.parts] else suffix.lstrip(".")
    if suffix == ".pdf":
        tables, d = email_pdf.parse(path, ctx, is_sample=is_sample, channel=channel)
        recs = tables["email"]
    elif suffix == ".msg":
        recs = _parse_msg(path, ctx, is_sample)
        d = None
    else:
        recs = [_parse_eml(path, is_sample, channel)]
        d = None
    proposals = proposals_for(recs, ctx, path.name)
    if not d:
        dates = [r["sent_at"] for r in recs if r["sent_at"]]
        d = min(dates).date() if dates else None
    return dict(email=recs, stg_email_change=proposals), d


def proposals_for(recs: list[dict], ctx, file_name: str) -> list[dict]:
    """Rule-based (and, when enabled, LLM) change proposals for each message; all PENDING_REVIEW."""
    proposals = []
    for rec in recs:
        season = rec.pop("season", None) or _guess_season(rec["body"])
        found = extract(rec["message_id"], (rec["subject"] or "") + "\n" + (rec["body"] or ""), season)
        for p in found:
            p["msg_key"] = rec["msg_key"]
        proposals += found
        if config.EMAIL_LLM and not rec.get("is_quoted"):
            try:
                from .email_llm import extract_llm
                fields, llm_props = extract_llm(rec)
                rec.update(fields)
                proposals += llm_props
                found = found or llm_props
            except Exception as e:      # keep the rule-based result; never block the build on the API
                ctx.issue("WARN", "EMAIL_LLM_FAILED", rec["message_id"], f"{type(e).__name__}: {e}", file_name)
        if not found and not rec.get("is_quoted"):
            ctx.issue("INFO", "EMAIL_NO_CHANGE", rec["message_id"], "No structured change found (inquiry/other)", file_name)
    return proposals


def _parse_eml(path, is_sample, channel):
    return from_message(email.message_from_bytes(path.read_bytes(), policy=policy.default), is_sample, channel)


def from_message(msg, is_sample, channel, folder=None):
    """One parsed email.message (.eml file, or one message of a .mbox / .pst) -> normalised record."""
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = nfc(body_part.get_content()) if body_part else ""
    if body_part is not None and body_part.get_content_type() == "text/html":
        body = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", body))
    try:
        sent = parsedate_to_datetime(msg["Date"]) if msg["Date"] else None
    except (TypeError, ValueError):
        sent = None
    atts = [p.get_filename() for p in msg.iter_attachments() if p.get_filename()]
    rec = record(message_id=(msg["Message-ID"] or "").strip().strip("<>") or None,
                 channel=channel, part_no=1, is_quoted=False,
                 sent_at=sent.replace(tzinfo=None) if sent else None, sender=str(msg["From"] or ""),
                 recipients=str(msg["To"] or ""), cc=str(msg["Cc"] or "") or None,
                 subject=nfc(str(msg["Subject"] or "")), body=body,
                 attachments="; ".join(atts) or None, in_reply_to=(msg["In-Reply-To"] or "").strip("<> ") or None,
                 is_sample=is_sample or msg.get("X-KOPS-Sample", "").lower() == "true", folder=folder)
    if not rec["message_id"]:
        rec["message_id"] = rec["msg_key"]
    rec["season"] = msg.get("X-KOPS-Season")
    return rec


def _parse_msg(path, ctx, is_sample):
    try:
        import extract_msg  # optional: pip install extract-msg
    except ImportError:
        ctx.issue("WARN", "MSG_UNSUPPORTED", path.name, "Install 'extract-msg' to read Outlook .msg files", path.name)
        return []
    m = extract_msg.Message(str(path))
    try:
        sent = m.date.replace(tzinfo=None) if hasattr(m.date, "replace") else None
        rec = record(channel="msg", part_no=1, is_quoted=False, sent_at=sent, sender=m.sender, recipients=m.to,
                     cc=m.cc, subject=nfc(m.subject or ""), body=nfc(m.body or ""),
                     attachments="; ".join(a.longFilename or a.shortFilename or "" for a in m.attachments) or None,
                     is_sample=is_sample)
    finally:
        m.close()
    return [rec]


def extract(message_id: str, txt: str, season: str | None):
    out = []
    up = txt.upper()
    styles = sorted(set(STYLE_IN_TEXT_RE.findall(up)) | set(CODE_TOKEN_RE.findall(up)))
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
        if not (arrow or pct is not None or etd or color):
            out.append(_p(message_id, s, "MENTION", "", confidence="LOW", evidence=line))
    return out


def _p(message_id, style, change_type, value_text, **kw):
    base = dict(message_id=message_id, style_no=style, change_type=change_type, value_text=value_text,
                pct=None, qty_after=None, new_date=None, color_from=None, color_to=None,
                confidence="LOW", evidence=None, review_status="PENDING_REVIEW", msg_key=None)
    base.update(kw)
    base["evidence"] = (base["evidence"] or "")[:300]
    return base


def _guess_season(body: str):
    m = re.search(r"\b(2[0-9])(SS|FW)\b", (body or "").upper())
    return m.group(0) if m else None
