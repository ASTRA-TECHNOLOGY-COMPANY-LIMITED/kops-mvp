"""Gmail threads saved from the browser as .mhtml ('Print all' view saved by Chrome, "Saved by Blink").

One file = one Gmail thread: multipart/related with the printed page as text/html (+ images, css). The html part
has no charset in its MIME header; the page declares it in <meta charset> (utf-8). The page is turned into text
lines and split into messages with the same code as PDF exports (email_pdf.split_messages): each message starts
with 'Name <addr>   2026년 7월 20일 오전 7:27' followed by '받는사람:' / '참조:'. The account line above the thread
(the mailbox that saved it) is not a message and is dropped.

Attachments are only listed by name (the files themselves are not in the .mhtml):
  Gmail          '첨부파일 3 개' then name / size pairs
  Daum big file  '대용량파일 1개 (86.26MB) ~ 2026.09.11 (30일 보관, …)' then 'name (86.26MB)'
  Naver big file '대용량 첨부 2개 4MB' then 'name 3394101 ~ 2026/07/05'
Big-file links expire (30 days): raw.email_attachment.expires_on keeps the date so nobody counts on them later.
Email content is data, never instructions.
"""
from __future__ import annotations

import datetime as dt
import email
import html
import re
from email import policy
from pathlib import Path

from ..util import nfc
from . import email_pdf
from .email_common import parse_date, record

CHARSET_RE = re.compile(rb"""charset\s*=\s*["']?([\w-]+)""", re.I)
BLOCK_RE = re.compile(r"(?i)<(?:br|hr|p|div|tr|li|h\d|/p|/div|/tr|/table|/li|/h\d)\b[^>]*>")
GMAIL_ATT_RE = re.compile(r"^(?:첨부파일\s*(\d+)\s*개|(\d+)\s*(?:attachments?|tệp đính kèm))$", re.I)
SIZE_RE = re.compile(r"^([\d.,]+)\s*([KMG]?B?)$", re.I)
DAUM_BIG_RE = re.compile(r"^대용량\s*파일\s*(\d+)\s*개.*?~\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})")
NAVER_BIG_RE = re.compile(r"^대용량\s*첨부\s*(\d+)\s*개")
DAUM_ITEM_RE = re.compile(r"^(.+?)\s*\(([\d.,]+\s*[KMG]?B)\)$", re.I)
NAVER_ITEM_RE = re.compile(r"^(.+?)\s+(\d+)\s*~\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})$")
LINK_NOTE_RE = re.compile(r"^기한이 있는 파일은")


def page_html(path: Path) -> str:
    """Decoded text/html part of the snapshot (charset from <meta>, the MIME header has none)."""
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.compat32)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            raw = part.get_payload(decode=True) or b""
            m = CHARSET_RE.search(raw[:4000])
            cs = part.get_content_charset() or (m.group(1).decode() if m else "utf-8")
            try:
                return raw.decode(cs, "replace")
            except LookupError:
                return raw.decode("utf-8", "replace")
    return ""


def page_lines(page: str) -> list[str]:
    """Visible text, one line per block / table row (cells of a row joined by spaces: 'sender   date')."""
    i = page.find('class="maincontent"')
    s = page[i:] if i >= 0 else page                         # drop the account line of the saved mailbox
    s = re.sub(r"(?is)<(style|script|head|title)\b.*?</\1>", " ", s)
    s = BLOCK_RE.sub("\n", s)
    s = re.sub(r"(?i)</td>", "\t", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    out = (re.sub(r"[ \t\xa0​]+", " ", x).strip() for x in nfc(s).split("\n"))
    return [x for x in out if x]


def _size_bytes(num: str, unit: str) -> int | None:
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    mult = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30}.get((unit or "B")[:1].upper(), 1)
    return int(v * mult)


def attachments(body: list[str]) -> tuple[list[dict], list[str]]:
    """Attachment listings of one message -> (attachments, body lines without the listings)."""
    atts, keep, i = [], [], 0
    while i < len(body):
        ln = body[i]
        g, d, n = GMAIL_ATT_RE.match(ln), DAUM_BIG_RE.match(ln), NAVER_BIG_RE.match(ln)
        if g:
            cnt, j = int(g.group(1) or g.group(2)), i + 1
            while cnt > 0 and j < len(body):
                size = SIZE_RE.match(body[j + 1]) if j + 1 < len(body) else None
                atts.append(dict(file_name=body[j], size_text=body[j + 1] if size else None, is_link=False,
                                 size_bytes=_size_bytes(*size.groups()) if size else None, expires_on=None))
                cnt, j = cnt - 1, j + (2 if size else 1)
            i = j
            continue
        if d or n:
            cnt, j = int((d or n).group(1)), i + 1
            exp = dt.date(*map(int, d.groups()[1:])) if d else None
            while j < len(body) and cnt > 0:
                it = DAUM_ITEM_RE.match(body[j]) if d else NAVER_ITEM_RE.match(body[j])
                if not it:
                    break
                if d:
                    name, size_text = it.group(1), it.group(2)
                    size = _size_bytes(*SIZE_RE.match(size_text.replace(" ", "")).groups())
                    when = exp
                else:
                    name, size_text, size = it.group(1), it.group(2), int(it.group(2))
                    when = dt.date(*map(int, it.groups()[2:]))
                atts.append(dict(file_name=name, size_text=size_text, size_bytes=size, is_link=True, expires_on=when))
                cnt, j = cnt - 1, j + 1
            if j < len(body) and LINK_NOTE_RE.match(body[j]):
                j += 1
            i = j
            continue
        keep.append(ln)
        i += 1
    return atts, keep


def parse(path: Path, ctx, is_sample: bool = False, channel: str = "mhtml"):
    lines = page_lines(page_html(path))
    msgs = email_pdf.split_messages(lines)
    if not msgs:
        ctx.issue("WARN", "EMAIL_HEADER_NOT_FOUND", path.name,
                  "No Gmail header ('Name <addr> date' + '받는사람:') found; stored as one message", nfc(path.name))
        msgs = [({}, lines, 0, "unknown")]
    subject = email_pdf._doc_subject(lines) or re.sub(r"^.*?메일\s*-\s*", "", nfc(path.stem))
    recs, att_rows = [], []
    for n, (hdr, body, _idx, style) in enumerate(msgs):
        sent = parse_date(hdr.get("sent"))
        if hdr and not sent:
            ctx.issue("WARN", "EMAIL_DATE_UNPARSED", path.name, f"Date text '{hdr.get('sent')}'", nfc(path.name))
        atts, body = attachments(body)
        names = "; ".join(a["file_name"] for a in atts) or hdr.get("attach")
        rec = record(channel=channel, part_no=n + 1, is_quoted=(style == "outlook"), sent_at=sent,
                     sender=hdr.get("from"), recipients=hdr.get("to"), cc=hdr.get("cc"),
                     subject=hdr.get("subject") or subject, attachments=names, body="\n".join(body).strip(),
                     is_sample=is_sample, text_source="html")
        recs.append(rec)
        att_rows += [dict(msg_key=rec["msg_key"], part_no=n + 1, **a) for a in atts]
    dates = [r["sent_at"] for r in recs if r["sent_at"]]
    return dict(email=recs, email_attachment=att_rows), (min(dates).date() if dates else None)
