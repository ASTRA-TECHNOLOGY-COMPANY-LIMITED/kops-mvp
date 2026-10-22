"""Inbox helpers that run BEFORE a build (they write files; the build itself only reads).

  python -m kops_dw fetch-imap --host imap.gmail.com --user someone@gmail.com --folder "KLMAS" [--since 2026-01-01]
      Read-only IMAP download (mailbox opened read-only, nothing marked/moved/deleted) into
      raw-docs/inbox/imap/<folder>/. Password from env KOPS_IMAP_PASSWORD (Gmail: an app password).
      Works for Gmail, Outlook/Microsoft 365, Naver, Daum, Hiworks... any IMAP mailbox.
  python -m kops_dw attachments
      Save attachments of every .eml in raw-docs/inbox/ to raw-docs/EMAIL_ATTACHMENTS/<yyyy-mm>/ so Excel/PDF
      attachments are parsed like any other source (identical files are de-duplicated by sha256 in the build).

Gmail / Google Drive via Claude connectors: the agent saves messages as .eml (or PDF exports) into
raw-docs/inbox/gmail/ or raw-docs/inbox/pdf/; no code needed here. See plans/EMAIL_READINESS_PLAN.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import email
import email.utils
import imaplib
import os
import re
from email import policy
from pathlib import Path

from . import config

INBOX = config.INBOX_DIRS[0]


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\r\n]+', "_", name).strip()[:150] or "file"


def fetch_imap(argv):
    ap = argparse.ArgumentParser(prog="kops_dw fetch-imap")
    ap.add_argument("--host", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--folder", default="INBOX")
    ap.add_argument("--since", help="YYYY-MM-DD")
    ap.add_argument("--port", type=int, default=993)
    a = ap.parse_args(argv)
    pw = os.environ.get("KOPS_IMAP_PASSWORD")
    if not pw:
        raise SystemExit("Set KOPS_IMAP_PASSWORD (never put it on the command line or in the repo)")
    out = INBOX / "imap" / _safe(a.folder)
    out.mkdir(parents=True, exist_ok=True)
    m = imaplib.IMAP4_SSL(a.host, a.port)
    m.login(a.user, pw)
    typ, _ = m.select(f'"{a.folder}"', readonly=True)           # read-only: no \\Seen flags are set
    if typ != "OK":
        raise SystemExit(f"Folder not found: {a.folder}")
    crit = ["ALL"] if not a.since else ["SINCE", dt.date.fromisoformat(a.since).strftime("%d-%b-%Y")]
    _, data = m.uid("search", None, *crit)
    uids = data[0].split()
    new = 0
    for uid in uids:
        target = out / f"{uid.decode()}.eml"
        if target.exists():
            continue
        _, msg = m.uid("fetch", uid, "(BODY.PEEK[])")             # PEEK: does not mark as read
        raw = next((p[1] for p in msg if isinstance(p, tuple)), None)
        if raw:
            target.write_bytes(raw)
            new += 1
    m.logout()
    print(f"{len(uids)} messages in '{a.folder}', {new} new saved to {out}")


def attachments(argv=None):
    target_root = config.RAW_DOCS_DIR / "EMAIL_ATTACHMENTS"
    n = 0
    for p in sorted(INBOX.rglob("*.eml")) if INBOX.exists() else []:
        msg = email.message_from_bytes(p.read_bytes(), policy=policy.default)
        try:
            sent = email.utils.parsedate_to_datetime(msg["Date"]) if msg["Date"] else None
        except (TypeError, ValueError):
            sent = None
        folder = target_root / (sent.strftime("%Y-%m") if sent else "undated")
        for part in msg.iter_attachments():
            name = part.get_filename()
            if not name:
                continue
            dest = folder / _safe(name)
            if dest.exists():
                continue
            folder.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(part.get_payload(decode=True) or b"")
            n += 1
    print(f"{n} attachment(s) saved under {target_root}")
