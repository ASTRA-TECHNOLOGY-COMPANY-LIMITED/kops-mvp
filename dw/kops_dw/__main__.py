"""CLI: python -m kops_dw [build|test|dashboard|all|fetch-imap|attachments]

  all          build + test + dashboard (default)
  fetch-imap   read-only download of a mailbox folder into raw-docs/inbox/imap/ (see kops_dw/inbox.py)
  attachments  save .eml attachments to raw-docs/EMAIL_ATTACHMENTS/ so they are parsed by the next build
"""
from __future__ import annotations

import sys


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "all"
    if cmd == "fetch-imap":
        from .inbox import fetch_imap
        return fetch_imap(argv[1:])
    if cmd == "attachments":
        from .inbox import attachments
        return attachments(argv[1:])
    if cmd in ("build", "all"):
        from .pipeline import build
        build()
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
