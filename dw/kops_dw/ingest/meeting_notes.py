"""Meeting notes (.docx): every paragraph and table goes to raw.doc_block; structured tables
(requirements, action items, decisions, meeting info) are recognised by their header row."""
from __future__ import annotations

import json
import re

import docx

from ..util import nfc

SPLIT_RE = re.compile(r"\s+/\s+")


def parse(path, ctx):
    d = docx.Document(str(path))
    blocks, section, seq = [], None, 0
    body = d.element.body
    tables = iter(d.tables)
    paras = {p._p: p for p in d.paragraphs}
    title = None
    for el in body.iterchildren():
        tag = el.tag.split("}")[-1]
        if tag == "p":
            p = paras.get(el)
            if p is None or not p.text.strip():
                continue
            style = p.style.name if p.style is not None else ""
            if style.startswith("Heading"):
                section = nfc(p.text.strip())
                title = title or section
            seq += 1
            blocks.append(dict(seq=seq, section=section, kind="heading" if style.startswith("Heading") else
                               ("bullet" if "List" in style else "paragraph"), text=nfc(p.text.strip()), table_json=None))
        elif tag == "tbl":
            t = next(tables)
            rows = [[nfc(c.text.strip()) for c in r.cells] for r in t.rows]
            seq += 1
            blocks.append(dict(seq=seq, section=section, kind="table", text=None,
                               table_json=json.dumps(rows, ensure_ascii=False)))
    for b in blocks:
        b["doc_title"] = title

    meeting = dict(title=title, meeting_date=None, location=None)
    reqs, actions, decisions, attendees = [], [], [], []
    for b in blocks:
        if b["kind"] == "bullet" and b["section"] and b["section"].startswith("4."):
            head, _, rest = b["text"].partition("—")
            decisions.append(dict(no=None, topic=head.strip(), text=_vi(rest or b["text"]), raised_by=None, section=b["section"]))
        if b["kind"] != "table":
            continue
        rows = json.loads(b["table_json"])
        hdr = " ".join(rows[0]).upper()
        if "일시" in rows[1][0] if len(rows) > 1 else False:
            for r in rows[1:]:
                if "일시" in r[0]:
                    m = re.search(r"\d{4}-\d{2}-\d{2}", r[1])
                    meeting["meeting_date"] = m.group(0) if m else None
                elif "장소" in r[0]:
                    meeting["location"] = _vi(r[1])
        elif "성명" in hdr:
            for r in rows[1:]:
                attendees.append(dict(company=r[0], name=r[1], title=_vi(r[2]), role=_vi(r[3])))
        elif rows[0][0] == "#" and ("기능" in hdr or "CHỨC NĂNG" in hdr):
            # Group cells are 'KR / VN' on first use, then KR only: reuse the first translation.
            kr_vi = {}
            for r in rows[1:]:
                parts = SPLIT_RE.split(r[1])
                kr = parts[0].strip()
                if len(parts) > 1:
                    kr_vi[kr] = parts[-1].strip()
                reqs.append(dict(req_no=int(r[0]), req_group=kr_vi.get(kr, r[1]), text_kr=r[2], text_vi=r[3], raised_by=r[4]))
        elif "담당" in rows[0][0]:
            for r in rows[1:]:
                actions.append(dict(owner=r[0], item_kr=r[1], item_vi=r[2], due=_vi(r[3])))
        elif rows[0][0] == "#" and "발언" in hdr:
            for r in rows[1:]:
                decisions.append(dict(no=int(r[0]), topic=None, text=r[2], raised_by=r[3], section=b["section"]))
    if not reqs:
        ctx.issue("WARN", "DOC_NO_REQUIREMENTS", path.name, "No requirement table recognised", path.name)
    return dict(doc_block=blocks, stg_requirement=reqs, stg_action_item=actions, stg_decision=decisions,
                stg_attendee=attendees, stg_meeting=[meeting]), meeting["meeting_date"]


def _vi(s: str) -> str:
    """Bilingual cells are 'KR / VN': keep the Vietnamese half when present."""
    parts = SPLIT_RE.split(s or "")
    return parts[-1].strip() if len(parts) > 1 else (s or "").strip()
