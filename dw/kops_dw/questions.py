"""Open questions to KLMAS (analys-docs/open_questions.md) referenced from code, docs and the dashboard (E-01).

Question codes are renumbered when the question file changes (appendix of open_questions.md). Every code used in
the repo is registered here with a keyword of its heading, and the check below compares both with the file: after
the next renumbering the check turns red instead of the code silently pointing at another question.
The file is only read, never written.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import config

# Qnn / Dn -> keyword that must appear in the heading (Qnn) or in the "Cần gửi" cell (Dn), case-insensitive
TOPICS = {
    "Q03": "báo cáo sản xuất ngày",
    "Q04": "giảm 20%",
    "Q05": "mã khác nhau",
    "Q06": "CHE",
    "Q07": "980",
    "Q09": "nhà máy chính thức",
    "Q10": "hàng mẫu",
    "Q11": "bộ 2 món",
    "Q13": "đủ đơn",
    "Q19": "email của các bên",
    "Q21": "đúng hạn",
    "Q22": "TODAY",
    "Q23": "HAGACO",
    "Q24": "Số lỗi",
    "Q25": "REJECT",
    "Q26": "RDD",
    "Q27": "lô xuất",
    "Q32": "thứ Bảy",
    "Q33": "Lịch mùa",
    "Q38": "mã lỗi",
    "Q47": "MIZUNO",
    "Q50": "phân công",
    "D2": "Báo cáo ngày còn thiếu",
    "D3": "kiểm hàng",
}

# assumption_id (dw/docs/assumptions.md) -> question or data request that would replace it (None = no code yet)
ASSUMPTION_QUESTIONS = {
    "ASM-SEASON-01": "Q33",
    "ASM-DAILY-01": "Q23",
    "ASM-DAILY-02": "Q22",
    "ASM-FRESH-01": "Q32",
    "ASM-QC-01": "Q24",
    "ASM-QC-02": "Q25",
    "ASM-LINK-01": "Q27",
    "ASM-ONTIME-01": "Q21",
    "ASM-SCORE-01": "Q21",
    "ASM-SIM-01": None,
    "ASM-SIM-02": "D2",
    "ASM-SIM-03": "D3",
    "ASM-SIM-04": None,
    "ASM-SIM-05": "Q38",
}

_HEAD = re.compile(r"^###\s+(Q\d{2})\.\s+(.+?)\s*$", re.M)
_DATA = re.compile(r"^\|\s*(D\d{1,2})\s*\|\s*([^|]+?)\s*\|", re.M)
_REF = re.compile(r"(?<![\w-])Q\d{2}(?![\w])")


def load(path: Path | None = None) -> dict[str, str]:
    """{code: title} for every Qnn heading and Dn data request in the question file ({} when it is missing)."""
    p = Path(path or config.QUESTIONS_FILE)
    if not p.is_file():
        return {}
    text = p.read_text(encoding="utf-8")
    text = text.split("\n# Phụ lục", 1)[0]          # the appendix lists old codes
    out = {q: re.sub(r"\s*\*\(.*?\)\*\s*$", "", t) for q, t in _HEAD.findall(text)}
    out.update({d: t.split(":")[0].strip() for d, t in _DATA.findall(text)})
    return out


def scan_files() -> list[Path]:
    roots = [config.DW_DIR / d for d in ("kops_dw", "sql", "templates", "docs")]
    files = [f for r in roots if r.is_dir() for f in r.rglob("*")
             if f.suffix in (".py", ".sql", ".html", ".md", ".json") and "vendor" not in f.parts]
    files += [f for f in (config.DW_DIR / "README.md", config.REPO_DIR / "README.md", config.REPO_DIR / "CLAUDE.md")
              if f.is_file()]
    return sorted(set(files))


def references() -> dict[str, list[str]]:
    """{Qnn: [file:line, ...]} for every question code written in code / docs / templates."""
    refs: dict[str, list[str]] = {}
    for f in scan_files():
        if f.name == "questions.py":
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for q in _REF.findall(line):
                refs.setdefault(q, []).append(f"{f.relative_to(config.REPO_DIR) if f.is_relative_to(config.REPO_DIR) else f}:{i}")
    return refs


def check() -> list[tuple[str, bool, str]]:
    """(name, ok, detail) rows for checks.run_checks."""
    titles = load()
    if not titles:
        return [("Question codes: open_questions.md readable", False, f"missing {config.QUESTIONS_FILE}")]
    out = []
    bad = [f"{c} ({k!r} not in {titles.get(c, 'missing')!r})" for c, k in TOPICS.items()
           if k.lower() not in titles.get(c, "").lower()]
    out.append(("Question codes: registered topics match open_questions.md headings", not bad,
                "; ".join(bad) or f"{len(TOPICS)} codes"))
    refs = references()
    unreg = [f"{q} at {', '.join(w[:3])}" for q, w in sorted(refs.items()) if q not in TOPICS]
    out.append(("Question codes: every Qnn in code / docs / templates is registered", not unreg,
                "; ".join(unreg) or f"{sum(map(len, refs.values()))} references, {len(refs)} codes"))
    asm = [f"{a} -> {q}" for a, q in ASSUMPTION_QUESTIONS.items() if q and q not in TOPICS]
    out.append(("Question codes: every assumption points at a registered question", not asm, "; ".join(asm) or
                f"{len(ASSUMPTION_QUESTIONS)} assumptions"))
    return out


def for_dashboard() -> dict:
    """Question titles for the dashboard chips, read from the file at render time (no hard-coded titles)."""
    titles = load()
    return {"questions": {c: titles.get(c) for c in TOPICS}, "assumptions": ASSUMPTION_QUESTIONS}
