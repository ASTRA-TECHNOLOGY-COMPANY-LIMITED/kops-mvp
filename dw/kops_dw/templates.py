"""Template fingerprints (H-04): recognise the layout of an Excel file before trusting its parser.

Fingerprint = hash of the header rows of the first sheet: among rows 1-6, the row with the most text labels
(cells without digits, normalised with norm_key) plus neighbour rows with at least half as many (two-level
headers), in order. It stays the same across versions of a report
(data changes, the header does not) and changes when a column is renamed, added, removed or moved.

Known fingerprints are listed in dw/templates/known_templates.json (committed: column labels only, no data).
A file whose fingerprint is not known for its parser is NOT loaded: status UNKNOWN_TEMPLATE, listed in the
quarantine report with its labels, so a person decides (accept the layout, or adjust/write a parser) instead of the
DW silently loading wrong numbers from an older season's layout.

  python -m kops_dw templates                 unknown templates of the last build (labels, files)
  python -m kops_dw templates accept FP ...   accept fingerprint(s), then rebuild and check the numbers
  python -m kops_dw templates accept --loaded accept the fingerprints of every file loaded by the last build
KOPS_TEMPLATE_CHECK=0 turns the check off (rollback: files load as before H-04).
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import re
import sys

import openpyxl

from . import config
from .util import norm_key

REGISTRY = config.DW_DIR / "templates" / "known_templates.json"
HEADER_ROWS = 6


def _label(v):
    if not isinstance(v, str):
        return None
    k = norm_key(v)
    return k if k and not re.search(r"\d", k) and len(k) <= 60 else None


def fingerprint(xlsx_path) -> dict:
    """-> {fp, sheet, row(s), labels} of the first sheet (xlsx/xlsm; .xlsb must be converted first)."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        rows = [[lab for lab in map(_label, r) if lab]
                for r in ws.iter_rows(min_row=1, max_row=HEADER_ROWS, max_col=200, values_only=True)]
    finally:
        wb.close()
    if not any(rows):
        return dict(fp=hashlib.sha1(b"").hexdigest()[:12], sheet=ws.title, row=None, labels=[])
    top = max(range(len(rows)), key=lambda i: len(rows[i]))
    lo = hi = top        # two-level headers: neighbour rows with at least half as many labels (not legend/data rows)
    while lo > 0 and len(rows[lo - 1]) * 2 >= len(rows[top]):
        lo -= 1
    while hi + 1 < len(rows) and len(rows[hi + 1]) * 2 >= len(rows[top]):
        hi += 1
    labels = [lab for r in rows[lo:hi + 1] for lab in r]
    return dict(fp=hashlib.sha1("|".join(labels).encode()).hexdigest()[:12], sheet=ws.title,
                row=f"{lo + 1}-{hi + 1}" if hi > lo else str(top + 1), labels=labels)


def enabled() -> bool:
    return config.TEMPLATE_CHECK and REGISTRY.exists()


def known() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}


def is_known(fp: str | None, parser: str, registry: dict | None = None) -> bool:
    reg = known() if registry is None else registry
    return bool(fp) and fp in reg and reg[fp]["parser"] == parser


def nearest(labels: list[str], parser: str, registry: dict | None = None) -> str:
    """'vs <fp> (<example>): -missing +new' against the most similar known layout of the same parser."""
    reg = known() if registry is None else registry
    best, score = None, -1.0
    for fp, e in reg.items():
        if e["parser"] == parser:
            s = difflib.SequenceMatcher(None, e["labels"], labels, autojunk=False).ratio()
            if s > score:
                best, score = fp, s
    if best is None:
        return f"no known layout for parser {parser}"
    old = reg[best]["labels"]
    missing = [x for x in old if x not in labels]
    new = [x for x in labels if x not in old]
    moved = "" if missing or new else "; same labels, different order/count"
    return (f"closest known {best} ({reg[best]['example']}): missing [{', '.join(missing[:10])}], "
            f"new [{', '.join(new[:10])}]{moved}")


def accept(entries: list[dict]):
    """entries: dicts with fp, parser, sheet, labels, example (file name)."""
    reg = known()
    for e in entries:
        reg.setdefault(e["fp"], dict(parser=e["parser"], sheet=e["sheet"], labels=e["labels"], example=e["example"],
                                     accepted=dt.date.today().isoformat()))
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(dict(sorted(reg.items(), key=lambda kv: (kv[1]["parser"], kv[0]))),
                                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cli(argv):
    import duckdb
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    q = """SELECT template_fp, parser, template_sheet, template_labels, file_name, status FROM etl.source_file
           WHERE template_fp IS NOT NULL"""
    rows = [dict(zip(["fp", "parser", "sheet", "labels", "example", "status"], r)) for r in con.execute(q).fetchall()]
    con.close()
    for r in rows:
        r["labels"] = (r["labels"] or "").split(" | ")
    if argv[:1] == ["accept"]:
        if "--loaded" in argv:
            pick = [r for r in rows if r["status"] == "LOADED"]
        else:
            fps = set(argv[1:])
            pick = [r for r in rows if r["fp"] in fps]
            missing = fps - {r["fp"] for r in pick}
            if missing:
                sys.exit(f"Fingerprint(s) not seen in the last build: {', '.join(sorted(missing))}")
        accept(pick)
        print(f"{len({(r['fp'], r['parser']) for r in pick})} template(s) recorded in {REGISTRY}. Run the build again.")
        return
    reg = known()
    unknown = {}
    for r in rows:
        if not is_known(r["fp"], r["parser"], reg):
            unknown.setdefault((r["fp"], r["parser"]), []).append(r)
    if not unknown:
        print(f"All {len(rows)} Excel files match a known template ({len(reg)} known).")
        return
    for (fp, parser), files in unknown.items():
        print(f"\n{fp}  parser={parser}  sheet='{files[0]['sheet']}'  {len(files)} file(s)")
        print("  labels: " + " | ".join(files[0]["labels"]))
        for f in files[:10]:
            print(f"  - {f['example']}")
    print("\nCheck the labels against the parser; if it reads them correctly: "
          "python -m kops_dw templates accept <fp>  (then rebuild and check the numbers)")
