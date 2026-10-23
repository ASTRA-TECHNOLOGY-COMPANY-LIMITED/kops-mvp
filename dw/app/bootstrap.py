"""First admin account (F-00 / F-01): KOPS_ADMIN_USER / KOPS_ADMIN_PASSWORD from the environment or the repo's .env."""
from __future__ import annotations

import os

from kops_dw import config

from . import auth, state

ENV_FILE = config.REPO_DIR / ".env"


def read_env_file() -> dict[str, str]:
    out = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def env(key: str) -> str | None:
    return os.environ.get(key) or read_env_file().get(key) or None


def ensure_admin() -> None:
    if state.one("SELECT id FROM user WHERE role = 'admin' AND NOT is_system"):
        return
    user, pw = env("KOPS_ADMIN_USER"), env("KOPS_ADMIN_PASSWORD")
    if user and pw:
        auth.create_user(user, pw, "admin", must_change=True)
        state.audit("admin_bootstrap", None, user)
