"""Golden evaluation of the chatbot's basic mode (F-04): dw/eval/chat_cases.json, expected facts from SQL on the marts."""
from __future__ import annotations

import json

import duckdb

from kops_dw import config

from . import chat

CASES = config.DW_DIR / "eval" / "chat_cases.json"


def _get(facts, path: str):
    """'a.b.0.c' into nested dicts / lists; a dict key may itself contain dots (sim_rows -> 'sim.style')."""
    parts = path.split(".")
    cur, i = facts, 0
    while i < len(parts):
        if isinstance(cur, list):
            p = parts[i]
            cur = cur[int(p)] if p.isdigit() and int(p) < len(cur) else None
            i += 1
        elif isinstance(cur, dict):
            for j in range(len(parts), i, -1):          # longest key first
                key = ".".join(parts[i:j])
                if key in cur:
                    cur, i = cur[key], j
                    break
            else:
                return None
        else:
            return None
    return cur


def _same(got, exp) -> bool:
    if got is None or exp is None:
        return got is None and exp is None
    if isinstance(exp, bool) or isinstance(got, bool):
        return bool(got) == bool(exp)
    try:
        return abs(float(got) - float(exp)) < 0.051
    except (TypeError, ValueError):
        return str(got) == str(exp)


def evaluate() -> list[dict]:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    out = []
    try:
        for c in cases:
            ans = chat.ask(c["q"], c["lang"])
            problems = []
            if ans["intent"] != c["intent"]:
                problems.append(f"intent {ans['intent']} != {c['intent']}")
            for x in c["expect"]:
                r = con.execute(x["sql"]).fetchone()
                exp, got = (r[0] if r else None), _get(ans["facts"], x["fact"])
                if not _same(got, exp):
                    problems.append(f"{x['fact']}: {got!r} != {exp!r}")
            if c["intent"] and not (ans.get("data_date") and ans.get("sources")):
                problems.append("no data date / source")
            out.append({"q": c["q"], "lang": c["lang"], "ok": not problems, "problems": problems})
    finally:
        con.close()
    return out


def check() -> list[tuple[str, bool, str]]:
    res = evaluate()
    ok = sum(r["ok"] for r in res)
    bad = [f"{r['q'][:50]} ({'; '.join(r['problems'])})" for r in res if not r["ok"]]
    return [("Chatbot golden (basic mode): >= 90% of dw/eval/chat_cases.json", ok >= 0.9 * len(res) and len(res) >= 30,
             f"{ok}/{len(res)} correct" + (" | wrong: " + " | ".join(bad) if bad else ""))]


def cli() -> int:
    res = evaluate()
    for r in res:
        print(("  OK    " if r["ok"] else "  WRONG ") + f"[{r['lang']}] {r['q']}" + ("" if r["ok"] else "  -> " + "; ".join(r["problems"])))
    ok = sum(r["ok"] for r in res)
    print(f"{ok}/{len(res)} correct ({100 * ok / len(res):.0f}%)")
    return 0 if ok >= 0.9 * len(res) else 1
