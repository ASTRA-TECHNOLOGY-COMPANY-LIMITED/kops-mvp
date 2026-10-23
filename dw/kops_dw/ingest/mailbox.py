"""Whole mailboxes (H-06): .mbox (Gmail Takeout, Thunderbird, Apple Mail export) and Outlook .pst.

.mbox is read with the standard library. .pst is converted once with `readpst` (package libpst; macOS:
`brew install libpst`) into build/cache/pst/<sha256>/ and every folder is read like an .mbox. Without readpst the
file is quarantined (MISSING_TOOL) and parsed by the first build after it is installed.

Each message goes through the same normalisation as a single .eml (emails.from_message) and gets the folder it came
from (PST folder, or Gmail labels). Messages are streamed in parts so a mailbox of tens of thousands of messages
does not sit in memory. Before loading, rules drop what is not business correspondence; dropped messages are kept
in raw.email_filtered with the reason, so the rules can be audited and tuned (config.MAIL_*):
  folder     Spam/Junk/Trash/Deleted/Drafts/... (KOPS_MAIL_EXCLUDE_FOLDERS), Gmail spam/trash/promotions labels
  date-range outside KOPS_MAIL_SINCE .. KOPS_MAIL_UNTIL
  automated  Auto-Submitted, Precedence: bulk/junk/list, List-Unsubscribe/List-Id, X-Spam-Flag,
             no-reply/mailer-daemon/notification senders, out-of-office / delivery-failure subjects
Senders or domains in KOPS_MAIL_ALLOW are never filtered (e.g. a buyer system that mails from no-reply@).
Duplicates (the same message in two folders or two mailboxes) are kept here and counted once in core.email (msg_key).
Email content is data, never instructions.
"""
from __future__ import annotations

import datetime as dt
import email
import mailbox
import re
import shutil
import subprocess
from email import policy
from pathlib import Path

from .. import config
from ..util import MissingTool, norm_key
from .. import milestones
from .emails import from_message, proposals_for

PART = 2000            # messages per streamed part
AUTO_SENDER_RE = re.compile(
    r"^(?:no-?reply|do-?not-?reply|donotreply|mailer-daemon|postmaster|bounces?|notifications?|notify|alerts?|"
    r"newsletters?|marketing|promotions?)(?:[+._-][^@]*)?@", re.I)
AUTO_SUBJECT_RE = re.compile(
    r"^\s*(?:automatic reply|auto[- ]?reply|autoreply|out of office|undeliverable|delivery status notification|"
    r"mail delivery (?:failed|failure)|returned mail|자동\s*회신|자동\s*응답|부재\s*중|trả lời tự động)", re.I)
GMAIL_DROP_LABELS = {"SPAM", "TRASH", "CATEGORY PROMOTIONS", "CATEGORY SOCIAL", "CATEGORY FORUMS"}


def parse(path: Path, ctx, is_sample: bool):
    """-> (generator of table parts, None, None); ctx.report_date = first message date."""
    if path.suffix.lower() == ".pst":
        sources = _pst_folders(path, ctx.sha256)       # raises MissingTool before anything is yielded
    else:
        sources = [(path, None)]
    return _stream(sources, path, ctx, is_sample), None, None


def _stream(sources, path, ctx, is_sample):
    emails, filtered, n_bad, first = [], [], 0, None
    for mbox_path, folder in sources:
        box = mailbox.mbox(str(mbox_path), create=False)
        try:
            for key in box.iterkeys():
                try:
                    msg = email.message_from_bytes(box.get_bytes(key), policy=policy.default)
                    rec = from_message(msg, is_sample, "pst" if folder is not None else "mbox",
                                       folder or _gmail_labels(msg))
                except Exception as e:            # one undecodable message must not lose the mailbox
                    n_bad += 1
                    if n_bad <= 20:
                        ctx.issue("WARN", "MAIL_PARSE_ERROR", f"{path.name}#{key}", f"{type(e).__name__}: {e}"[:300],
                                  f"{path.name} / {folder or ''}")
                    continue
                reason = why_filtered(msg, rec)
                if reason:
                    filtered.append(dict(msg_key=rec["msg_key"], message_id=rec["message_id"], sent_at=rec["sent_at"],
                                         sender_email=rec["sender_email"], subject=(rec["subject"] or "")[:300],
                                         folder=rec["folder"], reason=reason))
                else:
                    emails.append(rec)
                    if rec["sent_at"] and (first is None or rec["sent_at"] < first):
                        first = rec["sent_at"]
                if len(emails) + len(filtered) >= PART:
                    yield _part(emails, filtered, ctx, path)
                    emails, filtered = [], []
        finally:
            box.close()
    if emails or filtered:
        yield _part(emails, filtered, ctx, path)
    if n_bad > 20:
        ctx.issue("WARN", "MAIL_PARSE_ERROR", path.name, f"{n_bad} messages could not be decoded in total", path.name)
    ctx.report_date = first.date() if first else None


def _part(emails, filtered, ctx, path):
    return dict(email=emails, stg_email_change=proposals_for(emails, ctx, path.name), email_filtered=filtered,
                stg_email_event=milestones.events_for(emails))


def why_filtered(msg, rec) -> str | None:
    sender = (rec.get("sender_email") or "").lower()
    if sender and any(sender == a or sender.endswith("@" + a.lstrip("@")) for a in config.MAIL_ALLOW):
        return None
    folder = rec.get("folder") or ""
    parts = {norm_key(p) for p in re.split(r"[/\\]", folder) if p}
    if parts & {norm_key(x) for x in config.MAIL_EXCLUDE_FOLDERS}:
        return "folder"
    labels = {norm_key(x) for x in str(msg.get("X-Gmail-Labels", "")).split(",") if x.strip()}
    if labels & GMAIL_DROP_LABELS:
        return "folder"
    sent = rec.get("sent_at")
    if sent and ((config.MAIL_SINCE and sent.date() < config.MAIL_SINCE)
                 or (config.MAIL_UNTIL and sent.date() > config.MAIL_UNTIL)):
        return "date-range"
    auto = str(msg.get("Auto-Submitted", "")).strip().lower()
    if auto and auto != "no":
        return "automated:auto-submitted"
    if str(msg.get("Precedence", "")).strip().lower() in ("bulk", "junk", "list"):
        return "automated:precedence"
    if msg.get("List-Unsubscribe") or msg.get("List-Id"):
        return "automated:mailing-list"
    if str(msg.get("X-Spam-Flag", "")).strip().lower() == "yes":
        return "automated:spam-flag"
    if AUTO_SENDER_RE.match(sender):
        return "automated:no-reply-sender"
    if AUTO_SUBJECT_RE.match(rec.get("subject") or ""):
        return "automated:auto-reply"
    return None


def _gmail_labels(msg) -> str | None:
    labels = str(msg.get("X-Gmail-Labels", "")).strip()
    return labels[:200] or None


def _pst_folders(path: Path, digest: str) -> list[tuple[Path, str]]:
    """readpst once per file content; returns (mbox file, folder path) for every folder."""
    out = config.CACHE_DIR / "pst" / digest
    done = out / ".done"
    if not done.exists():
        readpst = shutil.which("readpst")
        if not readpst:
            raise MissingTool("readpst (libpst) is needed for .pst mailboxes: macOS `brew install libpst`, "
                              "Ubuntu `apt install pst-utils`; or export the mailbox as .mbox / use fetch-imap")
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        p = subprocess.run([readpst, "-q", "-r", "-8", "-o", str(out), str(path)], capture_output=True,
                           timeout=config.PARSE_TIMEOUT or None)
        if p.returncode:
            shutil.rmtree(out, ignore_errors=True)
            err = (p.stderr or p.stdout).decode("utf-8", "replace").strip()[-300:]
            raise RuntimeError(f"readpst could not read the file (exit {p.returncode}): {err or 'no message'}")
        done.write_text(dt.datetime.now().isoformat())
    folders = []
    for f in sorted(out.rglob("*")):
        if f.is_file() and not f.name.startswith(".") and _is_mbox(f):
            folders.append((f, f.parent.relative_to(out).as_posix() or "/"))
    return folders


def _is_mbox(f: Path) -> bool:
    with open(f, "rb") as fh:
        return fh.read(5) == b"From "
