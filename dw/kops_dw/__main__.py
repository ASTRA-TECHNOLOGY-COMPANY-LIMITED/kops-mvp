"""CLI: python -m kops_dw [build|test|dashboard|serve|all|fetch-imap|attachments|lake-compact|mail-allow|templates|ocr|bench]

  all           build + test + dashboard (default)
  build         incremental build: only new/changed files are parsed, the rest is read from the lake
                --retry-failed  parse again the files that failed last time (otherwise kept as FAILED)
  fetch-imap    read-only download of a mailbox folder into raw-docs/inbox/imap/ (see kops_dw/inbox.py)
  attachments   save .eml attachments to raw-docs/EMAIL_ATTACHMENTS/ so they are parsed by the next build
  lake-compact  rewrite the Parquet lake without rows of superseded parses (run when no build is running)
  mail-allow    allow-list of partner senders for mailbox filters: `suggest [--write]`, `report [mbox ...]`
  templates     Excel layouts not yet known (quarantined); `templates accept <fp>` after checking them
  ocr           OCR the scanned PDF pages queued by the last build (tesseract kor+vie+eng), then rebuild
  dashboard     build/dashboard.html + build/data/<season>.json (--single: one self-contained HTML file)
  serve         local static server for the dashboard: http://127.0.0.1:8765/ (--port N, --open)
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
    if cmd == "mail-allow":
        from .mailallow import cli as mail_allow
        sys.exit(mail_allow(argv[1:]))
    if cmd == "admin-reset":     # admin password back to KOPS_ADMIN_PASSWORD (.env), must change at next login
        from app.bootstrap import reset_admin
        print(reset_admin())
        return
    if cmd == "chat-eval":       # chatbot golden cases (dw/eval/chat_cases.json), basic mode
        from app.chat_eval import cli
        sys.exit(cli())
    if cmd == "check-ui":      # Playwright UI test of the manager dashboard (E-07)
        from .uitest import run as check_ui
        sys.exit(check_ui(argv[1:]))
    if cmd == "report":        # PDF of the action list / overview (headless Chromium, local only)
        from .report import run as report
        sys.exit(report(argv[1:]))
    if cmd == "i18n":          # rewrite templates/i18n/vi.json from manager.html, list keys without Korean text
        from .i18n import sync
        missing = sync()
        print(f"{len(missing)} key(s) without Korean text" + "".join(f"\n  {k}" for k in missing))
        sys.exit(1 if missing else 0)
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
    if cmd == "serve":
        from app.main import serve      # web app (F-00): login, data API, notifications, chatbot
        sys.exit(serve(argv[1:]))
    if cmd in ("dashboard", "all"):
        from .dashboard import render
        render(single="--single" in flags)
    if cmd not in ("build", "test", "dashboard", "all"):
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
