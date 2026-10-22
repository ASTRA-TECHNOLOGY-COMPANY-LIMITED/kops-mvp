"""CLI: python -m kops_dw [build|test|dashboard|all|fetch-imap|attachments|lake-compact|templates|ocr|bench]

  all           build + test + dashboard (default)
  build         incremental build: only new/changed files are parsed, the rest is read from the lake
                --retry-failed  parse again the files that failed last time (otherwise kept as FAILED)
  fetch-imap    read-only download of a mailbox folder into raw-docs/inbox/imap/ (see kops_dw/inbox.py)
  attachments   save .eml attachments to raw-docs/EMAIL_ATTACHMENTS/ so they are parsed by the next build
  lake-compact  rewrite the Parquet lake without rows of superseded parses (run when no build is running)
  templates     Excel layouts not yet known (quarantined); `templates accept <fp>` after checking them
  ocr           OCR the scanned PDF pages queued by the last build (tesseract kor+vie+eng), then rebuild
  bench         acceptance checks / synthetic data / benchmark outside the repo (see kops_dw/bench.py)
"""
from __future__ import annotations

import sys


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    cmd = args[0] if args else "all"
    if cmd == "fetch-imap":
        from .inbox import fetch_imap
        return fetch_imap(argv[1:])
    if cmd == "attachments":
        from .inbox import attachments
        return attachments(argv[1:])
    if cmd == "bench":
        from .bench import main as bench
        sys.exit(0 if bench(argv[1:]) in (True, None) else 1)
    if cmd == "ocr":
        from .ocr import run
        sys.exit(run(argv[1:]))
    if cmd == "templates":
        from .templates import cli
        return cli(args[1:] + sorted(flags))
    if cmd == "lake-compact":
        from . import lake
        before = lake.size_bytes()
        for table, (files, dropped) in lake.compact(lake.read_results()).items():
            print(f"  {table}: {files} file(s) -> 1, {dropped} superseded row(s) dropped")
        print(f"Lake {before / 1e6:.1f} MB -> {lake.size_bytes() / 1e6:.1f} MB")
        return
    if cmd in ("build", "all"):
        from .pipeline import build
        build(retry_failed="--retry-failed" in flags)
    if cmd in ("test", "all"):
        from .checks import run_checks
        ok = run_checks()
        if not ok and cmd == "test":
            sys.exit(1)
    if cmd in ("dashboard", "all"):
        from .dashboard import render
        render()
    if cmd not in ("build", "test", "dashboard", "all"):
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
