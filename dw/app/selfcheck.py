"""App checks run with `python -m kops_dw test` (F-03 / F-07), on a throw-away state DB and the current DW."""
from __future__ import annotations

import collections
import tempfile
from pathlib import Path

import duckdb

from kops_dw import config


def notification_checks() -> list[tuple[str, bool, str]]:
    from . import notify, state
    out = []
    old = config.STATE_DIR
    with tempfile.TemporaryDirectory(prefix="kops-check-") as tmp:
        config.STATE_DIR = Path(tmp)
        try:
            state.init()
            acts = notify.read_actions()
            first = notify.sync(force=True, acts=acts, bid="check-1")
            again = notify.sync(force=True, acts=acts, bid="check-2")
            n_rows = state.one("SELECT count(*) n FROM notification")["n"]
            out.append(("Notifications: a rebuild adds no duplicate (open / rows after 2 syncs)",
                        again["new"] == 0 and n_rows == first["open"], f"{first['open']} / {n_rows}, new on 2nd sync {again['new']}"))
            # 27SS counts per kind = the action list (E-04), distinct lines (an exact duplicate file message counts once)
            con = duckdb.connect(str(config.DB_PATH), read_only=True)
            exp = collections.Counter()
            for t, txt, n in con.execute("""SELECT action_type, txt, count(DISTINCT (action_type, coalesce(style_nk, customer || '|' || factory_code),
                                                   source, txt, d1, d2)) FROM mart.mgr_action WHERE season = '27SS' GROUP BY 1, 2""").fetchall():
                if notify.kind_of(t, txt):
                    exp[notify.kind_of(t, txt)] += n
            con.close()
            got = collections.Counter(r["kind"] for r in state.rows("SELECT kind FROM notification WHERE season = '27SS' AND closed_at IS NULL"))
            fmt = lambda c: ", ".join(f"{k} {c.get(k, 0)}" for k in ("LATE", "AT_RISK", "DATA"))  # noqa: E731
            out.append(("Notifications 27SS per kind = Việc cần xử lý (LATE / AT_RISK / DATA)", got == exp, f"{fmt(got)} (actions: {fmt(exp)})"))
            # a condition that is gone closes the notice; when it comes back the same notice reopens
            drop = next(a for a in acts if notify.kind_of(a["action_type"], a["txt"]) and a["style_nk"])
            notify.sync(force=True, acts=[a for a in acts if a is not drop], bid="check-3")
            closed = state.one("SELECT count(*) n FROM notification WHERE closed_at IS NOT NULL")["n"]
            back = notify.sync(force=True, acts=acts, bid="check-4")
            out.append(("Notifications: closed when the condition is gone, reopened when it returns",
                        closed >= 1 and back["reopened"] >= 1 and back["new"] == 0, f"closed {closed}, reopened {back['reopened']}"))
        finally:
            config.STATE_DIR = old
    return out


def check() -> list[tuple[str, bool, str]]:
    return notification_checks()
