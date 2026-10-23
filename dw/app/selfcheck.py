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


def sql_guard_checks() -> list[tuple[str, bool, str]]:
    """query_mart (chatbot AI mode): only one SELECT on mart / dim; everything else refused before it reaches DuckDB."""
    from .chat_llm import SqlRefused, check_sql
    allowed = ["SELECT style_no FROM mart.mgr_style LIMIT 1", "WITH t AS (SELECT * FROM dim.style) SELECT count(*) FROM t"]
    refused = ["SELECT * FROM core.email", "SELECT * FROM etl.source_file", "SELECT * FROM read_csv('/etc/passwd')",
               "SELECT getenv('ANTHROPIC_API_KEY')", "SELECT 1; DROP TABLE mart.mgr_style", "DELETE FROM mart.mgr_style",
               "ATTACH 'x.db'", "COPY mart.mgr_style TO 'x.csv'", "SELECT * FROM 'build/kops.duckdb'", "PRAGMA database_list"]
    bad = []
    for q in allowed:
        try:
            check_sql(q)
        except SqlRefused as e:
            bad.append(f"refused: {q} ({e})")
    for q in refused:
        try:
            check_sql(q)
            bad.append(f"allowed: {q}")
        except SqlRefused:
            pass
    return [("Chatbot query_mart guard: SELECT on mart / dim only (2 allowed, 10 refused)", not bad, "; ".join(bad) or "ok")]


def check() -> list[tuple[str, bool, str]]:
    from .chat_eval import check as chat_check
    return notification_checks() + chat_check() + sql_guard_checks() + security_checks()


# ------------------------------------------------------------------------------------------------- security (F-07)
PUBLIC = {("GET", "/login"), ("POST", "/api/login"), ("GET", "/healthz"), ("GET", "/branding/{name}"), ("GET", "/vendor/{name}")}
ADMIN_ONLY = {("GET", "/api/users"), ("POST", "/api/users"), ("POST", "/api/users/{uid}"), ("GET", "/api/audit"),
              ("GET", "/api/settings"), ("POST", "/api/settings"), ("GET", "/api/chat/rated")}
MANAGER_ONLY = {("POST", "/api/chat")}                 # viewers: dashboards only


def _routes(app):
    from fastapi.routing import APIRoute
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in sorted(r.methods - {"HEAD"}):
                out.append((m, r.path))
    return out


def _fill(path: str) -> str:
    return path.replace("{kind}", "mgr").replace("{name}", "index.json").replace("{uid}", "1").replace("{cid}", "1")


def security_checks() -> list[tuple[str, bool, str]]:
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    from fastapi.testclient import TestClient

    from . import auth, state
    from .main import create_app
    out = []
    old = config.STATE_DIR
    with tempfile.TemporaryDirectory(prefix="kops-sec-") as tmp:
        config.STATE_DIR = Path(tmp)
        try:
            app = create_app(bootstrap=False)
            routes = _routes(app)
            pw = "Check-pass-12345"
            for name, role in (("sec-admin", "admin"), ("sec-manager", "manager"), ("sec-viewer", "viewer")):
                auth.create_user(name, pw, role)

            def client(user=None):
                c = TestClient(app, follow_redirects=False)
                c.get("/login")
                if user:
                    r = c.post("/api/login", json={"username": user, "password": pw}, headers={"X-CSRF-Token": c.cookies.get(auth.CSRF_COOKIE)})
                    c.headers["X-CSRF-Token"] = r.json()["csrf"]
                return c

            # 1. no session: every non-public route of the router (listed automatically) -> 401 or redirect to /login
            anon, leaks = client(), []
            for m, p in routes:
                if (m, p) in PUBLIC:
                    continue
                r = anon.request(m, _fill(p), json={} if m == "POST" else None)
                ok = r.status_code == 401 or (r.status_code in (302, 303, 307) and r.headers.get("location", "").startswith("/login"))
                if m == "POST" and r.status_code == 403:      # CSRF refused before the session check: still no access
                    ok = True
                if not ok:
                    leaks.append(f"{m} {p} -> {r.status_code}")
            out.append((f"Security: no session -> 401 / login on every route ({len(routes) - len(PUBLIC)} routes listed from the router)",
                        not leaks, "; ".join(leaks) or "ok"))
            # 2. roles: viewer / manager kept out of admin routes, viewer out of the chatbot
            bad = []
            for user, forbidden in (("sec-viewer", ADMIN_ONLY | MANAGER_ONLY), ("sec-manager", ADMIN_ONLY)):
                c = client(user)
                for m, p in forbidden:
                    r = c.request(m, _fill(p), json={"username": "x-new", "role": "admin", "action": "role", "values": {}, "question": "?"} if m == "POST" else None)
                    if r.status_code != 403:
                        bad.append(f"{user} {m} {p} -> {r.status_code}")
            unknown = [f"{m} {p}" for m, p in routes if any(k in p for k in ("users", "audit", "settings", "rated")) and (m, p) not in ADMIN_ONLY]
            out.append(("Security: viewer / manager get 403 on Settings, users, audit, chat review; viewer on the chatbot",
                        not bad and not unknown, "; ".join(bad + [f"not in ADMIN_ONLY: {u}" for u in unknown]) or f"{len(ADMIN_ONLY)} admin routes"))
            # 3. CSRF: every POST of a logged-in admin without the token -> 403
            c = client("sec-admin")
            token = c.headers.pop("X-CSRF-Token")
            missing = [f"POST {p} -> {c.post(_fill(p), json={}).status_code}" for m, p in routes if m == "POST"
                       and c.post(_fill(p), json={}).status_code != 403]
            c.headers["X-CSRF-Token"] = token
            out.append(("Security: POST without CSRF token -> 403 (all POST routes)", not missing, "; ".join(missing) or
                        f"{sum(1 for m, _ in routes if m == 'POST')} POST routes"))
            # 4. lockout after 5 wrong passwords, 5. expired session
            c = client()
            codes = [c.post("/api/login", json={"username": "sec-manager", "password": "wrong"}, headers={"X-CSRF-Token": c.cookies.get(auth.CSRF_COOKIE)}).status_code
                     for _ in range(6)]
            right = c.post("/api/login", json={"username": "sec-manager", "password": pw}, headers={"X-CSRF-Token": c.cookies.get(auth.CSRF_COOKIE)}).status_code
            out.append(("Security: 5 wrong passwords lock the account for 15 min (right password then refused)", codes[:5] == [401] * 5 and right == 423,
                        f"{codes} then {right}"))
            v = client("sec-viewer")
            state.execute("UPDATE session SET expires_at = '2000-01-01T00:00:00'")
            out.append(("Security: an expired session (12 h) is refused", v.get("/api/me").status_code == 401, str(v.get("/api/me").status_code)))
        finally:
            config.STATE_DIR = old
    return out
