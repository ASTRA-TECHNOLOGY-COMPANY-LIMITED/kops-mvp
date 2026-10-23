"""App state (F-00): users, sessions, audit, notifications, chat log, settings in SQLite `state/app.db`.

Kept apart from the data warehouse: the DW (DuckDB) is rebuilt from the KLMAS files at every build and is only read by
the app; this file survives rebuilds (Docker volume `kops_state`). One connection per call (WAL), so the app can serve
several requests at once.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from kops_dw import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL COLLATE NOCASE, display_name TEXT,
  role TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'viewer')),
  password_hash TEXT, must_change INTEGER NOT NULL DEFAULT 0, locked INTEGER NOT NULL DEFAULT 0,
  customer_scope TEXT,                      -- NULL = every customer; reserved for buyer accounts (not enabled)
  lang TEXT, default_page TEXT, is_system INTEGER NOT NULL DEFAULT 0,
  failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS session (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES user(id), csrf TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_seen TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, user_id INTEGER, username TEXT, action TEXT NOT NULL, target TEXT, detail TEXT,
  ip TEXT);
CREATE TABLE IF NOT EXISTS setting (
  key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT);
CREATE TABLE IF NOT EXISTS setting_history (
  id INTEGER PRIMARY KEY, key TEXT NOT NULL, old_value TEXT, new_value TEXT, at TEXT NOT NULL, by_user TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS notification (
  id INTEGER PRIMARY KEY, dedupe_key TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, rule TEXT NOT NULL, severity INTEGER NOT NULL,
  customer TEXT, season TEXT, brand TEXT, style_nk TEXT, style_no TEXT, factory_code TEXT, due_date TEXT,
  args TEXT, source TEXT, is_synthetic INTEGER NOT NULL DEFAULT 0,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, closed_at TEXT, build_id TEXT);
CREATE TABLE IF NOT EXISTS notification_state (
  notification_id INTEGER NOT NULL REFERENCES notification(id), user_id INTEGER NOT NULL REFERENCES user(id),
  status TEXT NOT NULL CHECK (status IN ('read', 'snoozed', 'done')), snooze_until TEXT, note TEXT, at TEXT NOT NULL,
  PRIMARY KEY (notification_id, user_id));
CREATE TABLE IF NOT EXISTS chat_log (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES user(id), at TEXT NOT NULL, lang TEXT, mode TEXT,
  question TEXT NOT NULL, intent TEXT, answer TEXT, rating INTEGER, rating_note TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def db_path() -> Path:
    return config.STATE_DIR / "app.db"


@contextmanager
def connect():
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init() -> None:
    with connect() as con:
        con.executescript(SCHEMA)


def rows(sql: str, params=()) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def one(sql: str, params=()) -> dict | None:
    r = rows(sql, params)
    return r[0] if r else None


def execute(sql: str, params=()) -> int:
    with connect() as con:
        cur = con.execute(sql, params)
        return cur.lastrowid or cur.rowcount


def audit(action: str, user: dict | None = None, target: str | None = None, detail=None, ip: str | None = None) -> None:
    execute("INSERT INTO audit (at, user_id, username, action, target, detail, ip) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now(), user and user.get("id"), user and user.get("username"), action, target,
             json.dumps(detail, ensure_ascii=False) if isinstance(detail, (dict, list)) else detail, ip))


def meta_get(key: str) -> str | None:
    r = one("SELECT value FROM meta WHERE key = ?", (key,))
    return r["value"] if r else None


def meta_set(key: str, value: str) -> None:
    execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, value))
