"""Source manifest (H-01): every file seen under the source roots with size, mtime and sha256.

The sha256 is only recomputed when a file's size or mtime changed since the last build, so a build over thousands of
unchanged files costs one stat() per file. The manifest lives in <lake>/_catalog/manifest.parquet together with
runs.parquet (one row per build, loaded as etl.run). Deleting the catalog only means every file is hashed again.
"""
from __future__ import annotations

import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import config
from .util import sha256

MANIFEST_SCHEMA = pa.schema([("path", pa.string()), ("root", pa.string()), ("rel", pa.string()),
                             ("size_bytes", pa.int64()), ("mtime_ns", pa.int64()), ("sha256", pa.string()),
                             ("first_seen", pa.string()), ("last_seen", pa.string())])


@dataclass
class Entry:
    path: Path
    root: Path            # source root the file was found under (raw-docs or an inbox folder)
    rel: str              # path inside that root; stable when the root itself moves (external disk, Drive)
    size_bytes: int
    mtime_ns: int
    sha256: str
    change: str           # NEW | CHANGED | UNCHANGED (vs the previous build)
    first_seen: str


def catalog_dir() -> Path:
    return config.LAKE_DIR / "_catalog"


def source_root(path: Path) -> Path:
    """Inbox folders first: raw-docs/inbox sits inside raw-docs."""
    for d in [*config.INBOX_DIRS, config.RAW_DOCS_DIR]:
        if d in path.parents:
            return d
    return path.parent


def load() -> dict[str, dict]:
    f = catalog_dir() / "manifest.parquet"
    if not f.exists():
        return {}
    return {r["path"]: r for r in pq.read_table(f).to_pylist()}


def scan(paths: list[Path], run_id: str, previous: dict[str, dict]) -> tuple[list[Entry], list[dict], int]:
    """-> (entries in the order given, previous rows whose file is gone, files hashed). Hashing runs in threads."""
    stats = [p.stat() for p in paths]
    need = [i for i, (p, st) in enumerate(zip(paths, stats))
            if (old := previous.get(str(p))) is None or (old["size_bytes"], old["mtime_ns"]) != (st.st_size, st.st_mtime_ns)]
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
        hashed = dict(zip(need, ex.map(lambda i: sha256(paths[i]), need)))
    entries = []
    for i, (p, st) in enumerate(zip(paths, stats)):
        old = previous.get(str(p))
        digest = hashed.get(i) or old["sha256"]
        change = "NEW" if old is None else ("UNCHANGED" if digest == old["sha256"] else "CHANGED")
        root = source_root(p)
        entries.append(Entry(p, root, p.relative_to(root).as_posix(), st.st_size, st.st_mtime_ns, digest, change,
                             old["first_seen"] if old else run_id))
    seen = {str(p) for p in paths}
    removed = [r for k, r in previous.items() if k not in seen]
    return entries, removed, len(need)


def save(entries: list[Entry], run_id: str):
    rows = [dict(path=str(e.path), root=str(e.root), rel=e.rel, size_bytes=e.size_bytes, mtime_ns=e.mtime_ns,
                 sha256=e.sha256, first_seen=e.first_seen, last_seen=run_id) for e in entries]
    _write(pa.Table.from_pylist(rows, schema=MANIFEST_SCHEMA), catalog_dir() / "manifest.parquet")


def load_runs() -> list[dict]:
    f = catalog_dir() / "runs.parquet"
    return pq.read_table(f).to_pylist() if f.exists() else []


def save_run(run: dict):
    rows = [*load_runs(), run][-1000:]
    _write(pa.Table.from_pylist(rows), catalog_dir() / "runs.parquet")


def new_run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")[:-3]


def _write(table: pa.Table, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, target)          # atomic: an interrupted build never leaves a half-written catalog
