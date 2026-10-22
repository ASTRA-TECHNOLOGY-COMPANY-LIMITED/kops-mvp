"""Emails exported/printed to PDF (Outlook 'Print to PDF', Gmail 'Print all', Naver/Hiworks print) in EN/KO/VI.

One PDF may hold one message, a thread printed by Gmail (several top-level messages), or one message with the
older conversation quoted below it (Outlook). Each header block becomes one record:
  Outlook-style  : 'From:'/'보낸 사람:'/'Từ:' followed by 'Sent:'/'Date:'/'보낸 날짜:'/'Đã gửi:', 'To:', 'Cc:', 'Subject:'
  Gmail print    : 'Name <addr>   Mon, Oct 19, 2026 at 10:15 AM' then 'To: ...'
Messages after the first block of an Outlook-style export are marked is_quoted (older mails in the chain); they
still count as history and are de-duplicated against other files by msg_key.
Scanned PDFs (no text layer) are reported (PDF_NO_TEXT) instead of guessed; OCR is optional (tesseract).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..util import nfc
from .email_common import parse_date, record

LABELS = {
    "from": r"(?:from|보낸\s*사람|발신자|보낸이|từ|người gửi|发件人)",
    "sent": r"(?:sent|date|보낸\s*날짜|날짜|발신\s*일시|보낸\s*시간|đã gửi|ngày gửi|ngày|gửi lúc|发送时间)",
    "to": r"(?:to|받는\s*사람|수신자|받는이|đến|người nhận|收件人)",
    "cc": r"(?:cc|참조|đồng gửi|抄送)",
    "subject": r"(?:subject|제목|chủ đề|tiêu đề|主题)",
    "attach": r"(?:attachments?|첨부\s*파일|첨부|tệp đính kèm|附件)",
}
LABEL_RE = {k: re.compile(r"^\s*" + v + r"\s*[:：]\s*(.*)$", re.I) for k, v in LABELS.items()}
GMAIL_SENDER_RE = re.compile(r"^(?P<name>[^<>\n]{1,80}?)\s*<(?P<addr>[^<>\s]+@[^<>\s]+)>\s*(?P<rest>.*)$")
NOISE_RE = re.compile(r"^(https?://mail\.google\.com\S*|\d+/\d+|page \d+ (?:of|/) \d+|\d+\s*/\s*\d+\s*페이지)$", re.I)


def pdf_text(path: Path) -> list[str]:
    """Text of each page. pypdf first; pdftotext (poppler) when installed and pypdf finds nothing."""
    pages = []
    try:
        from pypdf import PdfReader
        pages = [p.extract_text() or "" for p in PdfReader(str(path)).pages]
    except Exception:
        pages = []
    if sum(len(p.strip()) for p in pages) < 20 and shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, timeout=120)
        pages = out.stdout.decode("utf-8", "replace").split("\f")
    return [nfc(p) for p in pages]


def _label(line: str):
    for k, rx in LABEL_RE.items():
        m = rx.match(line)
        if m:
            return k, m.group(1).strip()
    return None, None


def split_messages(lines: list[str]):
    """Return a list of (header dict, body lines, line index, style) found in the text."""
    starts = []
    for i, ln in enumerate(lines):
        k, _ = _label(ln)
        if k == "from":
            nxt = [_label(x)[0] for x in lines[i + 1:i + 8]]
            if "sent" in nxt or "subject" in nxt:
                starts.append((i, "outlook"))
            continue
        g = GMAIL_SENDER_RE.match(ln)
        if g:
            rest = g.group("rest") or (lines[i + 1] if i + 1 < len(lines) else "")
            if parse_date(rest) and any(_label(x)[0] == "to" for x in lines[i + 1:i + 4]):
                starts.append((i, "gmail"))
    msgs = []
    for n, (i, style) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        hdr, j = {}, i
        if style == "gmail":
            g = GMAIL_SENDER_RE.match(lines[i])
            hdr["from"] = f"{g.group('name').strip()} <{g.group('addr')}>"
            rest = g.group("rest")
            if not parse_date(rest):
                j += 1
                rest = lines[j]
            hdr["sent"] = rest
            j += 1
        last_key = None
        while j < end:
            k, v = _label(lines[j])
            if k and k not in hdr:
                hdr[k], last_key = v, k
                j += 1
                continue
            if last_key in ("to", "cc", "attach") and lines[j].strip() and (";" in lines[j] or "@" in lines[j]) \
                    and not _label(lines[j])[0]:
                hdr[last_key] += " " + lines[j].strip()          # wrapped recipient lists
                j += 1
                continue
            if style == "outlook" and j - i <= 1 and not k:
                j += 1                                           # stray line inside the header block
                continue
            break
        msgs.append((hdr, lines[j:end], i, style))
    return msgs


def _doc_subject(lines: list[str]) -> str | None:
    """Gmail print: 'Gmail - <subject>' or the subject line above 'N messages' / '메일 N개'."""
    for i, ln in enumerate(lines[:12]):
        m = re.match(r"^Gmail\s*-\s*(.+)$", ln)
        if m:
            return m.group(1).strip()
        if re.match(r"^(\d+\s+messages?|메일\s*\d+\s*개|\d+\s+thư)$", ln.strip(), re.I) and i > 0:
            return lines[i - 1].strip()
    return None


def parse(path: Path, ctx, is_sample: bool = False, channel: str = "pdf"):
    pages = pdf_text(path)
    lines, page_of = [], []
    for pno, p in enumerate(pages, start=1):
        for ln in p.splitlines():
            s = ln.rstrip()
            if s.strip() and NOISE_RE.match(s.strip()):
                continue
            lines.append(s.strip())
            page_of.append(pno)
    if sum(len(x) for x in lines) < 20:
        ctx.issue("WARN", "PDF_NO_TEXT", path.name, "No text layer (scanned/image PDF). Needs OCR or a manual read.", path.name)
        return dict(email=[], stg_email_change=[]), None
    msgs = split_messages(lines)
    if not msgs:
        ctx.issue("WARN", "EMAIL_HEADER_NOT_FOUND", path.name,
                  "No From/Sent/Subject header block found; stored as one message without sender/date", path.name)
        msgs = [({}, lines, 0, "unknown")]
    doc_subject = _doc_subject(lines)
    recs = []
    for n, (hdr, body, idx, style) in enumerate(msgs):
        sent = parse_date(hdr.get("sent"))
        if hdr and not sent:
            ctx.issue("WARN", "EMAIL_DATE_UNPARSED", path.name, f"Date text '{hdr.get('sent')}'", f"{path.name} p{page_of[idx]}")
        body_txt = "\n".join(body).strip()
        recs.append(record(
            channel=channel, part_no=n + 1, is_quoted=(style == "outlook" and n > 0), sent_at=sent,
            sender=hdr.get("from"), recipients=hdr.get("to"), cc=hdr.get("cc"),
            subject=hdr.get("subject") or doc_subject or path.stem, attachments=hdr.get("attach"),
            body=body_txt, is_sample=is_sample, source_page=page_of[idx] if idx < len(page_of) else None))
    first = recs[0]["sent_at"]
    return dict(email=recs), (first.date() if first else None)
