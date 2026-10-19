"""CLI: python -m kops_dw [build|test|dashboard|all]"""
from __future__ import annotations

import sys


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "all"
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
