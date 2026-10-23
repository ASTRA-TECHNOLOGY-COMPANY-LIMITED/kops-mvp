"""Accounts and sessions (F-00 / F-01).

Passwords: argon2id, at least 10 characters. Sessions: random token in an httpOnly, SameSite=Lax cookie, 12 hours; only
its SHA-256 is stored, with a per-session CSRF token that every POST must echo in the X-CSRF-Token header (login: a
double-submit cookie). 5 wrong passwords lock the account for 15 minutes. Roles: viewer < manager < admin.
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
CSRF_COOKIE = "kops_csrf"
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


# a user who must change the password (first login, reset by an admin) may only do that
MUST_CHANGE_OK = {"/api/me", "/api/password", "/api/logout"}
ROLES = ("viewer", "manager", "admin")
MAX_FAILS, LOCK_MINUTES, MIN_PASSWORD = 5, 15, 10


def require_user(request: Request) -> dict:
    """Dependency for data / API routes: 401 without a valid session, 403 while the password must be changed."""
    u = session_user(request)
    if not u:
        raise HTTPException(401, "login required")
    if u["must_change"] and request.url.path not in MUST_CHANGE_OK:
        raise HTTPException(403, "password change required")
    return u


def require_page_user(request: Request) -> dict:
    """Dependency for HTML pages: redirect to the login page without a valid session (or to change the password)."""
    u = session_user(request)
    if not u or u["must_change"]:
        raise LoginRequired()
    return u


def require_role(minimum: str):
    """Dependency factory: viewer < manager < admin."""
    def dep(request: Request) -> dict:
        u = require_user(request)
        if ROLES.index(u["role"]) < ROLES.index(minimum):
            raise HTTPException(403, "not allowed")
        return u
    return dep


def require_csrf(request: Request) -> dict:
    """Dependency for every POST / PUT / DELETE of a logged-in user: X-CSRF-Token must equal the session token."""
    u = require_user(request)
    if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), u["csrf"]):
        raise HTTPException(403, "csrf")
    return u


def check_login_csrf(request: Request) -> None:
    """Login has no session yet: double-submit cookie set by GET /login."""
    c, h = request.cookies.get(CSRF_COOKIE, ""), request.headers.get("x-csrf-token", "")
    if not c or not secrets.compare_digest(c, h):
        raise HTTPException(403, "csrf")


def password_problem(pw: str, username: str) -> str | None:
    if len(pw) < MIN_PASSWORD:
        return "too_short"
    if pw.lower() == username.lower():
        return "same_as_user"
    return None


def register_failure(user: dict) -> None:
    fails = user["failed_logins"] + 1
    until = (dt.datetime.now() + dt.timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds") if fails >= MAX_FAILS else None
    state.execute("UPDATE user SET failed_logins = ?, locked_until = coalesce(?, locked_until) WHERE id = ?",
                  (0 if until else fails, until, user["id"]))


def is_temporarily_locked(user: dict) -> bool:
    return bool(user["locked_until"] and user["locked_until"] > state.now())


def set_password(user_id: int, pw: str, must_change: bool) -> None:
    state.execute("UPDATE user SET password_hash = ?, must_change = ?, failed_logins = 0, locked_until = NULL, updated_at = ? WHERE id = ?",
                  (hash_password(pw), int(must_change), state.now(), user_id))


def end_user_sessions(user_id: int) -> None:
    state.execute("DELETE FROM session WHERE user_id = ?", (user_id,))


def set_cookie(response, token: str) -> None:
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_HOURS * 3600, path="/")
