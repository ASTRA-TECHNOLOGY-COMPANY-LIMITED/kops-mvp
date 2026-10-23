"""Metadata-only documents (N-02): technical files that are listed in the DW but never opened.

Style packages from KLMAS hold, per email, the work sheets / comments / mini markers (Excel or PDF, up to 217 MB)
and CAD pattern files. The DW does not read them: it records what the name says (core.document) so a style
timeline can point to them. Sources of each field, in order:
  1. the file name                       '260629 (CHALLENGER - TRUONG PHUC) CHF3WJK6701_TÀI LIỆU SẢN XUẤT ĐẠI TRÀ ….xlsx'
  2. the KLMAS email folders around it   '260629 (CHALLENGER- TRUONG PHUC) CHF3WJK6701- FPP CFMD MAIN W.S …/'
  3. our own raw-docs folders (last resort, GUIDELINES §2): STYLES/<customer>/<season>/<style> - <factory>/
meta_source says which one gave the customer / style (file_name | email_folder | local_folder).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path

from . import config
from .util import nfc, norm_key

CAD_EXT = (".dxf", ".pds", ".sty", ".rul", ".mdl", ".pax", ".plt", ".hpg", ".cut")
ARCHIVE_EXT = (".zip", ".rar", ".7z")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".heic")
LINK_EXT = (".url", ".webloc", ".lnk")
OFFICE_EXT = (".xlsx", ".xlsb", ".xlsm", ".xls", ".pdf", ".doc", ".ppt", ".pptx")
# Never opened, whatever the name: CAD, archives, pictures, shortcuts, files without an extension ('noname').
META_ONLY_EXT = CAD_EXT + ARCHIVE_EXT + IMAGE_EXT + LINK_EXT + ("",)
# Office files whose name says they are technical / sample / quality paperwork (matched on the upper-case,
# unaccented name). A code-like style number in the name of an unparsed Excel/PDF also makes it a document.
DOC_KEYWORDS = (
    "W.S", "W,S", " WS", "WORK SHEET", "WORKING SHEET", "CMT", "CMMT", "COMMENT", "MINI MAR", "MARKER", "PATTERN",
    "GRADING", "TAI LIEU", "CONSUMPTION", "BALANCE SHEET", "FPP", "INLINE", "SAMPLE", "SMPL", "MANUAL", "PACKING",
    "B GARMENT", "SHORTAGE", "ASSORT", "SKETCH", "작업지시서", "작지", "요척", "패턴", "그레이딩", "미니마카", "검단",
    "B품", "폐기", "불량", "쇼티지", "수량확정", "소재확정", "원단발주", "매뉴얼", "샘플")
# What the file is (first match on the name; CAD / archive / image by extension).
KIND_RULES = [
    ("CONSUMPTION", ("CONSUMPTION", "BALANCE SHEET", "요척")),
    ("FABRIC_INSPECTION", ("검단", "FABRIC INSPECTION", "KIEM VAI")),
    ("MARKER", ("MINI MAR", "MARKER", "미니마카")),
    ("PATTERN", ("PATTERN", "GRADING", "패턴", "그레이딩")),
    ("COMMENT", ("CMT", "CMMT", "COMMENT", "코멘트")),
    ("WORK_SHEET", ("W.S", "W,S", " WS", "WORK SHEET", "WORKING SHEET", "TAI LIEU", "작업지시서", "작지")),
    ("CONFIRMATION", ("수량확정", "소재확정", "원단발주")),
    ("ASSORT", ("ASSORT", "아소트")),
    ("QUALITY", ("B GARMENT", "B품", "폐기", "불량", "QUALITY")),
    ("SHORTAGE", ("SHORTAGE", "쇼티지")),
    ("PACKING", ("PACKING",)),
    ("MANUAL", ("MANUAL", "매뉴얼")),
]
# Sample / production stage of a style (also used for email milestones, see milestones.py). First match wins,
# so the more specific phrases come first ('INLINE CFMD W.S' is INLINE, 'FPP CFMD' is not a request).
STAGE_RULES = [
    ("INLINE_CMT", ("INLINE",)),
    ("FPP_CMT", ("FPP CMT", "FPP SAMPLE COMMENT", "FPP COMMENT", "INTERNAL COMMENT", "FPP 코멘트", "FPP코멘트")),
    ("FPP_CFMD", ("FPP CFMD", "SAN XUAT DAI TRA", "TAI LIEU SAN XUAT", "SXDT", "MAIN W.S", "MAIN WS", "BULK W.S")),
    ("FPP_REQUEST", ("FPP REQUEST", "FPP SAMPLE REQUEST", "MAY MAU FPP", "MAY FPP", "FPP WORK SHEET",
                     "FPP WORKING SHEET", "FPP SAMPLE WS", "FPP SAMPLE (", "PP샘플", "FPP샘플")),
    ("DM_APPROVAL", ("CONSUMPTION", "BALANCE SHEET", "DUYET DM", "요척")),
    ("FABRIC_INSPECTION", ("검단", "FABRIC INSPECTION", "KIEM VAI")),
]
SEASON_RE = re.compile(r"(?<![0-9A-Z])(?:(2\d)\s?(SS|FW|AW)|(SS|FW|AW)\s?(2\d))(?![0-9A-Z])")
# Letters + >= 3 digits, 6-20 chars (CHF3WJK6701, LBV-27016, BI6838U03, 32YA6G40, 7ND1709): checked in SQL
# against core.style_dictionary; a candidate that is not a known style is kept as written.
CODE_RE = re.compile(r"(?<![A-Z0-9])(?=[A-Z0-9-]*[A-Z])(?=(?:[A-Z-]*\d){3})[A-Z0-9][A-Z0-9-]{4,18}[A-Z0-9](?![A-Z0-9])")
NOT_STYLE_RE = re.compile(r"^(?:2\d(?:SS|FW|AW)(?:-.*)?|\d{6}R\d*|\d+P|\d+PCS|[A-Z]{2,}\d{6,}|RDD-\d+|[A-Z]+-\d{1,2})$")
# Pattern file suffixes: CHF3MJK6301-G-260612.dxf, CHF4MPT6442-FPP-V9-260521.sty, BI7138UE1-110-150(…).dxf
CODE_SUFFIX_RE = re.compile(r"^(?:G|FPP|V\d+|\d{2,3})(?:-.*)?$")
PAREN_FACTORY_RE = re.compile(r"\(\s*([^()]*?)\s*-\s*([^()]*?)\s*\)")
LOCAL_DEPTH = {"STYLES": 4, "QUALITY": 3}       # our folders: STYLES/<customer>/<season>/<style> - <factory>/

_FACTORY = {k.replace(" ", ""): v for k, v in config.FACTORY_ALIASES.items()}


def is_meta_only(path: Path) -> bool:
    ext = path.suffix.lower()
    return ext in META_ONLY_EXT or (ext in OFFICE_EXT and _office_doc(nfc(path.name)))


def _office_doc(name: str) -> bool:
    up = norm_key(name)
    return any(k in up or k in name.upper() for k in DOC_KEYWORDS) or bool(_codes(name))


def _codes(text: str) -> list[str]:
    up = nfc(text).upper().replace("_", " ")
    codes = (_strip_suffix(c) for c in CODE_RE.findall(up))
    return [c for c in dict.fromkeys(codes) if not NOT_STYLE_RE.match(c)]


def _strip_suffix(code: str) -> str:
    """Shortest head with >= 3 digits followed by a pattern suffix ('LBV-27016' keeps its dash)."""
    parts = code.split("-")
    for i in range(1, len(parts)):
        head = "-".join(parts[:i])
        if sum(ch.isdigit() for ch in head) >= 3 and CODE_SUFFIX_RE.match("-".join(parts[i:])):
            return head
    return code


def _first_rule(rules, *texts) -> str | None:
    for t in texts:
        up, raw = norm_key(t), nfc(t).upper()
        for code, words in rules:
            if any(w in up or w in raw for w in words):
                return code
    return None


def _customer(text: str) -> str | None:
    up = norm_key(text)
    return next((c for k, c in config.CUSTOMER_KEYS if re.search(r"(?<![A-Z])" + re.escape(k) + r"(?![A-Z])", up)), None)


def _factory(text: str) -> str | None:
    """'(CHALLENGER - TRUONG PHUC)', '(DHG-SONHA)', '(CLGR-TBM)', '0514)TP_ …', or a factory name in the text."""
    up = norm_key(text).replace("_", " ")
    for _, fac in PAREN_FACTORY_RE.findall(up):
        code = _FACTORY.get(fac.replace(" ", ""))
        if code:
            return code
    m = re.match(r"^\d{4}\)\s*([A-Z ]+?)\s+", up)                    # '0514)TP_ CHF3WJK6701 …'
    if m and m.group(1).replace(" ", "") in _FACTORY:
        return _FACTORY[m.group(1).replace(" ", "")]
    for alias in sorted((a for a in config.FACTORY_ALIASES if len(a) >= 4), key=len, reverse=True):
        if re.search(r"(?<![A-Z])" + re.escape(alias) + r"(?![A-Z])", up):
            return config.FACTORY_ALIASES[alias]
    return None


def _season(text: str) -> str | None:
    m = SEASON_RE.search(norm_key(text))
    if not m:
        return None
    yy, ss = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
    return yy + ("FW" if ss == "AW" else ss)               # MIZUNO writes 26AW for the 26FW season


def _date(text: str, year_hint: int | None = None) -> dt.date | None:
    t = nfc(text)
    for rx, fmt in ((r"^(\d{6})(?!\d)", "%y%m%d"), (r"(?<!\d)(20\d{6})(?!\d)", "%Y%m%d")):
        m = re.search(rx, t)
        if m:
            try:
                return dt.datetime.strptime(m.group(1), fmt).date()
            except ValueError:
                pass
    m = re.search(r"\((\d{2})-(\d{2})-(\d{2})\)", t)                  # 'BI7138U01(26-08-13).xlsx'
    if m:
        try:
            return dt.date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.match(r"^(\d{2})(\d{2})\s*[).]", t)                      # '0514)TP_ …': month/day, year from the folder
    if m and year_hint:
        try:
            return dt.date(year_hint, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    return None


def describe(path: Path, root: Path) -> dict:
    """Metadata of one document from its name and folders (no file access beyond the name)."""
    name = nfc(path.name)
    try:
        parts = [nfc(p) for p in path.relative_to(root).parts[:-1]]
    except ValueError:
        parts = []
    depth = LOCAL_DEPTH.get(parts[0], len(parts)) if parts else 0
    local, klmas = parts[:depth], list(reversed(parts[depth:]))     # KLMAS folders, innermost first
    out = dict(file_name=name, ext=path.suffix.lower() or None, path_hash=hashlib.sha1(
        "/".join(parts + [name]).encode()).hexdigest()[:16], meta_source=None)
    sources = [("file_name", name)] + [("email_folder", f) for f in klmas]
    for field, fn in (("customer", _customer), ("factory", _factory), ("season", _season)):
        out[field] = next((v for _, t in sources if (v := fn(t))), None)
    styles, src = [], None
    for where, t in sources:
        found = _codes(t)
        if found:
            styles, src = found, where
            break
    if local and len(local) >= 4 and (not styles or not out["factory"]):   # STYLES/<cust>/<season>/<style> - <factory>
        style_dir, _, fac = local[3].partition(" - ")
        if not styles:
            styles, src = _codes(style_dir), "local_folder"
        out["factory"] = out["factory"] or config.FACTORY_ALIASES.get(norm_key(fac.split(" - ")[0]))
    if local and not out["customer"]:
        out["customer"] = _customer(local[1]) if len(local) > 1 else None
        src = src or "local_folder"
    if local and not out["season"] and len(local) > 2:
        out["season"] = _season(local[2])
    out["style_candidates"] = ",".join(styles) or None
    out["meta_source"] = src or ("file_name" if out["customer"] else None)
    ext = out["ext"] or ""
    out["doc_kind"] = ("CAD_PATTERN" if ext in CAD_EXT else "ARCHIVE" if ext in ARCHIVE_EXT else "IMAGE"
                       if ext in IMAGE_EXT else "LINK" if ext in LINK_EXT else _first_rule(KIND_RULES, name) or "OTHER")
    out["stage"] = _first_rule(STAGE_RULES, name, *klmas)
    folder_date = next((d for f in klmas if (d := _date(f))), None)
    out["doc_date"] = _date(name, folder_date.year if folder_date else None) or folder_date
    return out
