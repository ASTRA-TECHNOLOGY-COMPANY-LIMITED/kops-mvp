"""Parquet lake (H-02): parse results stored once per source file and reused by every later build.

Layout under config.LAKE_DIR (default dw/build/lake):
  <schema.table>/<parser>/<batch>-<part>.parquet   rows of one raw/stg/etl table + _key, _batch, _seq
  _parse_result/<batch>.parquet                    one row per parsed file: status, report date, timings ...
  _catalog/manifest.parquet, runs.parquet          manifest.py (H-01)
_key identifies one parse of one file (parse.cache_key: sha256 + parser version + name + path in its root). Rows
are written in batches (one per chunk of files) instead of one file per source, so 50,000 emails do not turn into
100,000 tiny Parquet files. Nothing is overwritten: a re-parse writes a new batch and the build reads, for each
key, the rows of its newest batch. `python -m kops_dw lake-compact` rewrites the tables without superseded rows.

Rollback: the lake is a cache. Deleting the folder only costs time (the next build parses every file again).
"""
from __future__ import annotations

import datetime as dt
import os
from collections import defaultdict
from functools import cache
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from . import config

RESULTS = "_parse_result"
ARROW = {"VARCHAR": pa.string(), "INTEGER": pa.int32(), "BIGINT": pa.int64(), "DOUBLE": pa.float64(),
         "BOOLEAN": pa.bool_(), "DATE": pa.date32(), "TIMESTAMP": pa.timestamp("us")}
RESULT_SCHEMA = pa.schema([
    ("_key", pa.string()), ("_batch", pa.string()), ("sha256", pa.string()), ("parser", pa.string()),
    ("parser_version", pa.string()), ("file_name", pa.string()), ("status", pa.string()), ("message", pa.string()),
    ("report_date", pa.date32()), ("family", pa.string()), ("season", pa.string()), ("rows_loaded", pa.int64()),
    ("n_issues", pa.int64()), ("seconds", pa.float64()), ("template_fp", pa.string()),
    ("template_sheet", pa.string()), ("template_labels", pa.string()), ("ocr_pages", pa.string()), ("parsed_at", pa.timestamp("us"))])
LAKE_TABLES_PREFIX = ("raw.", "stg.")


@cache
def schemas() -> dict[str, list[tuple[str, str]]]:
    """Column specs of every table a parser can write (raw.*, stg.*, etl.data_issue), from sql/00_raw.sql."""
    con = duckdb.connect()
    con.execute((config.DW_DIR / "sql" / "00_raw.sql").read_text())
    out = {}
    for schema, table in con.execute("SELECT schema_name, table_name FROM duckdb_tables()").fetchall():
        name = f"{schema}.{table}"
        if name.startswith(LAKE_TABLES_PREFIX) or name == "etl.data_issue":
            cols = con.execute(f"DESCRIBE {name}").fetchall()
            out[name] = [(c[0], c[1]) for c in cols if c[0] != "file_id"]
    con.close()
    return out


def qualify(name: str) -> str:
    """Parser output names: 'email' -> raw.email, 'stg_email_change' -> stg.email_change."""
    if "." in name:
        return name
    return f"stg.{name[4:]}" if name.startswith("stg_") else f"raw.{name}"


def _coerce(v, typ: str):
    """Same casts DuckDB applied when rows were INSERTed one by one (a value that cannot be cast raises)."""
    if v is None:
        return None
    if typ == "VARCHAR":
        return v if isinstance(v, str) else str(v)
    if typ in ("INTEGER", "BIGINT"):
        if isinstance(v, float):
            return int(round(v))
        return int(v.strip()) if isinstance(v, str) else int(v)
    if typ == "DOUBLE":
        return float(v)
    if typ == "BOOLEAN":
        return bool(v)
    if typ == "DATE":
        if isinstance(v, dt.datetime):
            return v.date()
        return dt.date.fromisoformat(v) if isinstance(v, str) else v
    if typ == "TIMESTAMP":
        if isinstance(v, str):
            v = dt.datetime.fromisoformat(v)
        elif not isinstance(v, dt.datetime) and isinstance(v, dt.date):
            v = dt.datetime.combine(v, dt.time())
        return v.replace(tzinfo=None) if v.tzinfo else v
    return v


class Writer:
    """Buffers rows of many files and writes one Parquet file per (table, parser) when flushed."""

    def __init__(self, batch: str, flush_rows: int = 200_000, flush_bytes: int = 64 << 20):
        self.batch, self.flush_rows, self.flush_bytes = batch, flush_rows, flush_bytes
        self.buf: dict[tuple[str, str], dict[str, list]] = {}
        self.seq = defaultdict(int)
        self.pending = self.pending_bytes = self.part = 0

    def add(self, tables: dict, key: str, parser: str) -> int:
        """Cast every row first (a bad value fails this file only), then buffer. Returns rows added."""
        staged, n = [], 0
        for name, rows in tables.items():
            if not rows:
                continue
            table = qualify(name)
            spec = schemas()[table]
            cols = {c: [_coerce(r.get(c), t) for r in rows] for c, t in spec}
            start = self.seq[(key, table)]
            cols["_key"], cols["_batch"] = [key] * len(rows), [self.batch] * len(rows)
            cols["_seq"] = list(range(start, start + len(rows)))
            staged.append((table, cols, len(rows)))
        for table, cols, cnt in staged:
            self.seq[(key, table)] += cnt
            buf = self.buf.setdefault((table, parser), defaultdict(list))
            for c, vals in cols.items():
                buf[c] += vals
            self.pending += cnt
            self.pending_bytes += sum(len(v) for v in cols.get("body", ()) if v)     # email bodies dominate
            n += cnt if not table.startswith("etl.") else 0
        if self.pending >= self.flush_rows or self.pending_bytes >= self.flush_bytes:
            self.flush()
        return n

    def flush(self):
        for (table, parser), cols in self.buf.items():
            fields = [(c, ARROW[t]) for c, t in schemas()[table]]
            fields += [("_key", pa.string()), ("_batch", pa.string()), ("_seq", pa.int32())]
            schema = pa.schema(fields)
            data = pa.Table.from_pydict({f.name: cols[f.name] for f in schema}, schema=schema)
            _write(data, config.LAKE_DIR / table / parser / f"{self.batch}-{self.part:03d}.parquet")
        self.buf, self.pending, self.pending_bytes = {}, 0, 0
        self.part += 1


def write_results(metas: list[dict], batch: str):
    """Written after the batch's rows: a result row means its data is complete (safe to stop and resume)."""
    if metas:
        _write(pa.Table.from_pylist(metas, schema=RESULT_SCHEMA), config.LAKE_DIR / RESULTS / f"{batch}.parquet")


def read_results() -> dict[str, dict]:
    """Newest parse result per key."""
    d = config.LAKE_DIR / RESULTS
    if not d.exists() or not any(d.glob("*.parquet")):
        return {}
    con = duckdb.connect()
    cur = con.execute(f"""SELECT * FROM read_parquet('{d}/*.parquet', union_by_name=true)
                          QUALIFY row_number() OVER (PARTITION BY _key ORDER BY _batch DESC) = 1""")
    cols = [c[0] for c in cur.description]
    out = {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}
    con.close()
    return out


def compact_results(results: dict[str, dict], run_id: str, max_files: int = 64):
    """Many incremental builds leave many small result files: fold them into one."""
    d = config.LAKE_DIR / RESULTS
    old = sorted(d.glob("*.parquet")) if d.exists() else []
    if len(old) <= max_files:
        return
    write_results(list(results.values()), f"{run_id}-compact")
    keep = d / f"{run_id}-compact.parquet"
    for f in old:
        if f != keep:
            f.unlink()


def load(con, picks: list[dict]) -> dict[str, int]:
    """Insert the lake rows of the picked parses into the DB tables, in file / row order.
    picks: dicts with _key, _batch, file_id, loaded (False = only its data issues, e.g. a failed parse)."""
    if not picks:
        return {}
    con.register("_pick_arrow", pa.Table.from_pylist(picks, schema=pa.schema(
        [("_key", pa.string()), ("_batch", pa.string()), ("file_id", pa.int32()), ("loaded", pa.bool_())])))
    con.execute("CREATE TEMP TABLE _pick AS SELECT * FROM _pick_arrow")
    con.unregister("_pick_arrow")
    counts = {}
    for table, spec in schemas().items():
        files = table_files(table)
        if not files:
            continue
        src = f"read_parquet({_list(files)}, union_by_name=true)"
        have = {c[0] for c in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
        cols = [c for c, _ in spec if c in have]
        where = "" if table == "etl.data_issue" else "WHERE k.loaded"
        con.execute(f"""INSERT INTO {table} (file_id, {', '.join(cols)})
                        SELECT k.file_id, {', '.join('p.' + c for c in cols)} FROM {src} p
                        JOIN _pick k ON p._key = k._key AND p._batch = k._batch {where}
                        ORDER BY k.file_id, p._seq""")
        counts[table] = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    con.execute("DROP TABLE _pick")
    return counts


def table_files(table: str) -> list[Path]:
    return sorted((config.LAKE_DIR / table).glob("*/*.parquet"))


def compact(results: dict[str, dict]) -> dict[str, tuple[int, int]]:
    """Rewrite every table with only the rows of the newest parse of each key (drops superseded batches).
    Returns {table: (files before, rows dropped)}. Run when no build is running."""
    valid = pa.Table.from_pylist([dict(_key=k, _batch=r["_batch"]) for k, r in results.items()],
                                 schema=pa.schema([("_key", pa.string()), ("_batch", pa.string())]))
    con = duckdb.connect()
    con.register("valid", valid)
    out = {}
    for table in schemas():
        for parser_dir in sorted(p for p in (config.LAKE_DIR / table).glob("*") if p.is_dir()):
            files = sorted(parser_dir.glob("*.parquet"))
            if not files:
                continue
            src = f"read_parquet({_list(files)}, union_by_name=true)"
            total = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
            target = parser_dir / "compact.parquet.tmp"
            con.execute(f"""COPY (SELECT p.* FROM {src} p SEMI JOIN valid v ON p._key = v._key AND p._batch = v._batch
                            ORDER BY p._key, p._seq) TO '{target}' (FORMAT parquet)""")
            kept = con.execute(f"SELECT count(*) FROM read_parquet('{target}')").fetchone()[0]
            for f in files:
                f.unlink()
            os.replace(target, parser_dir / "compact-000.parquet")
            out[f"{table}/{parser_dir.name}"] = (len(files), total - kept)
    con.close()
    return out


def size_bytes() -> int:
    return sum(f.stat().st_size for f in config.LAKE_DIR.rglob("*.parquet")) if config.LAKE_DIR.exists() else 0


def _list(files) -> str:
    return "[" + ", ".join("'" + str(f).replace("'", "''") + "'" for f in files) + "]"


def _write(table: pa.Table, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, target)
