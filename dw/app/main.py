"""KOPS web app (F-00): FastAPI on top of the data warehouse.

- The DW (build/kops.duckdb and the JSON files rendered from it) is only read; app state lives in state/app.db.
- Every data file is served by an API route that checks the session; there is no static path to build/.
  Public without login: /login, /api/login, /healthz, /vendor/*.js (chart library) and /branding/* (logo).
- Accounts (F-01): roles viewer < manager < admin, CSRF on every POST, lockout, 12 h sessions (auth.py).
- `python -m kops_dw serve [--host 127.0.0.1] [--port 8765]` runs it with uvicorn.
"""
from __future__ import annotations

import re
import secrets
import socket
import threading
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from kops_dw import config

from . import auth, notify, settings, state

TEMPLATES = config.DW_DIR / "templates"
_NAME = re.compile(r"^[\w.-]+\.json$")


def _data_dir(kind: str) -> Path:
    return {"mgr": config.BUILD_DIR / "data" / "mgr", "analyst": config.BUILD_DIR / "data"}[kind]


def _version() -> str:
    """KOPS_VERSION (set by `make up` from git), else the short git hash of this checkout."""
    import os
    import subprocess
    if os.environ.get("KOPS_VERSION"):
        return os.environ["KOPS_VERSION"]
    try:
        return subprocess.run(["git", "-C", str(config.REPO_DIR), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or "dev"
    except (OSError, subprocess.SubprocessError):
        return "dev"


VERSION = _version()


def brand_name() -> str:
    from .bootstrap import env
    return env("KOPS_BRAND_NAME") or "KLMAS"


def create_app(bootstrap: bool = True) -> FastAPI:
    state.init()
    if bootstrap:                     # first admin from .env (tests use a throw-away state DB and skip it)
        from .bootstrap import ensure_admin
        ensure_admin()
    try:
        notify.sync()                 # notices of the current build (also re-checked on every notification request)
    except Exception as e:            # noqa: BLE001 - the app must start even without a DW
        print(f"notifications not synced: {e}", flush=True)
    app = FastAPI(title="KOPS", docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(auth.LoginRequired)
    async def _to_login(request: Request, exc: auth.LoginRequired):
        nxt = request.url.path + (("?" + request.url.query) if request.url.query else "")
        return RedirectResponse("/login?next=" + nxt if nxt not in ("/", "") else "/login", status_code=303)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True, "dw": (config.BUILD_DIR / "data" / "mgr" / "index.json").exists()}

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        resp = HTMLResponse((TEMPLATES / "login.html").read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"})
        if not request.cookies.get(auth.CSRF_COOKIE):
            resp.set_cookie(auth.CSRF_COOKIE, secrets.token_urlsafe(24), samesite="strict", path="/")
        return resp

    @app.post("/api/login")
    async def login(request: Request):
        auth.check_login_csrf(request)
        body = await request.json()
        name, pw = str(body.get("username", ""))[:80], str(body.get("password", ""))
        user = auth.get_user(name)
        ip = request.client.host if request.client else None
        if user and auth.is_temporarily_locked(user):
            state.audit("login_locked", user, ip=ip)
            return JSONResponse({"ok": False, "error": "locked", "minutes": auth.LOCK_MINUTES}, status_code=423)
        if not user or user["is_system"] or user["locked"] or not auth.check_password(user, pw):
            if user:
                auth.register_failure(user)
            state.audit("login_failed", user, name, ip=ip)
            return JSONResponse({"ok": False, "error": "invalid"}, status_code=401)
        state.execute("UPDATE user SET failed_logins = 0, locked_until = NULL WHERE id = ?", (user["id"],))
        token, csrf = auth.issue_session(user)
        state.audit("login", user, ip=ip)
        resp = JSONResponse({"ok": True, "csrf": csrf, "must_change": bool(user["must_change"]),
                             "default_page": user["default_page"], "lang": user["lang"]})
        auth.set_cookie(resp, token)
        return resp

    @app.post("/api/logout")
    def logout(request: Request, user: dict = Depends(auth.require_csrf)):
        auth.end_session(request.cookies.get(auth.COOKIE))
        state.audit("logout", user)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(auth.COOKIE, path="/")
        return resp

    @app.get("/api/me")
    def me(user: dict = Depends(auth.require_user)):
        return {k: user[k] for k in ("username", "display_name", "role", "must_change", "lang", "default_page", "csrf")}

    @app.post("/api/password")
    async def change_password(request: Request, user: dict = Depends(auth.require_csrf)):
        body = await request.json()
        old, new = str(body.get("old", "")), str(body.get("new", ""))
        if not auth.check_password(user, old):
            state.audit("password_change_failed", user)
            return JSONResponse({"ok": False, "error": "old_wrong"}, status_code=400)
        problem = auth.password_problem(new, user["username"]) or ("same_as_old" if new == old else None)
        if problem:
            return JSONResponse({"ok": False, "error": problem, "min": auth.MIN_PASSWORD}, status_code=400)
        auth.set_password(user["id"], new, must_change=False)
        state.audit("password_changed", user)
        return {"ok": True}

    @app.post("/api/profile")
    async def profile(request: Request, user: dict = Depends(auth.require_csrf)):
        body = await request.json()
        page = body.get("default_page")
        lang = body.get("lang")
        state.execute("UPDATE user SET default_page = coalesce(?, default_page), lang = coalesce(?, lang), updated_at = ? WHERE id = ?",
                      (page if isinstance(page, str) and re.match(r"^[a-z]{2,20}$", page) else None,
                       lang if lang in ("vi", "ko") else None, state.now(), user["id"]))
        return {"ok": True}

    # ---------------------------------------------------------------- admin: users and audit
    def _user_row(u):
        return {k: u[k] for k in ("id", "username", "display_name", "role", "locked", "must_change", "customer_scope",
                                  "locked_until", "created_at", "updated_at")}

    @app.get("/api/users")
    def users(user: dict = Depends(auth.require_role("admin"))):
        return [_user_row(u) for u in state.rows("SELECT * FROM user WHERE NOT is_system ORDER BY username")]

    @app.post("/api/users")
    async def create_user(request: Request, user: dict = Depends(auth.require_csrf)):
        auth.require_role("admin")(request)
        body = await request.json()
        name, role = str(body.get("username", "")).strip(), body.get("role", "viewer")
        if not re.match(r"^[A-Za-z0-9._@-]{3,60}$", name) or role not in auth.ROLES or auth.get_user(name):
            return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
        temp = secrets.token_urlsafe(12)            # shown once to the admin, must be changed at first login
        uid = auth.create_user(name, temp, role, must_change=True, display_name=str(body.get("display_name") or name)[:80])
        state.audit("user_created", user, name, {"role": role})
        return {"ok": True, "id": uid, "temp_password": temp}

    @app.post("/api/users/{uid}")
    async def update_user(uid: int, request: Request, user: dict = Depends(auth.require_csrf)):
        auth.require_role("admin")(request)
        body = await request.json()
        target = state.one("SELECT * FROM user WHERE id = ? AND NOT is_system", (uid,))
        action = body.get("action")
        if not target:
            raise HTTPException(404)
        if target["id"] == user["id"] and action in ("lock", "role"):
            return JSONResponse({"ok": False, "error": "self"}, status_code=400)
        out = {"ok": True}
        if action == "lock":
            state.execute("UPDATE user SET locked = 1, updated_at = ? WHERE id = ?", (state.now(), uid))
            auth.end_user_sessions(uid)
        elif action == "unlock":
            state.execute("UPDATE user SET locked = 0, failed_logins = 0, locked_until = NULL, updated_at = ? WHERE id = ?", (state.now(), uid))
        elif action == "reset":
            temp = secrets.token_urlsafe(12)
            auth.set_password(uid, temp, must_change=True)
            auth.end_user_sessions(uid)
            out["temp_password"] = temp
        elif action == "role" and body.get("role") in auth.ROLES:
            state.execute("UPDATE user SET role = ?, updated_at = ? WHERE id = ?", (body["role"], state.now(), uid))
        else:
            return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
        state.audit("user_" + action, user, target["username"], {"role": body.get("role")} if action == "role" else None)
        return out

    @app.get("/api/audit")
    def audit_log(user: dict = Depends(auth.require_role("admin"))):
        return state.rows("SELECT at, username, action, target, detail, ip FROM audit ORDER BY id DESC LIMIT 500")

    @app.get("/api/app")
    def app_info(user: dict = Depends(auth.require_user)):
        return {"version": VERSION, "brand_name": brand_name()}

    @app.get("/", response_class=HTMLResponse)
    def home(user: dict = Depends(auth.require_page_user)):
        page = config.BUILD_DIR / "manager.html"
        if not page.exists():
            return HTMLResponse("<p>Dashboard not built yet: python -m kops_dw (or make up)</p>", status_code=503)
        return FileResponse(page, headers={"Cache-Control": "no-store"})

    @app.get("/dashboard.html", response_class=HTMLResponse)
    def analyst(user: dict = Depends(auth.require_page_user)):
        return FileResponse(config.BUILD_DIR / "dashboard.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/data/{kind}/{name}")
    def data(kind: str, name: str, user: dict = Depends(auth.require_user)):
        if kind not in ("mgr", "analyst") or not _NAME.match(name):
            raise HTTPException(404)
        f = _data_dir(kind) / name
        if not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, media_type="application/json", headers={"Cache-Control": "no-store"})

    @app.get("/branding/{name}")
    def branding(name: str):
        """Logo / favicon: branding/ at the repo root (mounted in Docker), .png before .svg, else the built-in default.
        No cache, so a replaced file shows on the next page load without a rebuild."""
        stem = name.rsplit(".", 1)[0]
        if stem not in ("logo", "logo-dark", "favicon"):
            raise HTTPException(404)
        for d in (config.BRANDING_DIR, config.DW_DIR / "templates" / "branding"):
            for ext, mt in (("png", "image/png"), ("svg", "image/svg+xml")):
                f = d / f"{stem}.{ext}"
                if f.is_file():
                    return FileResponse(f, media_type=mt, headers={"Cache-Control": "no-cache"})
        raise HTTPException(404)

    # ---------------------------------------------------------------- notifications (F-03)
    @app.get("/api/notifications")
    def notifications(closed: int = 0, user: dict = Depends(auth.require_user)):
        notify.sync()
        return notify.for_user(user, include_closed=bool(closed))

    @app.get("/api/notifications/count")
    def notification_count(user: dict = Depends(auth.require_user)):
        notify.sync()
        return {"unread": notify.unread_count(user), "build_id": notify.build_id()}

    @app.post("/api/notifications/state")
    async def notification_state(request: Request, user: dict = Depends(auth.require_csrf)):
        body = await request.json()
        status, ids = body.get("status"), [int(i) for i in body.get("ids", [])][:1000]
        if status not in ("read", "unread", "snoozed", "done"):
            raise HTTPException(400, "status")
        if status in ("snoozed", "done"):           # handling a notice is for managers; viewers only mark as read
            auth.require_role("manager")(request)
        n = notify.set_status(user, ids, status, (body.get("note") or None) and str(body["note"])[:500])
        if status == "done":
            state.audit("notification_done", user, ",".join(map(str, ids[:20])), body.get("note"))
        return {"ok": True, "n": n}

    # ---------------------------------------------------------------- settings (admin, F-03)
    @app.get("/api/settings")
    def get_settings(user: dict = Depends(auth.require_role("admin"))):
        return {"values": settings.current(), "limits": settings.EDITABLE, "history": settings.history()}

    @app.post("/api/settings")
    async def post_settings(request: Request, user: dict = Depends(auth.require_csrf)):
        auth.require_role("admin")(request)
        body = await request.json()
        try:
            changed = settings.update(user, body.get("values", {}), body.get("note"))
        except (ValueError, TypeError) as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        return {"ok": True, "changed": changed}

    @app.get("/vendor/{name}")
    def vendor(name: str):
        f = config.DW_DIR / "templates" / "vendor" / name
        if not re.match(r"^[\w.-]+\.js$", name) or not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, media_type="text/javascript")

    return app


def serve(argv: list[str]) -> int:
    import uvicorn
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    # inside the Docker container: --host 0.0.0.0, the host side publishes 127.0.0.1:8765 only (docker-compose.yml)
    host = argv[argv.index("--host") + 1] if "--host" in argv else "127.0.0.1"
    if not (config.BUILD_DIR / "data" / "mgr" / "index.json").exists():
        from kops_dw.dashboard import render
        render()
    print(f"KOPS app on http://127.0.0.1:{port}/ (Ctrl+C to stop; listening on {host})", flush=True)
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")
    return 0


def run_in_thread(host: str = "127.0.0.1"):
    """Start the app on a free local port in a background thread (UI test, PDF report) -> (server, port)."""
    import uvicorn
    with socket.socket() as s:
        s.bind((host, 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(bootstrap=False), host=host, port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return server, port
