"""KOPS web app (F-00): FastAPI on top of the data warehouse.

- The DW (build/kops.duckdb and the JSON files rendered from it) is only read; app state lives in state/app.db.
- Every data file is served by an API route that checks the session; there is no static path to build/.
  Public without login: /login, /api/login, /healthz, /vendor/*.js (chart library) and /branding/* (logo).
- `python -m kops_dw serve [--host 127.0.0.1] [--port 8765]` runs it with uvicorn.
"""
from __future__ import annotations

import re
import socket
import threading
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from kops_dw import config

from . import auth, state

TEMPLATES = config.DW_DIR / "templates"
_NAME = re.compile(r"^[\w.-]+\.json$")


def _data_dir(kind: str) -> Path:
    return {"mgr": config.BUILD_DIR / "data" / "mgr", "analyst": config.BUILD_DIR / "data"}[kind]


def create_app() -> FastAPI:
    state.init()
    from .bootstrap import ensure_admin
    ensure_admin()
    app = FastAPI(title="KOPS", docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(auth.LoginRequired)
    async def _to_login(request: Request, exc: auth.LoginRequired):
        nxt = request.url.path + (("?" + request.url.query) if request.url.query else "")
        return RedirectResponse("/login?next=" + nxt if nxt not in ("/", "") else "/login", status_code=303)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True, "dw": (config.BUILD_DIR / "data" / "mgr" / "index.json").exists()}

    @app.get("/login", response_class=HTMLResponse)
    def login_page():
        return HTMLResponse((TEMPLATES / "login.html").read_text(encoding="utf-8"))

    @app.post("/api/login")
    async def login(request: Request):
        body = await request.json()
        user = auth.get_user(str(body.get("username", "")))
        ip = request.client.host if request.client else None
        if not user or user["is_system"] or user["locked"] or not auth.check_password(user, str(body.get("password", ""))):
            state.audit("login_failed", None, str(body.get("username", ""))[:80], ip=ip)
            return JSONResponse({"ok": False, "error": "invalid"}, status_code=401)
        token, csrf = auth.issue_session(user)
        state.audit("login", user, ip=ip)
        resp = JSONResponse({"ok": True, "csrf": csrf, "must_change": bool(user["must_change"])})
        auth.set_cookie(resp, token)
        return resp

    @app.post("/api/logout")
    def logout(request: Request, user: dict = Depends(auth.require_user)):
        auth.end_session(request.cookies.get(auth.COOKIE))
        state.audit("logout", user)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(auth.COOKIE, path="/")
        return resp

    @app.get("/api/me")
    def me(user: dict = Depends(auth.require_user)):
        return {k: user[k] for k in ("username", "display_name", "role", "must_change", "lang", "default_page", "csrf")}

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
    server = uvicorn.Server(uvicorn.Config(create_app(), host=host, port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return server, port
