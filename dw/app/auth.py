"""Accounts and sessions (F-00 / F-01).

Passwords: argon2id. Sessions: random token in an httpOnly, SameSite=Lax cookie; only its SHA-256 is stored, with a
per-session CSRF token that every POST must echo in the X-CSRF-Token header.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request

from . import state

COOKIE = "kops_session"
SESSION_HOURS = 12
_ph = PasswordHasher()


class LoginRequired(Exception):
    """Raised for an HTML page without a valid session: the app answers with a redirect to /login."""


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def check_password(user: dict, pw: str) -> bool:
    if not user.get("password_hash"):
        return False
    try:
        return _ph.verify(user["password_hash"], pw)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(username: str, password: str | None, role: str, *, must_change: bool = False, is_system: bool = False,
                display_name: str | None = None) -> int:
    t = state.now()
    return state.execute(
        """INSERT INTO user (username, display_name, role, password_hash, must_change, is_system, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (username, display_name or username, role, hash_password(password) if password else None, int(must_change),
         int(is_system), t, t))


def get_user(username: str) -> dict | None:
    return state.one("SELECT * FROM user WHERE username = ?", (username,))


def issue_session(user: dict) -> tuple[str, str]:
    """New session for a user -> (token for the cookie, csrf token)."""
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    now = dt.datetime.now()
    state.execute("INSERT INTO session (token_hash, user_id, csrf, created_at, expires_at, last_seen) VALUES (?, ?, ?, ?, ?, ?)",
                  (_h(token), user["id"], csrf, now.isoformat(timespec="seconds"),
                   (now + dt.timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds"), now.isoformat(timespec="seconds")))
    return token, csrf


def end_session(token: str | None) -> None:
    if token:
        state.execute("DELETE FROM session WHERE token_hash = ?", (_h(token),))


def session_user(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    s = state.one("""SELECT s.csrf, s.expires_at, u.* FROM session s JOIN user u ON u.id = s.user_id
                     WHERE s.token_hash = ?""", (_h(token),))
    if not s or s["expires_at"] < state.now() or s["locked"]:
        if s:
            end_session(token)
        return None
    return s


def require_user(request: Request) -> dict:
    """Dependency for data / API routes: 401 without a valid session."""
    u = session_user(request)
    if not u:
        raise HTTPException(401, "login required")
    return u


def require_page_user(request: Request) -> dict:
    """Dependency for HTML pages: redirect to the login page without a valid session."""
    u = session_user(request)
    if not u:
        raise LoginRequired()
    return u


def set_cookie(response, token: str) -> None:
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_HOURS * 3600, path="/")
