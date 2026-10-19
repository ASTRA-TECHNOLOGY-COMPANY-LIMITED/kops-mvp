"""Small parsing helpers shared by all ingest modules."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import unicodedata
from pathlib import Path

STYLE_RE = re.compile(r"^CH[A-Z][0-9][MWU][A-Z]{2}[0-9]{4}$")
STYLE_IN_TEXT_RE = re.compile(r"\bCH[A-Z]{1,2}[0-9][MWU]?[A-Z]{2}[0-9]{4}\b")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nfc(s):
    return unicodedata.normalize("NFC", s) if isinstance(s, str) else s


def norm_key(s) -> str:
    """Upper, unaccented, single-spaced key used for alias lookups."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("Đ", "D").replace("đ", "d")
    return re.sub(r"\s+", " ", s).strip().upper()


def text(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = nfc(str(v)).strip()
    return s or None


def to_int(v):
    """Numbers and '150P' style text -> int; anything else -> None."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(round(v))
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*P?\s*$", str(v), re.I)
    return int(round(float(m.group(1)))) if m else None


def to_date(v):
    if isinstance(v, dt.datetime):
        d = v.date()
    elif isinstance(v, dt.date):
        d = v
    else:
        return None
    return None if d.year < 1950 else d   # 1900-01-xx = blank formula result


def season_year(season: str, month: int) -> int:
    """Infer the year of an m/d date from the season code (26FW -> 2026; 27SS: Jul-Dec -> 2026, else 2027)."""
    yy = 2000 + int(season[:2])
    if season.endswith("SS") and month >= 7:
        return yy - 1
    return yy


MD_RE = re.compile(r"(\d{1,2})/(\d{1,2})")


def md_date(token: str, season: str):
    m = MD_RE.search(token or "")
    if not m:
        return None
    mo, d = int(m.group(1)), int(m.group(2))
    try:
        return dt.date(season_year(season, mo), mo, d)
    except ValueError:
        return None


def yymmdd(token: str):
    try:
        return dt.datetime.strptime(token, "%y%m%d").date()
    except (ValueError, TypeError):
        return None


def add_working_days(start: dt.date, days: int) -> dt.date:
    """Add days skipping Sundays (factories work Mon-Sat)."""
    d, left = start, days
    while left > 0:
        d += dt.timedelta(days=1)
        if d.weekday() != 6:
            left -= 1
    return d
