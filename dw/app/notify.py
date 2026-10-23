"""Notifications for late / at-risk orders (F-03), rebuilt from the marts after every build.

Source: mart.mgr_action (the "Việc cần xử lý" list, real data only), plus the synthetic flags of mart.mgr_style so a
notice resting on synthetic shipments / output is labelled. Kinds:
  LATE     ETD VN passed and shipped < ordered (tolerance Q13)                       <- FORECAST_LATE / ETD_PASSED_NOT_SHIPPED
  AT_RISK  plan BAL < 0 or finish + transit > RDD, forecast after RDD, approval missing before cutting, material after the
           cut date, factory without daily reports                                  <- PLAN_LATE, FORECAST_LATE, APPROVAL_MISSING,
                                                                                       MATERIAL_LATE, DAILY_STALE
  DATA     numbers differ between files, ETD typed with the wrong year              <- FILE_MISMATCH
Pending e-mail proposals stay on the action list only.
Dedupe key = rule + style (or customer / factory) + the milestone the notice is about, so a rebuild never duplicates a
notice; a notice whose condition is gone is closed (closed_at), and reopened if it comes back.
"""
from __future__ import annotations

import json
import threading

import duckdb

from kops_dw import config

from . import state

KIND = {"PLAN_LATE": "AT_RISK", "APPROVAL_MISSING": "AT_RISK", "MATERIAL_LATE": "AT_RISK", "DAILY_STALE": "AT_RISK",
        "FILE_MISMATCH": "DATA"}
_lock = threading.Lock()


def kind_of(action_type: str, txt: str | None) -> str | None:
    if action_type == "FORECAST_LATE":
        return "LATE" if txt == "ETD_PASSED_NOT_SHIPPED" else "AT_RISK"
    return KIND.get(action_type)


def _milestone(a: dict) -> str:
    """The date / item a notice is about: stays the same from one build to the next while the problem is the same."""
    t = a["action_type"]
    if t == "FORECAST_LATE":
        return f"{a['txt']}:{a['d2']}"
    if t == "PLAN_LATE":
        return f"{a['txt']}:{a['d2']}"
    if t == "APPROVAL_MISSING":
        return f"{a['d1']}:{a['txt']}"
    if t == "MATERIAL_LATE":
        return f"{a['txt']}:{a['d2']}"
    if t == "DAILY_STALE":
        return f"{a['season']}:{a['d1']}"
    return f"{a['source']}:{a['txt']}:{a['d1']}"


def build_id() -> str | None:
    f = config.BUILD_DIR / "data" / "mgr" / "index.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("build_id")
    except (OSError, ValueError):
        return None


def read_actions() -> list[dict]:
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        cur = con.execute("""
          SELECT a.*, coalesce(m.style_syn OR m.ship_syn OR m.out_syn OR m.insp_syn, false) AS syn
          FROM mart.mgr_action a LEFT JOIN mart.mgr_style m ON m.style_nk = a.style_nk""")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


def sync(force: bool = False, acts: list[dict] | None = None, bid: str | None = None) -> dict:
    """Bring app.notification in line with the current build. Cheap when the build did not change."""
    with _lock:
        bid = bid or build_id()
        if not bid or (not force and state.meta_get("notification_build") == bid):
            return {"skipped": True}
        if acts is None:
            try:
                acts = read_actions()
            except duckdb.Error:
                return {"error": "dw not readable (build running?)"}
        now = state.now()
        seen, new, reopened = set(), 0, 0
        with state.connect() as con:
            for a in acts:
                kind = kind_of(a["action_type"], a["txt"])
                if not kind:
                    continue
                who = a["style_nk"] or f"{a['customer']}|{a['factory_code']}"
                key = f"{a['action_type']}|{who}|{_milestone(a)}"
                if key in seen:
                    continue
                seen.add(key)
                args = json.dumps({k: (str(a[k]) if a[k] is not None else None) for k in ("d1", "d2", "n1", "txt")}, ensure_ascii=False)
                row = con.execute("SELECT id, closed_at FROM notification WHERE dedupe_key = ?", (key,)).fetchone()
                vals = (kind, a["action_type"], a["severity"], a["customer"], a["season"], a["brand"], a["style_nk"], a["style_no"],
                        a["factory_code"], str(a["due_date"]) if a["due_date"] else None, args, a["source"], int(bool(a["syn"])), now, bid)
                if row:
                    reopened += row["closed_at"] is not None
                    con.execute("""UPDATE notification SET kind = ?, rule = ?, severity = ?, customer = ?, season = ?, brand = ?,
                                   style_nk = ?, style_no = ?, factory_code = ?, due_date = ?, args = ?, source = ?, is_synthetic = ?,
                                   last_seen = ?, build_id = ?, closed_at = NULL WHERE id = ?""", (*vals, row["id"]))
                else:
                    new += 1
                    con.execute("""INSERT INTO notification (kind, rule, severity, customer, season, brand, style_nk, style_no,
                                   factory_code, due_date, args, source, is_synthetic, last_seen, build_id, dedupe_key, first_seen)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (*vals, key, now))
            open_keys = [r[0] for r in con.execute("SELECT dedupe_key FROM notification WHERE closed_at IS NULL").fetchall()]
            gone = [k for k in open_keys if k not in seen]
            con.executemany("UPDATE notification SET closed_at = ? WHERE dedupe_key = ?", [(now, k) for k in gone])
            con.execute("INSERT INTO meta (key, value) VALUES ('notification_build', ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                        (bid,))
        return {"open": len(seen), "new": new, "closed": len(gone), "reopened": reopened}


def for_user(user: dict, include_closed: bool = False) -> list[dict]:
    """Notices with this user's status; a snooze that ran out counts as unread again."""
    rows = state.rows(f"""
      SELECT n.*, s.status, s.snooze_until, s.note, s.at AS status_at FROM notification n
      LEFT JOIN notification_state s ON s.notification_id = n.id AND s.user_id = ?
      {'' if include_closed else 'WHERE n.closed_at IS NULL'}
      ORDER BY n.closed_at IS NOT NULL, n.severity, n.due_date, n.id""", (user["id"],))
    now = state.now()
    for r in rows:
        if r["status"] == "snoozed" and (r["snooze_until"] or "") <= now:
            r["status"] = None
        r["args"] = json.loads(r["args"] or "{}")
    return rows


def unread_count(user: dict) -> int:
    return sum(1 for r in for_user(user) if not r["status"])


def set_status(user: dict, ids: list[int], status: str, note: str | None = None) -> int:
    import datetime as dt
    now = state.now()
    until = (dt.datetime.now() + dt.timedelta(days=7)).isoformat(timespec="seconds") if status == "snoozed" else None
    with state.connect() as con:
        for i in ids:
            if status == "unread":
                con.execute("DELETE FROM notification_state WHERE notification_id = ? AND user_id = ?", (i, user["id"]))
            else:
                con.execute("""INSERT INTO notification_state (notification_id, user_id, status, snooze_until, note, at)
                               VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (notification_id, user_id)
                               DO UPDATE SET status = excluded.status, snooze_until = excluded.snooze_until,
                               note = coalesce(excluded.note, notification_state.note), at = excluded.at""",
                            (i, user["id"], status, until, note, now))
    return len(ids)
