"""Thresholds editable by an admin (F-03): kept in app.db with a change history and written to state/rules.json, which
the data-warehouse build reads (config._rule_overrides). A change applies from the next build (`make refresh`)."""
from __future__ import annotations

import json

from kops_dw import config

from . import state

# key -> (min, max); defaults are config.RULES as shipped in the code
EDITABLE = {
    "approval_days_before": (0, 60),
    "approval_days_after": (1, 120),
    "critical_days_plan": (1, 60),
    "critical_days_cut": (1, 60),
    "stale_weekdays": (1, 10),
    "year_suspect_days": (60, 400),
    "qty_tolerance_pct": (0, 20),
    "ontime_tolerance_days": (0, 30),
}


def _defaults() -> dict:
    return {k: config.RULES[k] for k in EDITABLE}      # RULES already carries the rules.json overrides


def rules_file():
    return config.STATE_DIR / "rules.json"


def current() -> dict:
    vals = dict(_defaults())
    for r in state.rows("SELECT key, value FROM setting"):
        if r["key"] in EDITABLE:
            vals[r["key"]] = int(r["value"])
    return vals


def update(user: dict, changes: dict, note: str | None) -> dict:
    cur = current()
    clean = {}
    for k, v in changes.items():
        if k not in EDITABLE:
            raise ValueError(f"unknown setting {k}")
        lo, hi = EDITABLE[k]
        v = int(v)
        if not lo <= v <= hi:
            raise ValueError(f"{k} must be {lo}..{hi}")
        if v != cur[k]:
            clean[k] = v
    now = state.now()
    with state.connect() as con:
        for k, v in clean.items():
            con.execute("INSERT INTO setting_history (key, old_value, new_value, at, by_user, note) VALUES (?, ?, ?, ?, ?, ?)",
                        (k, str(cur[k]), str(v), now, user["username"], (note or "")[:300]))
            con.execute("""INSERT INTO setting (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)
                           ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at,
                           updated_by = excluded.updated_by""", (k, str(v), now, user["username"]))
    if clean:
        new = current()
        rules_file().parent.mkdir(parents=True, exist_ok=True)
        rules_file().write_text(json.dumps(new, indent=1) + "\n", encoding="utf-8")
        state.audit("settings_changed", user, ",".join(clean), clean)
    return clean


def history() -> list[dict]:
    return state.rows("SELECT key, old_value, new_value, at, by_user, note FROM setting_history ORDER BY id DESC LIMIT 200")
