"""Parse open_questions.md into a block list (JSON) for the docx renderer."""
import json, re, sys, html

src = open(sys.argv[1], encoding="utf-8").read()
src = src.split("\n# Phụ lục")[0]          # internal appendix is not sent to KLMAS
lines = src.splitlines()

INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)")


def runs(text):
    text = html.unescape(text)
    out = []
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**"):
            out.append({"t": part[2:-2], "b": True})
        elif part.startswith("`"):
            out.append({"t": part[1:-1], "code": True})
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append({"t": part[1:-1], "i": True})
        else:
            out.append({"t": part})
    return out


blocks, i = [], 0
section = None
tier = None
while i < len(lines):
    raw = lines[i]
    s = raw.strip()
    if not s or s == "---":
        i += 1
        continue
    if s.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                rows.append([runs(c) for c in cells])
            i += 1
        indent = len(raw) - len(raw.lstrip())
        blocks.append({"k": "table", "rows": rows, "indent": 1 if indent else 0})
        continue
    if s.startswith("```"):
        i += 1
        code = []
        while i < len(lines) and not lines[i].strip().startswith("```"):
            code.append(lines[i]); i += 1
        blocks.append({"k": "code", "lines": code}); i += 1
        continue
    m = re.match(r"^(#{1,3}) (.*)$", s)
    if m:
        lvl, title = len(m.group(1)), m.group(2)
        q = re.match(r"^(Q[\w-]+)\. (.*)$", title)
        if lvl == 3 and q:
            note = None
            nm = re.search(r"\s*\*\((.*)\)\*\s*$", q.group(2))
            t = q.group(2)
            if nm:
                note, t = nm.group(1), q.group(2)[:nm.start()]
            blocks.append({"k": "q", "id": q.group(1), "title": t, "note": note, "section": section, "tier": tier})
        else:
            blocks.append({"k": f"h{lvl if lvl < 3 else 2}", "runs": runs(title), "text": title})
            if lvl <= 2:
                section = title
            if lvl == 1:
                tier = title
        i += 1
        continue
    if s.startswith("**Trả lời của KLMAS:**"):
        blocks.append({"k": "answer"}); i += 1
        continue
    m = re.match(r"^(\s*)(?:[-*]|(\d+)\.) (.*)$", raw)
    if m:
        lvl = len(m.group(1)) // 2
        blocks.append({"k": "li", "lvl": min(lvl, 2), "num": m.group(2), "runs": runs(m.group(3))})
        i += 1
        continue
    if s.startswith(">"):
        blocks.append({"k": "note", "runs": runs(s.lstrip("> "))}); i += 1
        continue
    blocks.append({"k": "p", "runs": runs(s)}); i += 1

json.dump(blocks, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print(len(blocks), "blocks;", sum(b["k"] == "q" for b in blocks), "questions;", sum(b["k"] == "answer" for b in blocks), "answers")
