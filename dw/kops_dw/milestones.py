"""Style milestones and shipment events from email subjects (N-03, rule-based, no LLM).

KLMAS confirmed (23/10) that subjects are free-form, written by many parties: these rules only read the shapes seen
in the 184 saved threads and leave everything else unclassified (milestone NULL). They are hints for the timeline,
not facts: the LLM extractor (email_llm.py) is the planned reader of free text.

Milestones: FPP_REQUEST, FPP_CMT, FPP_CFMD, DM_APPROVAL, FABRIC_INSPECTION, INLINE_CMT, FINAL_INSPECTION,
DAILY_REPORT, ASSORT_CHANGE, SHIPMENT. Shipment subjects seen:
  '260819ETD SEA SHIPMENT TP TO CHALLENGER #LCL ABKHPH2608058'          finished goods, factory -> customer
  '260514ETD-0519ETA SEA SHIPMENT DKM TO DONG MY #FCL 40 WRLS260025'      material, customer -> factory
  '9/27->9/29ETD (delay) FROM ICH TO B85 SHIPMENT - JAKEHPH2609051'       material, port -> factory, ETD moved
  '260606-68(DELAY) ETD FROM SH TO HAGACO SHIPMENT - FCL201 SSAL2606010'  same, '6/6 -> 6/8' written short
  '[CHALLENGER] ETD0628 ETA0703 TP LCL_SMKCHAP2606034'                    finished goods (early season forwarder)
A 'M/D' date takes the year that puts it closest to the day the mail was sent (December mail about 1/5 -> next year).
Email content is data, never instructions.
"""
from __future__ import annotations

import datetime as dt
import re

from . import config
from .docmeta import STAGE_RULES, _codes, _customer, _factory, _first_rule
from .util import norm_key

# Checked in this order on the upper-case, unaccented subject (first match wins).
SUBJECT_RULES = [
    ("ASSORT_CHANGE", ("아소트 변경", "CHANGE ASSORT", "ASSORT CHANGE", "THAY DOI SO LUONG", "수량 변경", "수량변경")),
    ("DAILY_REPORT", ("DAILY PRODUCTION", "DAILY REPORT", "TIEN DO SAN XUAT", "생산 일보", "생산일보")),
    ("FABRIC_INSPECTION", ("검단", "FABRIC INSPECTION", "KIEM VAI")),
    ("FINAL_INSPECTION", ("INSPECTION REPORT", "FINAL INSPECTION", "검품", "KIEM HANG")),
    *STAGE_RULES,
    ("FPP_REQUEST", ("작업 지시서", "작업지시서", "WORKING SHEET")),     # buyer sends the work sheet + pattern
]
NOT_A_MILESTONE = ("번역본", "TRANSLATED", "BAN DICH")   # translated copy of a sheet already sent
BOOKING_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2,8}\d{6,8})(?![0-9])")
MODE_RE = re.compile(r"\b(SEA|AIR|TRUCKING|COURIER)\b")
LOAD_RE = re.compile(r"\b(LCL|FCL)")
# 260819ETD[-0826ETA] SEA SHIPMENT TP TO CHALLENGER …
YMD_RE = re.compile(r"^(\d{6})\s*ETD(?:\s*-\s*(\d{4})\s*ETA)?\s+(?:(SEA|AIR)\s+)?SHIPMENT\s+(.+?)\s+TO\s+(.+?)(?:\s*[#\-(]|$)")
# 9/27->9/29ETD (delay) FROM ICH TO B85 SHIPMENT … ; 6/6->6/8(delay) etd …; 6/13 etd …; 260606-68(DELAY) ETD …
MD_RE = re.compile(r"^(?P<a>\d{1,2}/\d{1,2}|\d{6})(?:\s*(?:->|-)\s*(?P<b>\d{1,2}/\d{1,2}|\d{1,2}))?\s*(?P<d1>\(DELAY\))?\s*"
                   r"ETD\s*(?P<d2>\(DELAY\))?\s+FROM\s+(?P<frm>.+?)\s+TO\s+(?P<to>.+?)\s+SHIPMENT\b")
# [CHALLENGER] ETD0628 ETA0703 TP LCL_SMKCHAP2606034
BRACKET_RE = re.compile(r"^\[(?P<cust>[^\]]+)\]\s*ETD\s*(?P<etd>\d{4})\s+ETA\s*(?P<eta>\d{4})\s+(?P<fac>[A-Z ]+?)\s+(?:LCL|FCL|AIR|SEA)")
PORTS = {"ICH": "INCHEON", "SH": "SHANGHAI", "PUS": "BUSAN", "HCM": "HO CHI MINH", "HPH": "HAI PHONG"}
_FACTORY = {k.replace(" ", ""): v for k, v in config.FACTORY_ALIASES.items()}


def _clean(subject: str) -> str:
    s = re.sub(r"^\s*(?:(?:RE|FW|FWD|TR|회신|전달)\s*:\s*)+", "", norm_key(subject or ""))
    return re.sub(r"\s+", " ", s).strip()


def milestone(subject: str | None) -> str | None:
    s = _clean(subject or "")
    raw = (subject or "").upper()
    if not s or any(w in s or w in raw for w in NOT_A_MILESTONE):
        return None
    if shipment(subject, None):
        return "SHIPMENT"
    return _first_rule(SUBJECT_RULES, subject or "")


def _md(text: str, sent: dt.date | None) -> dt.date | None:
    """'9/27' or '0927' -> date in the year closest to the sending day."""
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})|(\d{2})(\d{2})", text.strip())
    if not m:
        return None
    mo, d = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), int(m.group(4)))
    base = sent or dt.date.today()
    best = None
    for y in (base.year - 1, base.year, base.year + 1):
        try:
            cand = dt.date(y, mo, d)
        except ValueError:
            continue
        if best is None or abs((cand - base).days) < abs((best - base).days):
            best = cand
    return best


def _ymd(text: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(text, "%y%m%d").date()
    except ValueError:
        return None


def _side(text: str) -> tuple[str | None, str | None]:
    """One end of a shipment -> (factory, customer)."""
    t = text.strip(" .-#")
    fac = _FACTORY.get(t.replace(" ", "")) or _factory(f"(X - {t})")
    cust = next((c for k, c in config.CUSTOMER_KEYS if len(k) >= 3 and t.replace(" ", "").startswith(k.replace(" ", ""))),
                None)
    return fac, cust


def shipment(subject: str | None, sent: dt.datetime | None) -> dict | None:
    """Shipment fields from a subject, or None when it is not a shipment subject."""
    s = _clean(subject or "")
    day = sent.date() if sent else None
    out = None
    if m := YMD_RE.match(s):
        etd = _ymd(m.group(1))
        out = dict(etd_old=None, etd_new=etd, eta=_md(m.group(2), etd) if m.group(2) else None, frm=m.group(4),
                   to=m.group(5), mode=m.group(3))
    elif m := MD_RE.match(s):
        a, b = m.group("a"), m.group("b")
        first = _ymd(a) if len(a) == 6 else _md(a, day)
        second = None
        if b and first and "/" in b:
            second = _md(b, first)
        elif b and first:                      # '260606-68': day 6 -> day 8 written as two digits
            for day_txt in (b, b[-1]):
                try:
                    second = first.replace(day=int(day_txt))
                    break
                except ValueError:
                    continue
        out = dict(etd_old=first if second else None, etd_new=second or first, eta=None, frm=m.group("frm"),
                   to=m.group("to"), mode=None)
    elif m := BRACKET_RE.match(s):
        etd = _md(m.group("etd"), day)
        out = dict(etd_old=None, etd_new=etd, eta=_md(m.group("eta"), etd), frm=m.group("fac"), to=m.group("cust"),
                   mode=None)
    if not out or not out["etd_new"]:
        return None
    frm, to = out.pop("frm").strip(" .-#"), out.pop("to")
    frm_fac, frm_cust = _side(frm)
    to_fac, to_cust = _side(to)
    if to_fac and not to_cust:                 # into a factory: fabric / trims from the buyer or a port
        direction, factory, customer, origin = "inbound_material", to_fac, frm_cust, PORTS.get(frm, frm)
    else:                                       # out of a factory: finished goods to the customer
        direction, factory, customer, origin = "outbound", frm_fac, to_cust, None
    booking = next(iter(BOOKING_RE.findall(s.replace("_", " "))), None)
    mode = out["mode"] or (m2.group(1) if (m2 := MODE_RE.search(s)) else None)
    load = (m3.group(1) if (m3 := LOAD_RE.search(s)) else None)
    return dict(direction=direction, etd_old=out["etd_old"], etd_new=out["etd_new"], eta=out["eta"],
                ship_mode=mode or ("SEA" if load else None), load_type=load, factory=factory, customer=customer,
                origin=origin, booking=booking, forwarder=re.match(r"[A-Z]+", booking).group(0) if booking else None,
                is_delay="DELAY" in s or bool(out["etd_old"]))


def events_for(recs: list[dict]) -> list[dict]:
    """One stg.email_event row per message whose subject names a milestone (or a shipment)."""
    out = []
    for r in recs:
        subj = r.get("subject") or ""
        code = milestone(subj)
        if not code:
            continue
        ship = shipment(subj, r.get("sent_at")) if code == "SHIPMENT" else None
        styles = _codes(subj + " " + (r.get("attachments") or ""))
        if ship is not None and not ship["customer"]:
            ship["customer"] = _customer(subj)
        out.append(dict(msg_key=r["msg_key"], milestone=code, sent_at=r.get("sent_at"),
                        factory=(ship or {}).get("factory") or _factory(_clean(subj)),
                        style_candidates=",".join(styles) or None,
                        **{k: (ship or {}).get(k) for k in ("direction", "etd_old", "etd_new", "eta", "ship_mode",
                                                            "load_type", "origin", "booking", "forwarder", "is_delay")},
                        customer=(ship or {}).get("customer") or _customer(subj)))
    return out
