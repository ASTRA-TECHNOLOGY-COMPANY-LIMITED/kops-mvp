"""Build the DW: discover sources -> manifest -> register -> parse new files -> load raw/stg -> run SQL models.

The database is rebuilt every time (idempotent): delete build/kops.duckdb and recreate it. Parsing is incremental:
the manifest (manifest.py) remembers size/mtime/sha256 of every file, and parse results are kept in the Parquet lake
(lake.py) under a key of content + parser version (parse.py). A build only parses files whose key is not in the lake
(new, changed, renamed/moved, or parser changed) and reads everything else back from Parquet.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import re
import shutil
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path

import duckdb

from . import config, docmeta, lake, manifest, ocr, parse, templates
from .ingest import buyer_order_status
from .util import nfc, norm_key

SQL_DIR = config.DW_DIR / "sql"
Ctx = parse.Ctx

# Known source types that have no parser yet (Phase 1 tasks): registered and skipped without a warning.
PENDING = [
    ("DAILY PRODUCTION REPORT", "daily_production", "Parser planned in Phase 1 (M1-02)"),
    ("KLMAS INSPECTION REPORT (FORM)", "inspection_form", "Blank inspection form (template, not data)"),
    ("INSPECTION REPORT", "inspection_tracker", "Parser planned in Phase 1 (M1-06)"),
    ("INPUT DATA", "qc_third_party", "Third-party QC database; parser proposed (M1-12)"),
]
DOC_MESSAGE = "Metadata only: technical document / pattern (name read, file not opened)"
# CHALLENGER ORDER RECAPs use the detailed fixed-column parser; other customers the header-driven one.
CHALLENGER_KEYS = ("CHALLENGER", "CLGR")
EMAIL_EXT = (".eml", ".pdf", ".msg", ".mhtml")
MAILBOX_EXT = (".mbox", ".pst")      # whole mailboxes (ingest/mailbox.py)


def _in_inbox(path: Path) -> bool:
    return any(d in path.parents for d in config.INBOX_DIRS)


def classify(path: Path):
    """Return (source_type, parser, season) from the file name, or (type, None, None) if not parsed."""
    name = nfc(path.name).upper().replace("_", " ")   # '…_27SS_PRODUCTION_PLAN' -> '… 27SS PRODUCTION PLAN'
    season = (m.group(0) if (m := re.search(r"\b2\d(SS|FW)\b", name)) else None)
    ext = path.suffix.lower()
    if _in_inbox(path) and ext in MAILBOX_EXT:
        return "email", "mailbox", season
    if _in_inbox(path) and ext in EMAIL_EXT:
        return "email", "emails", season
    if ext in docmeta.META_ONLY_EXT:            # CAD patterns, archives, pictures, links: never opened
        return "document", None, season
    if ext in (".xlsx", ".xlsb", ".xlsm"):
        if "ORDER RECAP" in name and any(k in name for k in CHALLENGER_KEYS):
            return "excel", "order_recap", season
        if "ORDER RECAP" in name:
            return "excel", "order_recap_ext", season
        if "PRODUCTION PLAN" in name:
            return "excel", "production_plan", season
        if "SHIPPING SCHEDULE" in name:
            return "excel", "shipping_schedule", season
        if "SHIPMENT STATUS" in name:
            return "excel", "shipment_status", season
        if "PRODUCTION AND SHIPPING STATUS" in name:
            return "excel", "production_status", season
        for key, stype, _ in PENDING:
            if stype and key in name:
                return stype, None, season
        if docmeta.is_meta_only(path):           # work sheets, comments, markers ... (name only, not opened)
            return "document", None, season
        return "excel", None, season
    if ext == ".docx":
        return "meeting_note", "meeting_notes", season
    if ext in (".eml", ".mhtml"):           # .mhtml: Gmail threads saved inside style packages (STYLES/...)
        return "email", "emails", season
    if ext == ".pdf" and buyer_order_status.is_buyer_status(path.name):
        return "tracking_pdf", "buyer_order_status", season
    if ext in docmeta.OFFICE_EXT and docmeta.is_meta_only(path):
        return "document", None, season
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
            files += sorted(p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in EMAIL_EXT + MAILBOX_EXT
                            and not any(x.startswith(("_", ".")) for x in p.relative_to(d).parts))
    return files


def build(verbose=True, retry_failed=False, pins: list[str] | None = None, db_path: Path | None = None) -> Path:
    """pins: file-name prefixes that are the current version of their report family instead of the newest one
    (golden snapshots, checks.py). With pins the build writes db_path only: no manifest / run / quarantine update."""
    t0 = time.time()
    config.LAKE_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(config.LAKE_DIR / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(f"Another build is using {config.LAKE_DIR}") from None
    run_id = manifest.new_run_id()
    entries, removed, n_hashed = manifest.scan(discover(), run_id, manifest.load())
    t_scan = time.time() - t0

    versions, results = parse.parser_versions(), lake.read_results()
    check_templates, known_templates = templates.enabled(), templates.known()
    seen, registry, extra_issues, tasks, documents = {}, [], [], [], []
    for i, entry in enumerate(entries, start=1):
        path, digest = entry.path, entry.sha256
        name = nfc(path.name)                    # macOS stores names decomposed (NFD); compare and store NFC
        stype, parser, season = classify(path)
        rec = dict(file_id=i, file_name=name, rel_path=nfc(_rel(path)), source_type=stype, parser=parser,
                   season=season, file_date=file_date(name), report_date=None, sha256=digest,
                   size_bytes=entry.size_bytes, is_sample=config.DW_DIR in path.parents,
                   status="LOADED", is_current=False, rows_loaded=0, message=None, loaded_at=dt.datetime.now(),
                   family=None, parse_key=None, from_cache=False, parse_seconds=None, template_fp=None,
                   template_sheet=None, template_labels=None)
        ctx = Ctx()
        ctx.file_id = i
        if digest in seen:
            rec.update(status="DUPLICATE", message=f"Same content as file_id {seen[digest]}")
            ctx.issue("INFO", "DUPLICATE_FILE", name, rec["message"], name)
        elif parser is None:
            pending = next((m for _, s, m in PENDING if s == stype), None)
            rec.update(status="SKIPPED", message=pending or ("Reference document - not parsed" if stype == "reference"
                                                             else DOC_MESSAGE if stype == "document"
                                                             else "Unknown template"))
        elif parser in parse.EXCEL_PARSERS and entry.size_bytes > config.MAX_PARSE_MB * 1e6:
            rec.update(status="SKIPPED", message=f"Too large: {entry.size_bytes / 1e6:.0f} MB > KOPS_MAX_PARSE_MB="
                                                 f"{config.MAX_PARSE_MB:g}; not opened (metadata only)")
            ctx.issue("WARN", "FILE_TOO_LARGE", name, rec["message"], name)
            if stype == "excel":
                ctx.issue("WARN", "UNKNOWN_TEMPLATE", name, "Excel file not matched to a parser", name)
        else:
            seen[digest] = i
            ocr_done = parser == "emails" and path.suffix.lower() == ".pdf" and ocr.is_done(digest)
            key = parse.cache_key(digest, parser, versions[parser], name, entry.rel, rec["is_sample"],
                                  "ocr" if ocr_done else "")      # OCR text arrived: parse this PDF again
            rec["parse_key"] = key
            res = results.get(key)
            if res is None or (retry_failed and res["status"] == "FAILED") or (
                    res["status"] == "UNKNOWN_TEMPLATE" and (not check_templates or
                                                             templates.is_known(res["template_fp"], parser, known_templates))):
                tasks.append(dict(key=key, path=str(path), name=name, rel=entry.rel, parser=parser,
                                  season=season, sha256=digest, is_sample=rec["is_sample"], version=versions[parser],
                                  size=entry.size_bytes))
        registry.append(rec)
        extra_issues += ctx.issues
        if stype == "document" or rec["message"] and rec["message"].startswith("Too large"):
            documents.append(dict(docmeta.describe(path, config.RAW_DOCS_DIR), file_id=i, size_bytes=entry.size_bytes,
                                  sha256=digest))

    t_parse = time.time()
    metas = _parse_all(tasks, run_id, verbose)
    t_parse = time.time() - t_parse
    parsed = {m["_key"] for m in metas}
    results.update({m["_key"]: m for m in metas})
    for r in registry:
        res = results.get(r["parse_key"]) if r["parse_key"] else None
        if res is None:
            continue
        r.update(status=res["status"], message=res["message"], report_date=res["report_date"], family=res["family"],
                 rows_loaded=res["rows_loaded"], from_cache=r["parse_key"] not in parsed, parse_seconds=res["seconds"],
                 template_fp=res["template_fp"], template_sheet=res.get("template_sheet"),
                 template_labels=res["template_labels"])
        if res["season"]:
            r["season"] = res["season"]
        if (check_templates and r["status"] == "LOADED" and r["template_fp"]
                and not templates.is_known(r["template_fp"], r["parser"], known_templates)):
            r.update(status="UNKNOWN_TEMPLATE", rows_loaded=0,     # parsed earlier, layout no longer accepted
                     message=f"Unknown layout (fingerprint {r['template_fp']} not in known_templates.json)")
    if verbose and len(registry) <= 300:
        for r in registry:
            src = "cached" if r["from_cache"] else ("parsed" if r["parse_key"] else "")
            print(f"  [{r['status']:9}] {r['file_name']}  rows={r['rows_loaded']}  {src}")
    _mark_current(registry, pins)
    db = db_path or config.DB_PATH

    config.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    con.execute((SQL_DIR / "00_raw.sql").read_text())
    _load_reference(con)
    t_load = time.time()
    lake.load(con, [dict(_key=r["parse_key"], _batch=results[r["parse_key"]]["_batch"], file_id=r["file_id"],
                         loaded=r["status"] == "LOADED") for r in registry if r["parse_key"] in results])
    t_load = time.time() - t_load
    _insert(con, "etl.data_issue", extra_issues)
    _insert(con, "etl.source_file", registry)
    _insert(con, "stg.document", documents)
    quarantine = _quarantine(registry)
    _insert(con, "etl.quarantine", quarantine)
    _insert(con, "etl.ocr_queue", [
        dict(file_id=r["file_id"], file_name=r["file_name"], path=str(e.path), sha256=r["sha256"],
             pages=results[r["parse_key"]]["ocr_pages"], status="DONE" if ocr.is_done(r["sha256"]) else "PENDING")
        for r, e in zip(registry, entries) if r["parse_key"] in results and results[r["parse_key"]]["ocr_pages"]])
    t_sql = time.time()
    for f in sorted(SQL_DIR.glob("[1-9]*.sql")):
        con.execute(f.read_text())
    t_sql = time.time() - t_sql
    run = dict(run_id=run_id, started_at=dt.datetime.fromtimestamp(t0), seconds=round(time.time() - t0, 2),
               n_files=len(entries), n_new=sum(e.change == "NEW" for e in entries),
               n_changed=sum(e.change == "CHANGED" for e in entries), n_removed=len(removed), n_hashed=n_hashed,
               n_parsed=len(metas), n_cached=sum(r["from_cache"] for r in registry),
               n_failed=sum(r["status"] == "FAILED" for r in registry), n_quarantined=len(quarantine),
               workers=config.WORKERS if metas else 0,
               scan_seconds=round(t_scan, 2), parse_seconds=round(t_parse, 2), load_seconds=round(t_load, 2),
               sql_seconds=round(t_sql, 2), peak_rss_mb=_peak_rss_mb())
    if pins is not None:                      # snapshot: leave the catalog, runs and quarantine report as they are
        con.close()
        lock.close()
        return db
    _save_manifest(con, entries, removed, run)
    con.close()
    lake.compact_results(results, run_id)
    lock.close()
    _write_quarantine(quarantine, verbose)
    if verbose:
        big = sum(1 for d in documents if d["size_bytes"] > config.MAX_PARSE_MB * 1e6)
        print(f"Metadata only (not opened): {len(documents)} file(s), {big} of them > {config.MAX_PARSE_MB:g} MB")
        print(f"Built {config.DB_PATH} in {time.time() - t0:.1f}s ({run['n_files']} files: {run['n_new']} new, "
              f"{run['n_changed']} changed, {n_hashed} hashed; parsed {run['n_parsed']}, cached {run['n_cached']})")
    return config.DB_PATH


def _chunks(tasks: list[dict], max_files=50, max_bytes=16 << 20) -> list[list[dict]]:
    """Big files alone, small files (emails) together: fewer Parquet files and less process overhead."""
    out, cur, size = [], [], 0
    for t in sorted(tasks, key=lambda t: -t["size"]):
        if cur and (len(cur) >= max_files or size + t["size"] > max_bytes):
            out.append(cur)
            cur, size = [], 0
        cur.append(t)
        size += t["size"]
    return out + ([cur] if cur else [])


def _parse_all(tasks: list[dict], run_id: str, verbose: bool) -> list[dict]:
    """Parse in worker processes. A file that raises, times out (KOPS_PARSE_TIMEOUT) or kills its worker
    (segfault, out of memory) is recorded as FAILED and quarantined; the other files go on."""
    if not tasks:
        return []
    chunks = _chunks(tasks)
    batches = [f"{run_id}-{n:05d}" for n in range(len(chunks))]
    timeout, workers = config.PARSE_TIMEOUT, max(1, min(config.WORKERS, len(chunks)))
    if workers == 1:
        return [m for b, c in zip(batches, chunks) for m in parse.run_chunk(c, b, timeout, verbose)]
    inflight = config.LAKE_DIR / "_inflight"        # <pid>.txt = key of the file a worker is parsing right now
    metas, t0, rnd, n_iso = [], time.time(), 0, 0
    todo = list(zip(batches, chunks))
    while todo:
        shutil.rmtree(inflight, ignore_errors=True)
        inflight.mkdir(parents=True)
        leftovers = _pool_round(todo, workers, timeout, verbose, inflight, metas, len(tasks), t0)
        if not leftovers:
            break
        # A worker died or hung: the files it was parsing are tried alone, the others go to a fresh pool.
        suspects = {f.read_text() for f in inflight.glob("*.txt")}
        done_keys = {m["_key"] for m in metas}
        rest = [t for t in leftovers if t["key"] not in done_keys]
        alone = [t for t in rest if t["key"] in suspects] or rest       # no marker found: try every file alone
        for t in alone:
            metas += _parse_isolated(t, f"{run_id}-i{n_iso:05d}", timeout, verbose)
            n_iso += 1
        rnd += 1
        alone_keys = {t["key"] for t in alone}
        again = [t for t in rest if t["key"] not in alone_keys]
        todo = [(f"{run_id}-r{rnd}-{n:05d}", c) for n, c in enumerate(_chunks(again))]
    shutil.rmtree(inflight, ignore_errors=True)
    return metas


def _pool_round(todo, workers, timeout, verbose, inflight, metas, n_tasks, t0) -> list[dict]:
    """Run chunks in a process pool; returns the tasks of chunks lost because the pool broke."""
    leftovers, last = [], time.time()
    stall = 2 * timeout + 60 if timeout else None
    ex = ProcessPoolExecutor(workers)
    futs = {ex.submit(parse.run_chunk, c, b, timeout, verbose, str(inflight)): c for b, c in todo}
    pending = set(futs)
    try:
        while pending:
            done, pending = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
            for f in done:
                try:
                    metas += f.result()
                except Exception:              # BrokenProcessPool: a worker died (segfault, out of memory, killed)
                    leftovers += futs[f]
            if done:
                last = time.time()
                if verbose and n_tasks > 50:
                    print(f"  parse {len(metas)}/{n_tasks} files, {time.time() - t0:.0f}s", flush=True)
            elif stall and time.time() - last > stall:     # a worker hangs in C code (the alarm cannot fire)
                for p in list(getattr(ex, "_processes", {}).values()):
                    p.kill()
    finally:
        ex.shutdown(wait=True, cancel_futures=True)
    return leftovers


def _parse_isolated(t: dict, batch: str, timeout: int, verbose: bool) -> list[dict]:
    """Re-run one file in its own process to tell a crashing/hanging file from its chunk neighbours."""
    one = ProcessPoolExecutor(1)
    fut = one.submit(parse.run_chunk, [t], batch, timeout, verbose)
    try:
        return fut.result(timeout=(timeout + 60) if timeout else None)
    except FuturesTimeout:
        for p in list(getattr(one, "_processes", {}).values()):
            p.kill()
        return parse.failed([t], batch, "PARSE_TIMEOUT", f"Timeout: worker hung for more than {timeout} s")
    except Exception as e:
        return parse.failed([t], batch, "PARSE_CRASHED",
                            f"Crashed: the parser process died ({type(e).__name__}); file may be corrupt or too large")
    finally:
        one.shutdown(wait=True, cancel_futures=True)


QUARANTINE_HINT = {
    "PARSE_FAILED": "Mở file kiểm tra; sửa parser hoặc nhờ KLMAS gửi lại file, rồi chạy build --retry-failed",
    "PARSE_TIMEOUT": "File quá lớn/treo: tăng KOPS_PARSE_TIMEOUT hoặc tách file, rồi build --retry-failed",
    "PARSE_CRASHED": "Tiến trình parse chết (file hỏng/thiếu RAM): kiểm tra file, rồi build --retry-failed",
    "UNKNOWN_TEMPLATE": "Bố cục cột chưa biết: so nhãn với parser; đọc đúng thì `python -m kops_dw templates accept "
                        "<fp>`, sai thì cần sửa/viết parser (H-05)",
    "MISSING_TOOL": "Cài công cụ ghi trong message (vd. brew install libpst / tesseract); build sau tự đọc lại",
    "TOO_LARGE": "File báo cáo lớn hơn KOPS_MAX_PARSE_MB: kiểm tra có đúng là báo cáo không; nếu đúng thì tăng "
                 "KOPS_MAX_PARSE_MB rồi build",
    "UNKNOWN_FILE": "Tên file không khớp loại báo cáo nào: kiểm tra, thêm quy tắc vào pipeline.classify nếu cần",
}


def _quarantine(registry: list[dict]) -> list[dict]:
    """Files that are not loaded and need a person: failed / timed out / crashed parses, unknown layouts."""
    out = []
    for r in registry:
        msg = r["message"] or ""
        if r["status"] == "FAILED":
            code = ("PARSE_TIMEOUT" if msg.startswith("Timeout") else "PARSE_CRASHED" if msg.startswith("Crashed")
                    else "PARSE_FAILED")
        elif r["status"] == "UNKNOWN_TEMPLATE":
            code = "UNKNOWN_TEMPLATE"
        elif r["status"] == "SKIPPED" and msg.startswith("Missing tool"):
            code = "MISSING_TOOL"
        elif r["status"] == "SKIPPED" and msg.startswith("Too large"):
            code = "TOO_LARGE"
        elif r["status"] == "SKIPPED" and r["source_type"] == "excel" and r["parser"] is None:
            code = "UNKNOWN_FILE"
        else:
            continue
        out.append(dict(file_id=r["file_id"], file_name=r["file_name"], rel_path=r["rel_path"], parser=r["parser"],
                        status=r["status"], reason=code, message=msg, template_fp=r["template_fp"],
                        labels=r["template_labels"] if code == "UNKNOWN_TEMPLATE" else None,
                        action=QUARANTINE_HINT[code]))
    return out


def _write_quarantine(rows: list[dict], verbose: bool):
    import csv
    with open(config.QUARANTINE_PATH, "w", newline="", encoding="utf-8-sig") as f:   # BOM: opens in Excel
        w = csv.DictWriter(f, fieldnames=["file_name", "rel_path", "parser", "status", "reason", "message",
                                          "template_fp", "labels", "action"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    if verbose and rows:
        print(f"Quarantine: {len(rows)} file(s) not loaded -> {config.QUARANTINE_PATH}")
        for r in rows[:20]:
            print(f"  [{r['reason']}] {r['file_name']}: {(r['message'] or '')[:120]}")


def _mark_current(registry, pins: list[str] | None = None):
    """Several versions of the same report may sit in raw-docs: the newest per (template, season, family) is
    current. Order by the date in the file name first: the 'UP DATE' cell inside a file is typed by hand and
    has gone backwards between versions (BPK 261021 says 07/09). A pinned file (name prefix) is current for its
    family whatever newer version exists."""
    latest = {}
    for r in registry:
        if r["status"] != "LOADED":
            continue
        if r["parser"] in ("emails", "mailbox", "meeting_notes"):
            r["is_current"] = True
            continue
        key = (r["parser"], r["season"], r["family"])
        rank = (any(r["file_name"].startswith(p) for p in pins or ()),
                r["file_date"] or r["report_date"] or dt.date.min, r["report_date"] or dt.date.min, r["file_id"])
        if key not in latest or rank > latest[key][0]:
            latest[key] = (rank, r)
    for _, r in latest.values():
        r["is_current"] = True


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


def _insert(con, table: str, rows: list[dict]):
    if not rows:
        return
    cols = [c[0] for c in con.execute(f"DESCRIBE {table}").fetchall()]
    data = [[r.get(c) for c in cols] for r in rows]
    con.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(cols))})", data)


def _load_reference(con):
    _insert(con, "stg.factory_alias", [dict(alias_key=norm_key(k), factory_code=v)
                                       for k, v in config.FACTORY_ALIASES.items()])
    _insert(con, "stg.factory_alias_review", [dict(alias_key=norm_key(k), factory_code=v[0], confidence=v[1], question=v[2])
                                              for k, v in config.FACTORY_ALIAS_REVIEW.items()])
    _insert(con, "stg.customer_ref", [dict(customer=k, name=v) for k, v in config.CUSTOMER_NAMES.items()])
    _insert(con, "stg.free_mail", [dict(domain=d) for d in sorted(config.FREE_MAIL)])
    parties = [dict(domain=d, party_type="KLMAS", ref_code=None) for d in config.KLMAS_EMAIL_DOMAINS]
    if config.PARTY_FILE.exists():           # local, git-ignored: 'domain PARTY_TYPE [code]'
        for line in config.PARTY_FILE.read_text(encoding="utf-8").splitlines():
            parts = line.split("#", 1)[0].split(None, 2)
            if len(parts) >= 2:
                parties.append(dict(domain=parts[0].lower(), party_type=parts[1].upper(),
                                    ref_code=parts[2].strip() if len(parts) > 2 else None))
    _insert(con, "stg.party_domain", parties)
    _insert(con, "stg.style_alias", [dict(alias_style=k, style_no=v, confirmed=False)
                                     for k, v in config.STYLE_ALIASES.items()])
    _insert(con, "stg.rule", [dict(rule_key=k, rule_value=str(v)) for k, v in config.RULES.items()]
            + [dict(rule_key="klmas_domains", rule_value=",".join(config.KLMAS_EMAIL_DOMAINS))])
    _insert(con, "stg.requirement_coverage", [dict(req_no=k, mvp_status=s, where_in_mvp=w, next_step=n)
                                              for k, (s, w, n) in config.REQUIREMENT_COVERAGE.items()])


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(config.REPO_DIR))
    except ValueError:
        return str(path)
