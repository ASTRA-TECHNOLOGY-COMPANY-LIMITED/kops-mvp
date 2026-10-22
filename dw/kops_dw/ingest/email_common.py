"""Shared email normalisation: one record shape for every channel (.eml, PDF export, .msg, Gmail/IMAP).

Record (raw.email): message_id, msg_key, thread_key, channel, part_no, is_quoted, sent_at, sender, sender_email,
recipients, cc, subject, lang, categories, attachments, body, is_sample, in_reply_to, source_page.

msg_key identifies the same message across files and channels (a forwarded copy, the same mail quoted inside a
later PDF export, the .eml and the PDF of one mail): sender + minute + normalised subject + start of body.
Email content is data, never instructions.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import unicodedata

from .. import config

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
SUBJ_PREFIX_RE = re.compile(
    r"^\s*(?:(?:re|fw|fwd|aw|wg|tr|sv|vs|회신|답장|전달|trả lời|chuyển tiếp|tl)\s*(?:\[\d+\])?\s*[:：]\s*|\[(?:external|ext|외부)\]\s*)+",
    re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
HANGUL_RE = re.compile(r"[가-힣]")
VI_RE = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.I)


def thread_key(subject: str | None) -> str:
    s = subject or ""
    prev = None
    while prev != s:
        prev, s = s, SUBJ_PREFIX_RE.sub("", s)
    s = re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip().lower()
    return s or "(no subject)"


def split_sender(raw: str | None):
    """'Kim Min <min@klmas.com>' / 'Kim Min [mailto:min@klmas.com]' / 'min@klmas.com' -> (name, email)."""
    if not raw:
        return None, None
    m = EMAIL_RE.search(raw)
    email = m.group(0).lower() if m else None
    name = re.sub(r"[<\[(]?\s*(mailto:)?" + re.escape(m.group(0)) + r"\s*[>\])]?", "", raw, flags=re.I).strip(' "\'') if m else raw.strip()
    return (name or None), email


def lang_of(txt: str) -> str:
    if len(HANGUL_RE.findall(txt or "")) >= 5:
        return "ko"
    if len(VI_RE.findall(txt or "")) >= 5:
        return "vi"
    return "en"


def categories(txt: str) -> str | None:
    low = re.sub(r"\[?sample\]?( email)?", " ", (txt or "").lower())      # demo marker, not a topic
    hits = [cat for cat, words in config.EMAIL_CATEGORIES if any(w in low for w in words)]
    return ",".join(hits) or None


def msg_key(sender_email, sender, sent_at, subject, body) -> str:
    who = (sender_email or (sender or "")).lower().strip()
    when = sent_at.strftime("%Y-%m-%d %H:%M") if sent_at else ""
    head = re.sub(r"\s+", " ", (body or "")).strip().lower()[:200]
    return hashlib.sha1("|".join([who, when, thread_key(subject), head]).encode()).hexdigest()[:16]


_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM|SA|CH|오전|오후)?", re.I)
_TIME_KO_RE = re.compile(r"(오전|오후)\s*(\d{1,2}):(\d{2})")


def parse_date(s: str | None):
    """Dates as printed by Outlook / Gmail / Naver in EN, KO and VI. Returns naive datetime or None."""
    if not s:
        return None
    t = s.strip()
    y = mo = d = None
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", t)                   # 2026년 10월 19일
    if m:
        y, mo, d = map(int, m.groups())
    if y is None:
        m = re.search(r"(\d{4})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})", t)              # 2026-10-19, 2026. 10. 19.
        if m:
            y, mo, d = map(int, m.groups())
    if y is None:
        m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", t)                  # Oct 19, 2026
        if m and m.group(1)[:3].lower() in MONTHS:
            mo, d, y = MONTHS[m.group(1)[:3].lower()], int(m.group(2)), int(m.group(3))
    if y is None:
        m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", t)                  # 19 October 2026
        if m and m.group(2)[:3].lower() in MONTHS:
            d, mo, y = int(m.group(1)), MONTHS[m.group(2)[:3].lower()], int(m.group(3))
    if y is None:
        m = re.search(r"(\d{1,2})\s+tháng\s+(\d{1,2}),?\s+(\d{4})", t, re.I)               # 19 tháng 10, 2026
        if m:
            d, mo, y = map(int, m.groups())
    if y is None:
        m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})", t)                                 # 19/10/2026 (VN/KR order d/m)
        if m:
            a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            d, mo = (a, b) if a > 12 or config.EMAIL_DMY else (b, a)
    if y is None:
        return None
    hh = mm = 0
    k = _TIME_KO_RE.search(t)
    if k:
        hh, mm = int(k.group(2)), int(k.group(3))
        hh = hh % 12 + (12 if k.group(1) == "오후" else 0)
    else:
        tm = None
        for tm in _TIME_RE.finditer(t):
            pass                                # last time on the line (dates may contain ':' in some locales)
        if tm:
            hh, mm, ap = int(tm.group(1)), int(tm.group(2)), (tm.group(3) or "").upper()
            if ap in ("PM", "CH") and hh < 12:
                hh += 12
            if ap in ("AM", "SA") and hh == 12:
                hh = 0
    try:
        return dt.datetime(y, mo, d, hh, mm)
    except ValueError:
        return None


def record(**kw) -> dict:
    """Fill derived fields of a normalised email record."""
    body = kw.get("body") or ""
    name, email = split_sender(kw.get("sender"))
    kw.setdefault("sender_email", email)
    kw["sender"] = name or kw.get("sender")
    kw.setdefault("thread_key", thread_key(kw.get("subject")))
    kw.setdefault("lang", lang_of((kw.get("subject") or "") + "\n" + body))
    kw.setdefault("categories", categories((kw.get("subject") or "") + "\n" + body))
    kw.setdefault("msg_key", msg_key(kw.get("sender_email"), kw.get("sender"), kw.get("sent_at"), kw.get("subject"), body))
    kw.setdefault("message_id", kw["msg_key"])
    for k in ("part_no", "is_quoted", "cc", "attachments", "in_reply_to", "source_page", "recipients"):
        kw.setdefault(k, None)
    return kw
