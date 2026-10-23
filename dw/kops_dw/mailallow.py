"""Mail allow-list (N-06): senders / domains whose mail is never dropped by the mailbox filters (ingest/mailbox.py).

The list lives in dw/mail_allow.local.txt (git-ignored: real partner addresses); dw/mail_allow.example.txt shows the
format. One entry per line, '#' starts a comment:
  klmas-sample.vn            a whole company domain (KLMAS, buyer, factory, forwarder)
  factory.owner@gmail.com    one address on a free mail service
A whole free-mail domain (gmail.com, naver.com, daum.net ...) is refused: it would let every spammer on it through.

  python -m kops_dw mail-allow suggest [--write]   domains / addresses seen in the loaded emails (From, To, Cc)
  python -m kops_dw mail-allow report               messages the filters drop with and without the list
"""
from __future__ import annotations

import collections
import re
from pathlib import Path

from . import config

FREE_MAIL = config.FREE_MAIL
ADDR_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def load(path: Path | None = None) -> tuple[list[str], list[str]]:
    """-> (entries, refused) from the list file; refused = whole free-mail domains."""
    path = path or config.MAIL_ALLOW_FILE
    entries, refused = [], []
    if not path.exists():
        return entries, refused
    for line in path.read_text(encoding="utf-8").splitlines():
        e = line.split("#", 1)[0].strip().lower().lstrip("@")
        if not e:
            continue
        (refused if e in FREE_MAIL else entries).append(e)
    return entries, refused


def _observed(con) -> tuple[collections.Counter, dict]:
    """Address -> number of messages it appears in (From / To / Cc of real emails), and role counts."""
    seen, roles = collections.Counter(), collections.defaultdict(collections.Counter)
    for sender, to, cc in con.execute("SELECT sender_email, recipients, cc FROM core.email WHERE NOT is_sample").fetchall():
        for role, txt in (("from", sender), ("to", to), ("cc", cc)):
            for a in {x.lower() for x in ADDR_RE.findall(txt or "")}:
                seen[a] += 1
                roles[a][role] += 1
    return seen, roles


def suggest(write: bool = False) -> int:
    import duckdb
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    seen, roles = _observed(con)
    con.close()
    domains = collections.Counter()
    for a, n in seen.items():
        domains[a.split("@", 1)[1]] += n
    lines = ["# KOPS mail allow-list, generated from the emails loaded in the DW (python -m kops_dw mail-allow suggest)",
             "# Review before use: remove anything that is not KLMAS, a buyer, a factory or a forwarder.", "",
             "# Company domains (messages seen)"]
    lines += [f"{d:<40} # {n}" for d, n in domains.most_common() if d not in FREE_MAIL]
    lines += ["", "# Addresses on free mail services (never the whole domain)"]
    for a, n in sorted(seen.items(), key=lambda x: (-x[1], x[0])):
        if a.split("@", 1)[1] in FREE_MAIL:
            r = roles[a]
            lines.append(f"{a:<40} # {n} (from {r['from']}, to {r['to']}, cc {r['cc']})")
    text = "\n".join(lines) + "\n"
    if write:
        if config.MAIL_ALLOW_FILE.exists():
            print(f"{config.MAIL_ALLOW_FILE} exists: not overwritten (delete it first to regenerate)")
            return 1
        config.MAIL_ALLOW_FILE.write_text(text, encoding="utf-8")
        print(f"Wrote {config.MAIL_ALLOW_FILE} ({sum(1 for x in lines if x and not x.startswith('#'))} entries)")
    else:
        print(text)
    return 0


def _allowed(sender: str, allow: list[str]) -> bool:
    return bool(sender) and any(sender == a or sender.endswith("@" + a) for a in allow)


def report(paths: list[str]) -> int:
    """Filtered messages without / with the allow-list: real emails in the DW (sender rules only: the saved threads
    carry no list / auto-submitted headers) and every mailbox given or loaded (all rules)."""
    import duckdb

    from .ingest import mailbox
    allow, refused = load()
    print(f"Allow-list {config.MAIL_ALLOW_FILE.name}: {len(allow)} entries"
          + (f"; refused (whole free-mail domain): {', '.join(refused)}" if refused else ""))
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    senders = [s or "" for (s,) in con.execute("SELECT sender_email FROM core.email WHERE NOT is_sample").fetchall()]
    boxes = paths or [p for (p,) in con.execute(
        "SELECT m.path FROM etl.source_file f JOIN etl.manifest m ON m.sha256 = f.sha256 WHERE f.parser = 'mailbox'"
    ).fetchall()]
    con.close()
    before = sum(1 for s in senders if mailbox.AUTO_SENDER_RE.match(s))
    after = sum(1 for s in senders if mailbox.AUTO_SENDER_RE.match(s) and not _allowed(s, allow))
    print(f"Emails in the DW ({len(senders)} messages, sender rules): filtered {before} without the list, {after} with it")
    saved = config.MAIL_ALLOW
    for p in boxes:
        counts = {}
        for label, lst in (("without", []), ("with", allow)):
            config.MAIL_ALLOW = lst
            reasons = collections.Counter()
            for msg, rec in mailbox.iter_messages(Path(p)):
                reasons[mailbox.why_filtered(msg, rec) or "kept"] += 1
            counts[label] = reasons
        config.MAIL_ALLOW = saved
        kept = {k: v.get("kept", 0) for k, v in counts.items()}
        total = sum(counts["without"].values())
        print(f"{Path(p).name}: {total} messages; filtered {total - kept['without']} without the list, "
              f"{total - kept['with']} with it")
        for reason in sorted(set(counts["without"]) | set(counts["with"])):
            if reason != "kept":
                print(f"   {reason:<28} {counts['without'].get(reason, 0):>6} -> {counts['with'].get(reason, 0):>6}")
    return 0


def cli(args: list[str]) -> int:
    if args and args[0] == "suggest":
        return suggest(write="--write" in args)
    if args and args[0] == "report":
        return report([a for a in args[1:] if not a.startswith("--")])
    print(__doc__)
    return 2
