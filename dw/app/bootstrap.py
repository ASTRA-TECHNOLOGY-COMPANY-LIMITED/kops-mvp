"""First admin account (F-01): KOPS_ADMIN_USER / KOPS_ADMIN_PASSWORD from the environment or the repo's .env."""
from __future__ import annotations

import os
import secrets

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


def ensure_env_admin() -> tuple[str, str] | None:
    """KOPS_ADMIN_USER / KOPS_ADMIN_PASSWORD from the environment or .env; when .env has none, a strong random password is
    appended to .env (only these two lines, other variables untouched). The password is never printed."""
    user, pw = env("KOPS_ADMIN_USER"), env("KOPS_ADMIN_PASSWORD")
    if user and pw:
        return user, pw
    user, pw = user or "admin", secrets.token_urlsafe(18)
    try:
        existed = ENV_FILE.exists()
        with ENV_FILE.open("a", encoding="utf-8") as f:
            if existed and not ENV_FILE.read_text(encoding="utf-8").endswith("\n"):
                f.write("\n")
            f.write("# First admin of the KOPS app (generated; must be changed at first login)\n")
            if not env("KOPS_ADMIN_USER"):
                f.write(f"KOPS_ADMIN_USER={user}\n")
            f.write(f"KOPS_ADMIN_PASSWORD={pw}\n")
        if not existed:
            os.chmod(ENV_FILE, 0o600)
    except OSError:
        return None                     # read-only (container without .env): `make up` writes it on the host first
    os.environ["KOPS_ADMIN_USER"], os.environ["KOPS_ADMIN_PASSWORD"] = user, pw
    return user, pw


def ensure_admin() -> None:
    if state.one("SELECT id FROM user WHERE role = 'admin' AND NOT is_system"):
        return
    creds = ensure_env_admin()
    if creds:
        auth.create_user(creds[0], creds[1], "admin", must_change=True)
        state.audit("admin_bootstrap", None, creds[0])
        print(f"Admin account '{creds[0]}' created; its first password is KOPS_ADMIN_PASSWORD in .env (change it at first login)",
              flush=True)


def reset_admin() -> str:
    """`make admin-reset` / `python -m kops_dw admin-reset`: password of the env admin back to KOPS_ADMIN_PASSWORD."""
    state.init()
    creds = ensure_env_admin()
    if not creds:
        return "KOPS_ADMIN_USER / KOPS_ADMIN_PASSWORD missing"
    u = auth.get_user(creds[0])
    if u:
        auth.set_password(u["id"], creds[1], must_change=True)
        state.execute("UPDATE user SET locked = 0, role = 'admin' WHERE id = ?", (u["id"],))
        auth.end_user_sessions(u["id"])
    else:
        auth.create_user(creds[0], creds[1], "admin", must_change=True)
    state.audit("admin_reset", None, creds[0])
    return f"Admin '{creds[0]}' reset to KOPS_ADMIN_PASSWORD from .env; change it at the next login"
