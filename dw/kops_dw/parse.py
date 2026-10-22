"""Parse source files into lake rows. Runs in the build process or in worker processes (H-03).

A parse result depends only on the file content (sha256), the parser code and the config it reads
(parser_versions), the file name (season, date, customer come from it) and the path inside its source root (customer
fallback, gmail/ folder). Together they make the cache key: a file whose key is already in the lake is not parsed
again. Editing a parser module (or a config value listed in PARSER_DEPS) re-parses only that parser's files.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import sys
import time
import traceback
from pathlib import Path

from . import config, lake
from .excel import open_workbook

LAKE_FORMAT = "1"          # bump to re-parse everything (e.g. after a change in how rows are stored)
EXCEL_PARSERS = ("order_recap", "order_recap_ext", "production_plan", "shipment_status", "production_status")
_COMMON = ["parse.py", "util.py"]
_EXCEL = [*_COMMON, "excel.py"]
_CUSTOMERS = ["CUSTOMER_KEYS", "BRAND_ALIASES", "FACTORY_ALIASES"]
_EMAIL = [*_COMMON, "ingest/emails.py", "ingest/email_pdf.py", "ingest/email_common.py", "ingest/email_llm.py"]
_EMAIL_CFG = ["EMAIL_CATEGORIES", "EMAIL_DMY", "EMAIL_LLM", "EMAIL_LLM_MODEL"]
# parser -> (source files under kops_dw/, config names) whose content defines the parser version
PARSER_DEPS = {
    "order_recap": ([*_EXCEL, "ingest/order_recap.py"], []),
    "order_recap_ext": ([*_EXCEL, "ingest/order_recap_generic.py"], _CUSTOMERS),
    "production_plan": ([*_EXCEL, "ingest/production_plan.py", "ingest/order_recap_generic.py"], _CUSTOMERS),
    "shipment_status": ([*_EXCEL, "ingest/shipment_status.py"], ["SHIPMENT_SHEET_FACTORY"]),
    "production_status": ([*_EXCEL, "ingest/production_status.py"], []),
    "meeting_notes": ([*_COMMON, "ingest/meeting_notes.py"], []),
    "emails": (_EMAIL, _EMAIL_CFG),
}


class Ctx:
    """Collects data issues (and side facts) for the file being parsed."""

    def __init__(self, sha256: str | None = None):
        self.issues = []
        self.file_id = None
        self.sha256 = sha256
        self.report_date = None       # set by streaming parsers (mailboxes)

    def issue(self, severity, code, entity, message, location=None):
        self.issues.append(dict(file_id=self.file_id, severity=severity, code=code, entity=str(entity),
                                message=message, location=location))


def parser_versions() -> dict[str, str]:
    pkg = Path(__file__).parent
    out = {}
    for parser, (files, names) in PARSER_DEPS.items():
        h = hashlib.sha1(LAKE_FORMAT.encode())
        for f in files:
            h.update((pkg / f).read_bytes())
        for n in names:
            h.update(f"{n}={getattr(config, n)!r}".encode())
        out[parser] = h.hexdigest()[:12]
    return out


def cache_key(sha256: str, parser: str, version: str, name: str, rel: str, is_sample: bool, extra: str = "") -> str:
    return hashlib.sha1("|".join([sha256, parser, version, name, rel, str(is_sample), extra]).encode()).hexdigest()[:24]


def run_chunk(tasks: list[dict], batch: str, timeout: int = 0, verbose: bool = False) -> list[dict]:
    """Parse files one after another, write their rows to the lake as one batch, then the results."""
    writer = lake.Writer(batch)
    metas = [_run_one(t, writer, verbose) for t in tasks]
    writer.flush()
    lake.write_results(metas, batch)
    return metas


def _run_one(t: dict, writer: lake.Writer, verbose: bool) -> dict:
    ctx = Ctx(t["sha256"])
    t0 = time.time()
    meta = dict(_key=t["key"], _batch=writer.batch, sha256=t["sha256"], parser=t["parser"], parser_version=t["version"],
                file_name=t["name"], status="LOADED", message=None, report_date=None, family=None, season=None,
                rows_loaded=0, n_issues=0, seconds=0.0, template_fp=None, template_labels=None, ocr_pages=None,
                parsed_at=dt.datetime.now())
    try:
        tables, report_date, family = parse_file(t, ctx)
        seasons, n = set(), 0
        for part in [tables] if isinstance(tables, dict) else tables:      # mailboxes yield parts
            n += writer.add(part, t["key"], t["parser"])
            if t["parser"] in ("order_recap_ext", "production_plan"):
                seasons |= {r["season"] for rows in part.values() for r in rows if r.get("season")}
        meta.update(report_date=report_date or ctx.report_date, family=family, rows_loaded=n)
        if len(seasons) == 1:
            meta["season"] = seasons.pop()            # sheet title wins over the file name
    except Exception as e:  # keep going: one bad file must not stop the build
        meta.update(status="FAILED", message=f"{type(e).__name__}: {e}"[:1000])
        ctx.issue("ERROR", "PARSE_FAILED", t["name"], meta["message"], t["name"])
        if verbose:
            traceback.print_exc(file=sys.stderr)
    meta["n_issues"] = len(ctx.issues)
    writer.add({"etl.data_issue": ctx.issues}, t["key"], t["parser"])
    meta["seconds"] = round(time.time() - t0, 3)
    return meta


def parse_file(t: dict, ctx: Ctx):
    """-> (tables, report_date, family). family groups versions of one report (None = parser + season)."""
    from .ingest import (emails, meeting_notes, order_recap, order_recap_generic, production_plan,
                         production_status, shipment_status)
    from .pipeline import file_date
    path, parser, season, digest = Path(t["path"]), t["parser"], t["season"], t["sha256"]
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
        tables, report_date, family = mod.parse(wb, season, ctx, path.name, t["rel"])
        return tables, report_date or file_date(path.name), family
    if parser == "meeting_notes":
        tables, d = meeting_notes.parse(path, ctx)
        return tables, (dt.date.fromisoformat(d) if d else None), None
    if parser == "emails":
        tables, d = emails.parse(path, ctx)
        return tables, d, None
    raise ValueError(parser)
