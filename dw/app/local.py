"""The app on a free local port with a throw-away state DB, for the UI test and the PDF report (F-00).

Nothing is written to the real state/app.db: users and sessions live in a temporary directory removed afterwards.
"""
from __future__ import annotations

import secrets
import tempfile
from contextlib import contextmanager
from pathlib import Path

from kops_dw import config


@contextmanager
def local_app(role: str = "admin"):
    """-> dict(url, port, cookie, csrf, username, password, add_cookie(context))"""
    from . import auth, state
    from .main import run_in_thread
    old = config.STATE_DIR
    with tempfile.TemporaryDirectory(prefix="kops-state-") as tmp:
        config.STATE_DIR = Path(tmp)
        state.init()
        username, password = f"kops-{role}-test", secrets.token_urlsafe(16)
        uid = auth.create_user(username, password, role)
        server, port = run_in_thread()
        try:
            user = state.one("SELECT * FROM user WHERE id = ?", (uid,))

            def new_session():
                token, csrf = auth.issue_session(user)
                return {"name": auth.COOKIE, "value": token, "domain": "127.0.0.1", "path": "/", "httpOnly": True,
                        "sameSite": "Lax"}, csrf

            cookie, csrf = new_session()
            yield {"url": f"http://127.0.0.1:{port}", "port": port, "cookie": cookie, "csrf": csrf, "username": username,
                   "password": password, "user": user, "new_session": new_session}
        finally:
            server.should_exit = True
            config.STATE_DIR = old
