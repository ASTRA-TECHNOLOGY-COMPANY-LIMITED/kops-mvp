"""Build the DW: discover sources -> manifest -> register -> parse -> load raw/stg -> run SQL models.

The database is rebuilt every time (idempotent): delete build/kops.duckdb and recreate it from the files.
The manifest (manifest.py) remembers size/mtime/sha256 of every file, so unchanged files are not hashed again.
"""
from __future__ import annotations

import datetime as dt
import re
import time
import traceback
from pathlib import Path

import duckdb

from . import config, manifest
from .excel import open_workbook
from .ingest import (emails, meeting_notes, order_recap, order_recap_generic, production_plan, production_status,
                     shipment_status)
from .util import norm_key

SQL_DIR = config.DW_DIR / "sql"


class Ctx:
    """Collects data issues for the file being parsed."""

    def __init__(self):
        self.issues = []
        self.file_id = None

    def issue(self, severity, code, entity, message, location=None):
        self.issues.append(dict(file_id=self.file_id, severity=severity, code=code, entity=str(entity),
                                message=message, location=location))


# Known source types that have no parser yet (Phase 1 tasks): registered and skipped without a warning.
PENDING = [
    ("DAILY PRODUCTION REPORT", "daily_production", "Parser planned in Phase 1 (M1-02)"),
    ("KLMAS INSPECTION REPORT (FORM)", "inspection_form", "Blank inspection form (template, not data)"),
    ("INSPECTION REPORT", "inspection_tracker", "Parser planned in Phase 1 (M1-06)"),
    ("INPUT DATA", "qc_third_party", "Third-party QC database; parser proposed (M1-12)"),
]
# CHALLENGER ORDER RECAPs use the detailed fixed-column parser; other customers the header-driven one.
CHALLENGER_KEYS = ("CHALLENGER", "CLGR")
EMAIL_EXT = (".eml", ".pdf", ".msg")


def _in_inbox(path: Path) -> bool:
    return any(d in path.parents for d in config.INBOX_DIRS)


def classify(path: Path):
    """Return (source_type, parser, season) from the file name, or (type, None, None) if not parsed."""
    name = path.name.upper().replace("_", " ")   # '…_27SS_PRODUCTION_PLAN' -> '… 27SS PRODUCTION PLAN'
    season = (m.group(0) if (m := re.search(r"\b2\d(SS|FW)\b", name)) else None)
    ext = path.suffix.lower()
    if _in_inbox(path) and ext in EMAIL_EXT:
        return "email", "emails", season
    if ext in (".xlsx", ".xlsb", ".xlsm"):
        if "ORDER RECAP" in name and any(k in name for k in CHALLENGER_KEYS):
            return "excel", "order_recap", season
        if "ORDER RECAP" in name:
            return "excel", "order_recap_ext", season
        if "PRODUCTION PLAN" in name:
            return "excel", "production_plan", season
        if "SHIPMENT STATUS" in name:
            return "excel", "shipment_status", season
        if "PRODUCTION AND SHIPPING STATUS" in name:
            return "excel", "production_status", season
        for key, stype, _ in PENDING:
            if stype and key in name:
                return stype, None, season
        return "excel", None, season
    if ext == ".docx":
        return "meeting_note", "meeting_notes", season
    if ext == ".eml":
        return "email", "emails", season
    if ext in (".pdf", ".jpg", ".jpeg", ".png"):
        return "reference", None, None
    return "other", None, None


def file_date(name: str):
    m = re.match(r"^(\d{6})", name)
    try:
        return dt.datetime.strptime(m.group(1), "%y%m%d").date() if m else None
    except ValueError:
        return None


def discover():
    """All files under raw-docs (recursively) plus inbox .eml files.
    Folders starting with '_' (e.g. _DUPLICATES, _REORG) and hidden files are ignored."""
    files = []
    if config.RAW_DOCS_DIR.exists():
        for p in sorted(config.RAW_DOCS_DIR.rglob("*")):
            rel = p.relative_to(config.RAW_DOCS_DIR).parts
            if not p.is_file() or any(x.startswith(("_", ".")) for x in rel) or p.name.startswith("~$"):
                continue
            if p.suffix.lower() in (".eml", ".md", ".tsv", ".sh") or _in_inbox(p):
                continue                      # emails come from INBOX_DIRS; docs/scripts are not sources
            files.append(p)
    for d in config.INBOX_DIRS:                # emails: .eml / PDF export / .msg, any sub-folder (gmail/, pdf/ ...)
        if d.exists():
            files += sorted(p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in EMAIL_EXT
                            and not any(x.startswith(("_", ".")) for x in p.relative_to(d).parts))
    return files


def build(verbose=True) -> Path:
    t0 = time.time()
    run_id = manifest.new_run_id()
    entries, removed, n_hashed = manifest.scan(discover(), run_id, manifest.load())
    t_scan = time.time() - t0
    config.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    con = duckdb.connect(str(config.DB_PATH))
    con.execute((SQL_DIR / "00_raw.sql").read_text())
    _load_reference(con)

    seen, registry = {}, []
    for i, entry in enumerate(entries, start=1):
        path, digest = entry.path, entry.sha256
        stype, parser, season = classify(path)
        ctx = Ctx()
        ctx.file_id = i
        rec = dict(file_id=i, file_name=path.name, rel_path=_rel(path), source_type=stype, parser=parser,
                   season=season, file_date=file_date(path.name), report_date=None, sha256=digest,
                   size_bytes=entry.size_bytes, is_sample=config.DW_DIR in path.parents,
                   status="LOADED", is_current=False, rows_loaded=0, message=None, loaded_at=dt.datetime.now(),
                   family=None)
        if digest in seen:
            rec.update(status="DUPLICATE", message=f"Same content as file_id {seen[digest]}")
            ctx.issue("INFO", "DUPLICATE_FILE", path.name, rec["message"], path.name)
        elif parser is None:
            pending = next((m for _, s, m in PENDING if s == stype), None)
            rec.update(status="SKIPPED", message=pending or ("Reference document - not parsed" if stype == "reference"
                                                             else "Unknown template"))
            if stype == "excel":
                ctx.issue("WARN", "UNKNOWN_TEMPLATE", path.name, "Excel file not matched to a parser", path.name)
        else:
            seen[digest] = i
            try:
                tables, report_date, family = _parse(path, parser, season, digest, ctx)
                rec["report_date"], rec["family"] = report_date, family
                if parser in ("order_recap_ext", "production_plan"):
                    seasons = {r["season"] for rows in tables.values() for r in rows if r.get("season")}
                    if len(seasons) == 1:
                        rec["season"] = seasons.pop()        # sheet title wins over the file name
                rec["rows_loaded"] = _insert_all(con, tables, i)
            except Exception as e:  # keep going: one bad file must not stop the build
                rec.update(status="FAILED", message=f"{type(e).__name__}: {e}")
                ctx.issue("ERROR", "PARSE_FAILED", path.name, rec["message"], path.name)
                if verbose:
                    traceback.print_exc()
        registry.append(rec)
        _insert(con, "etl.data_issue", ctx.issues)
        if verbose:
            print(f"  [{rec['status']:9}] {path.name}  rows={rec['rows_loaded']}  issues={len(ctx.issues)}")
    # Several versions of the same report may sit in raw-docs: the newest per (template, season, family) is
    # current. Order by the date in the file name first: the 'UP DATE' cell inside a file is typed by hand and
    # has gone backwards between versions (BPK 261021 says 07/09).
    latest = {}
    for r in registry:
        if r["status"] != "LOADED":
            continue
        if r["parser"] in ("emails", "meeting_notes"):
            r["is_current"] = True
            continue
        key = (r["parser"], r["season"], r["family"])
        rank = (r["file_date"] or r["report_date"] or dt.date.min, r["report_date"] or dt.date.min, r["file_id"])
        if key not in latest or rank > latest[key][0]:
            latest[key] = (rank, r)
    for _, r in latest.values():
        r["is_current"] = True
    _insert(con, "etl.source_file", registry)
    t_sql = time.time()
    for f in sorted(SQL_DIR.glob("[1-9]*.sql")):
        con.execute(f.read_text())
    t_sql = time.time() - t_sql
    run = dict(run_id=run_id, started_at=dt.datetime.fromtimestamp(t0), seconds=round(time.time() - t0, 2),
               n_files=len(entries), n_new=sum(e.change == "NEW" for e in entries),
               n_changed=sum(e.change == "CHANGED" for e in entries), n_removed=len(removed), n_hashed=n_hashed,
               n_parsed=sum(r["status"] in ("LOADED", "FAILED") for r in registry), n_cached=0,
               n_failed=sum(r["status"] == "FAILED" for r in registry), n_quarantined=0, workers=1,
               scan_seconds=round(t_scan, 2), parse_seconds=0.0, load_seconds=0.0, sql_seconds=round(t_sql, 2),
               peak_rss_mb=_peak_rss_mb())
    _save_manifest(con, entries, removed, run)
    con.close()
    if verbose:
        print(f"Built {config.DB_PATH} in {time.time() - t0:.1f}s "
              f"({run['n_files']} files: {run['n_new']} new, {run['n_changed']} changed, {n_hashed} hashed)")
    return config.DB_PATH


def _save_manifest(con, entries, removed, run):
    """etl.manifest / etl.run in the DB, and the persistent catalog for the next build."""
    rows = [dict(path=str(e.path), rel=e.rel, size_bytes=e.size_bytes, mtime=dt.datetime.fromtimestamp(e.mtime_ns / 1e9),
                 sha256=e.sha256, change=e.change, first_seen=e.first_seen) for e in entries]
    rows += [dict(path=r["path"], rel=r["rel"], size_bytes=r["size_bytes"], sha256=r["sha256"], change="REMOVED",
                  mtime=dt.datetime.fromtimestamp(r["mtime_ns"] / 1e9), first_seen=r["first_seen"]) for r in removed]
    _insert(con, "etl.manifest", rows)
    manifest.save(entries, run["run_id"])
    manifest.save_run(run)
    _insert(con, "etl.run", manifest.load_runs())


def _peak_rss_mb() -> float:
    import resource
    import sys
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(rss / (1 << 20) if sys.platform == "darwin" else rss / 1024, 1)   # bytes on macOS, KiB on Linux


def _parse(path, parser, season, digest, ctx):
    """-> (tables, report_date, family). family groups versions of one report (None = parser + season)."""
    if parser in ("order_recap", "shipment_status", "production_status"):
        if not season:
            raise ValueError("Season code (e.g. 26FW) not found in file name")
        wb = open_workbook(path, digest)
        mod = {"order_recap": order_recap, "shipment_status": shipment_status,
               "production_status": production_status}[parser]
        tables, report_date = mod.parse(wb, season, ctx)
        return tables, report_date or file_date(path.name), None
    if parser in ("order_recap_ext", "production_plan"):
        wb = open_workbook(path, digest)
        mod = order_recap_generic if parser == "order_recap_ext" else production_plan
        tables, report_date, family = mod.parse(wb, season, ctx, path.name, _rel(path))
        return tables, report_date or file_date(path.name), family
    if parser == "meeting_notes":
        tables, d = meeting_notes.parse(path, ctx)
        return tables, (dt.date.fromisoformat(d) if d else None), None
    if parser == "emails":
        tables, d = emails.parse(path, ctx)
        return tables, d, None
    raise ValueError(parser)


def _insert_all(con, tables: dict, file_id: int) -> int:
    n = 0
    for name, rows in tables.items():
        schema = "stg" if name.startswith("stg_") else "raw"
        table = f"{schema}.{name[4:] if name.startswith('stg_') else name}"
        for r in rows:
            r["file_id"] = file_id
        _insert(con, table, rows)
        n += len(rows)
    return n


def _insert(con, table: str, rows: list[dict]):
    if not rows:
        return
    cols = [c[0] for c in con.execute(f"DESCRIBE {table}").fetchall()]
    data = [[r.get(c) for c in cols] for r in rows]
    con.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(cols))})", data)


def _load_reference(con):
    _insert(con, "stg.factory_alias", [dict(alias_key=norm_key(k), factory_code=v)
                                       for k, v in config.FACTORY_ALIASES.items()])
    _insert(con, "stg.style_alias", [dict(alias_style=k, style_no=v, confirmed=False)
                                     for k, v in config.STYLE_ALIASES.items()])
    _insert(con, "stg.rule", [dict(rule_key=k, rule_value=str(v)) for k, v in config.RULES.items()])
    _insert(con, "stg.requirement_coverage", [dict(req_no=k, mvp_status=s, where_in_mvp=w, next_step=n)
                                              for k, (s, w, n) in config.REQUIREMENT_COVERAGE.items()])


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(config.REPO_DIR))
    except ValueError:
        return str(path)
