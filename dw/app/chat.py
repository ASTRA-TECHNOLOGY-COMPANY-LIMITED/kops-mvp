"""Chatbot over the data warehouse, basic mode (F-04): offline, no API key.

Pipeline: entities (style / file no / alias through dim.style_alias, season, customer, factory, week / month, gender,
item, metric) -> intent (keyword rules in VI / KO / EN, first match wins) -> fixed read-only query on the marts ->
short answer in the user's language + table + sources + data date + links. A question it does not understand gets
"I do not understand" and the closest sample questions; it never guesses.

Every answer is a dict: intent, text, facts (numbers / names used by the golden cases in dw/eval/chat_cases.json),
table {cols, rows}, sources, data_date, synthetic, links.
Questions and data are DATA: nothing in a question or in the warehouse is executed or followed as an instruction.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata

import duckdb

from kops_dw import config

INTENTS = ("style_status", "style_risk", "risk_list", "approval_missing", "daily_stale", "material_delay", "changes_most",
           "shipments_week", "not_input", "etd_passed", "factory_compare", "factory_delay", "factory_defects",
           "factory_load", "trend_size", "trend_color", "trend_item", "trend_fabric", "trend_gender", "proposals",
           "latest_email", "email_response", "synthetic", "file_latest", "recon", "questions_pending", "metric_explain")

CUSTOMERS = [("CHALLENGER", "CHALLENGER"), ("챌린저", "CHALLENGER"), ("CLGR", "CHALLENGER"), ("DHG", "DHG"),
             ("DAEHAN", "DHG"), ("8 SECONDS", "DHG"), ("8SECONDS", "DHG"), ("BPK", "DHG"), ("BEANPOLE", "DHG"),
             ("JBEE", "JBEE"), ("KOFA", "KOFA"), ("NEPA", "KOFA"), ("DKM", "DKM"), ("MIZUNO", "DKM"), ("미즈노", "DKM"),
             ("다경", "DKM")]
ITEMS = {"JK": ["áo khoác", "jacket", "자켓", "재킷"], "PT": ["quần", "pants", "팬츠", "바지"], "SK": ["váy", "skirt", "스커트"],
         "WT": ["áo nỉ", "sweat", "맨투맨"], "LT": ["áo thun dài", "long sleeve", "긴팔"], "ST": ["áo thun ngắn", "short sleeve", "반팔"],
         "VT": ["áo gile", "vest", "조끼"]}
GENDER = {"W": ["nữ", "women", "woman", "여성", "여자"], "M": ["nam", "men", "남성", "남자"]}


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def _has(text: str, *words: str) -> bool:
    return any(w in text for w in words)


class Ctx:
    def __init__(self, lang: str, filters: dict | None):
        self.lang = lang if lang in ("vi", "ko") else "vi"
        self.filters = filters or {}
        self.con = duckdb.connect(str(config.DB_PATH), read_only=True)
        idx = config.BUILD_DIR / "data" / "mgr" / "index.json"
        meta = json.loads(idx.read_text(encoding="utf-8")) if idx.is_file() else {}
        self.today = meta.get("today")
        self.current = meta.get("current")

    def t(self, vi: str, ko: str, **kw) -> str:
        s = ko if self.lang == "ko" else vi
        return s.format(**kw) if kw else s

    def q(self, sql: str, params=()) -> list[tuple]:
        return self.con.execute(sql, params).fetchall()

    def one(self, sql: str, params=()):
        r = self.q(sql, params)
        return r[0] if r else None


def nf(v) -> str:
    if v is None:
        return "–"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.1f}"
    return f"{int(v):,}"


def pct(a, b):
    return round(100.0 * a / b, 1) if a is not None and b else None


# ---------------------------------------------------------------------------------------------------------- entities
def extract(ctx: Ctx, question: str) -> dict:
    up, low = question.upper(), question.lower()
    e: dict = {"styles": [], "season": None, "half": None, "customer": None, "factory": None, "week": None, "month": None,
               "gender": None, "item": None}
    for tok in dict.fromkeys(re.findall(r"[A-Z0-9][A-Z0-9-]{4,}", up)):
        if re.fullmatch(r"\d{2}(SS|FW)", tok) or tok.isdigit():
            continue
        rows = ctx.q("""SELECT DISTINCT s.style_nk, s.style_no, s.season, a.kind FROM dim.style_alias a JOIN dim.style s USING (style_key)
                        WHERE a.alias_code = ? AND NOT a.ambiguous ORDER BY a.kind = 'STYLE' DESC""", (tok,))
        if rows:
            e["styles"].append({"token": tok, "nk": rows[0][0], "style_no": rows[0][1], "season": rows[0][2]})
        elif re.fullmatch(r"[MWU]?(JK|PT|SK|WT|LT|ST|VT|HP|IT|OP|MK|HC)", tok):
            pass
    m = re.search(r"\b(\d{2})\s*(SS|FW|S/S|F/W)\b", up)
    fw, ss = bool(re.search(r"(?<![0-9A-Z])F/?W\b", up)), bool(re.search(r"(?<![0-9A-Z])S/?S\b", up))
    if m:
        e["season"] = m.group(1) + m.group(2).replace("/", "")
    elif fw != ss:                    # "mùa FW" alone; "mùa FW, mùa SS" compares both halves
        e["half"] = "FW" if fw else "SS"
    for k, c in CUSTOMERS:
        if k in up:
            e["customer"] = c
            break
    facs = [r[0] for r in ctx.q("SELECT factory_code FROM dim.factory")]
    for f in sorted(facs, key=len, reverse=True):
        if re.search(r"(?<![A-Z])" + re.escape(f) + r"(?![A-Z])", up):
            e["factory"] = f
            break
    if not e["factory"]:
        for alias, f in ctx.q("SELECT alias_key, factory_code FROM stg.factory_alias WHERE length(alias_key) >= 3"):
            if re.search(r"(?<![A-Z])" + re.escape(alias) + r"(?![A-Z])", up):
                e["factory"] = f
                break
    pl = _plain(question)
    if _has(pl, "tuan nay", "this week") or "이번 주" in question:
        e["week"] = 0
    elif _has(pl, "tuan sau", "tuan toi", "next week") or "다음 주" in question:
        e["week"] = 1
    m = re.search(r"th[aá]ng\s*(\d{1,2})|(\d{1,2})\s*월", low)
    if m:
        e["month"] = int(m.group(1) or m.group(2))
    m = re.search(r"\b([MWU])(JK|PT|SK|WT|LT|ST|VT|HP)\b", up)
    if m:
        e["gender"], e["item"] = m.group(1), m.group(2)
    for code, words in ITEMS.items():
        if not e["item"] and any(w in low for w in words):
            e["item"] = code
    for code, words in GENDER.items():
        if not e["gender"] and any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", low) for w in words):
            e["gender"] = code
    return e


# ------------------------------------------------------------------------------------------------------------ intent
def classify(question: str, e: dict) -> str | None:
    low, pl = question.lower(), _plain(question)
    has_style = bool(e["styles"])
    if _has(low, "giả định", "가정", "synthetic"):
        return "synthetic"
    if _has(low, "câu hỏi", "질문") and _has(low, "klmas", "chờ", "대기", "답변"):
        return "questions_pending"
    if _has(low, "là gì", "tính thế nào", "định nghĩa", "nghĩa là", "정의", "의미", "어떻게 계산"):
        return "metric_explain"
    if _has(low, "file", "파일") and _has(low, "mới nhất", "bản nào", "최신", "latest"):
        return "file_latest"
    if _has(low, "lệch số", "chênh lệch", "불일치", "차이가"):
        return "recon"
    if has_style and _has(low, "email", "mail", "메일") and _has(low, "gần nhất", "nói gì", "최근", "latest"):
        return "latest_email"
    if _has(low, "trả lời email", "phản hồi email", "응답", "회신") or (_has(low, "trả lời") and _has(low, "bao lâu")):
        return "email_response"
    if _has(low, "đề xuất", "chờ duyệt", "yêu cầu thay đổi", "승인 대기", "변경 요청"):
        return "proposals"
    if _has(low, "đổi nhà máy", "đổi số lượng", "nhiều lần nhất", "공장 변경", "수량 변경"):
        return "changes_most"
    if has_style and _has(low, "rủi ro", "risk", "위험", "리스크", "kịp rdd", "khi nào", "언제", "맞출"):
        return "style_risk"
    if _has(low, "fpp", "cfmd", "duyệt", "định mức", "승인"):
        return "approval_missing"
    if _has(low, "báo cáo ngày", "일일 보고", "daily report"):
        return "daily_stale"
    if _has(low, "vật tư", "자재", "material"):
        return "material_delay"
    if _has(low, "chất liệu", "vải", "fabric", "원단", "소재"):
        return "trend_fabric"
    if _has(low, "size", "사이즈", "assort"):
        return "trend_size"
    if _has(low, "màu", "color", "colour", "컬러", "색상"):
        return "trend_color"
    if _has(low, "nam / nữ", "nam/nữ", "giới tính", "남녀", "성별", "hàng nam"):
        return "trend_gender"
    if _has(low, "item", "아이템", "품목", "tăng mạnh"):
        return "trend_item"
    if has_style:
        return "style_status"
    if _has(low, "lô", "선적", "출고", "lots") and (e["week"] is not None or _has(low, "tuần", "주")):
        return "shipments_week"
    if _has(low, "chưa vào chuyền", "chưa cắt", "재단 안", "투입 안", "chưa may", "아직 재단"):
        return "not_input"
    if _has(low, "qua etd", "quá etd", "chưa xuất đủ", "etd 경과", "etd가 지난", "etd가 지났"):
        return "etd_passed"
    if e["factory"]:
        if _has(low, "mã lỗi", "lỗi", "불량"):
            return "factory_defects"
        return "factory_delay"
    if _has(low, "so sánh", "비교") and _has(low, "nhà máy", "공장"):
        return "factory_compare"
    if _has(low, "nhận nhiều", "nhiều sl", "tải", "부하", "물량"):
        return "factory_load"
    if _has(low, "bal âm", "rủi ro", "trễ rdd", "dự báo trễ", "위험", "지연"):
        return "risk_list"
    return None


# --------------------------------------------------------------------------------------------------------- answers
def _season(ctx: Ctx, e: dict) -> str:
    return e["season"] or ctx.filters.get("season") or ctx.current or "27SS"


def _cust_sql(e: dict, col: str = "customer") -> tuple[str, tuple]:
    return (f" AND {col} = ?", (e["customer"],)) if e["customer"] else ("", ())


def question_lower(e: dict) -> str:
    return e.get("_q", "").lower()


def _answer(ctx, intent, text, facts=None, table=None, sources=None, links=None, synthetic=False) -> dict:
    return {"intent": intent, "text": text, "facts": facts or {}, "table": table, "sources": sources or [],
            "data_date": ctx.today, "synthetic": synthetic, "links": links or []}


STAGE = {"vi": {"SHIPPED": "đã xuất đủ", "SHIPPING": "đang xuất", "INSPECTED": "đã kiểm, chờ xuất", "SEWING": "đang may",
                "CUT_PLANNED": "chờ cắt (đã có kế hoạch)", "NOT_STARTED": "chưa vào sản xuất"},
         "ko": {"SHIPPED": "선적 완료", "SHIPPING": "선적 중", "INSPECTED": "검품 완료, 선적 대기", "SEWING": "봉제 중",
                "CUT_PLANNED": "재단 대기 (계획 있음)", "NOT_STARTED": "생산 전"}}


def _style_row(ctx, nk):
    cols = ["style_nk", "customer", "brand", "season", "style_no", "factory_code", "order_qty", "shipped", "output_qty", "out_syn",
            "ship_syn", "passed", "inspected", "cut_plan", "finish_plan", "ready_date", "etd", "rdd", "risk_reason",
            "first_lot_etd", "delay_days", "plan_bal", "pending_proposals"]
    r = ctx.one(f"SELECT {', '.join(cols)} FROM mart.mgr_style WHERE style_nk = ?", (nk,))
    return dict(zip(cols, r)) if r else None


def _stage(s) -> str:
    tol = 1 - config.RULES["qty_tolerance_pct"] / 100.0
    if s["shipped"] and s["order_qty"] and s["shipped"] >= s["order_qty"] * tol:
        return "SHIPPED"
    if s["shipped"]:
        return "SHIPPING"
    if s["passed"] or s["inspected"]:
        return "INSPECTED"
    if s["output_qty"]:
        return "SEWING"
    if s["cut_plan"]:
        return "CUT_PLANNED"
    return "NOT_STARTED"


def _multi(fn):
    """Answer every style named in the question (up to 5), e.g. 'LEV-27002 / BI7139UE1'."""
    def run(ctx, e):
        if len(e["styles"]) <= 1:
            return fn(ctx, e)
        parts = [fn(ctx, {**e, "styles": [s]}) for s in e["styles"][:5]]
        out = parts[0]
        out["text"] = "\n".join(p["text"] for p in parts)
        out["facts"] = {"styles": [p["facts"] for p in parts], **parts[0]["facts"]}
        out["links"] = [lk for p in parts for lk in p["links"]]
        out["synthetic"] = any(p["synthetic"] for p in parts)
        return out
    return run


def a_style_status(ctx, e):
    st = e["styles"][0]
    s = _style_row(ctx, st["nk"])
    if not s:
        return _answer(ctx, "style_status", ctx.t("Không thấy style {x} trong ORDER RECAP hiện hành.", "현행 ORDER RECAP에 {x} 스타일이 없습니다.", x=st["token"]))
    stage = _stage(s)
    syn = bool(s["out_syn"] or s["ship_syn"])
    text = ctx.t("{st} ({c} {se}, nhà máy {f}): {stage}. Đặt {o} pcs, đã may {out}, đã xuất {sh} pcs ({p}%). ETD {etd}, RDD {rdd}.",
                 "{st} ({c} {se}, 공장 {f}): {stage}. 오더 {o} pcs, 봉제 {out}, 선적 {sh} pcs ({p}%). ETD {etd}, RDD {rdd}.",
                 st=s["style_no"], c=s["customer"], se=s["season"], f=s["factory_code"] or "?", stage=STAGE[ctx.lang][stage],
                 o=nf(s["order_qty"]), out=nf(s["output_qty"]), sh=nf(s["shipped"] or 0), p=nf(pct(s["shipped"] or 0, s["order_qty"])),
                 etd=s["etd"] or "–", rdd=s["rdd"] or "–")
    if st["token"] != s["style_no"]:
        text = ctx.t("{t} là mã của style {s}. ", "{t}는 {s} 스타일의 코드입니다. ", t=st["token"], s=s["style_no"]) + text
    return _answer(ctx, "style_status", text,
                   {"style_no": s["style_no"], "order_qty": s["order_qty"], "shipped": s["shipped"] or 0, "output_qty": s["output_qty"],
                    "stage": stage, "shipped_pct": pct(s["shipped"] or 0, s["order_qty"])},
                   sources=["mart.mgr_style", "ORDER RECAP", "Shipment Status", "DAILY PRODUCTION REPORT / Production Status"],
                   links=[{"tab": "style", "style": s["style_nk"], "label": s["style_no"]}], synthetic=syn)


def a_style_risk(ctx, e):
    st = e["styles"][0]
    s = _style_row(ctx, st["nk"])
    if not s:
        return a_style_status(ctx, e)
    acts = ctx.q("SELECT action_type, txt, d1, d2, n1, source FROM mart.mgr_action WHERE style_nk = ? ORDER BY severity", (s["style_nk"],))
    labels = {"PLAN_LATE": ctx.t("kế hoạch trễ", "계획 지연"), "FORECAST_LATE": ctx.t("dự báo trễ", "예측 지연"),
              "APPROVAL_MISSING": ctx.t("thiếu duyệt mẫu trước ngày cắt", "재단 전 샘플 승인 누락"), "MATERIAL_LATE": ctx.t("vật tư về trễ", "자재 입고 지연"),
              "PROPOSAL_PENDING": ctx.t("đề xuất email chờ duyệt", "승인 대기 이메일 요청"), "FILE_MISMATCH": ctx.t("lệch số giữa file", "파일 간 차이")}
    transit = config.RULES["rdd_offset_days"] + config.RULES["ready_buffer_days"]
    ok = None
    if s["finish_plan"] and s["rdd"]:
        ok = (s["finish_plan"] + dt.timedelta(days=transit)) <= s["rdd"]
    reasons = sorted({labels.get(a[0], a[0]) for a in acts if a[0] != "PROPOSAL_PENDING"})
    text = ctx.t("{st}: cắt {cut}, xong theo kế hoạch {fin}, ETD {etd}, RDD {rdd}. ", "{st}: 재단 {cut}, 계획 완료 {fin}, ETD {etd}, RDD {rdd}. ",
                 st=s["style_no"], cut=s["cut_plan"] or "–", fin=s["finish_plan"] or "–", etd=s["etd"] or "–", rdd=s["rdd"] or "–")
    if ok is not None:
        text += ctx.t("Xong + {d} ngày hoàn thiện và vận chuyển {v} RDD. ", "완료 + 마무리·운송 {d}일이면 RDD에 {v}. ", d=transit,
                      v=ctx.t("kịp", "맞춤") if ok else ctx.t("KHÔNG kịp", "늦음"))
    text += (ctx.t("Rủi ro: {r}.", "위험: {r}.", r=", ".join(reasons)) if reasons else ctx.t("Không có cảnh báo rủi ro.", "위험 경고 없음."))
    return _answer(ctx, "style_risk", text, {"style_no": s["style_no"], "n_risks": len(reasons), "risks": reasons, "rdd_ok": ok,
                                             "cut_plan": str(s["cut_plan"]) if s["cut_plan"] else None},
                   table={"cols": ["action", "detail", "source"], "rows": [[labels.get(a[0], a[0]), a[1], a[5]] for a in acts]},
                   sources=["mart.mgr_action", "PRODUCTION PLAN", "ORDER RECAP"], links=[{"tab": "style", "style": s["style_nk"], "label": s["style_no"]}])


def _actions(ctx, e, types, extra=""):
    se = e["season"] or ctx.filters.get("season")
    w, p = _cust_sql(e)
    sql = f"SELECT style_no, customer, factory_code, action_type, txt, d1, d2, n1, due_date, source, style_nk FROM mart.mgr_action WHERE action_type IN ({','.join('?' * len(types))}){w}"
    params = (*types, *p)
    if se:
        sql += " AND season = ?"
        params += (se,)
    return ctx.q(sql + extra + " ORDER BY severity, due_date", params), se


def a_risk_list(ctx, e):
    rows, se = _actions(ctx, e, ("PLAN_LATE", "FORECAST_LATE"))
    styles = sorted({r[0] for r in rows if r[0]})
    text = ctx.t("{n} style có BAL âm hoặc dự báo / kế hoạch trễ RDD{s}.", "BAL 음수 또는 RDD 지연 예상 스타일 {n}개{s}.",
                 n=len(styles), s=f" ({se})" if se else "")
    if styles:
        text += " " + ", ".join(styles[:10]) + ("…" if len(styles) > 10 else "")
    return _answer(ctx, "risk_list", text, {"count": len(styles), "first": styles[0] if styles else None},
                   table={"cols": ["style", "customer", "factory", "type", "detail"], "rows": [[r[0], r[1], r[2], r[3], r[4]] for r in rows[:50]]},
                   sources=["mart.mgr_action", "PRODUCTION PLAN", "DAILY PRODUCTION REPORT"], links=[{"tab": "actions", "label": "actions"}])


def a_approval(ctx, e):
    rows, se = _actions(ctx, e, ("APPROVAL_MISSING",))
    text = ctx.t("{n} style sắp cắt mà chưa thấy FPP CFMD / DM duyệt trong email hoặc tài liệu{s}: {l}.",
                 "재단 임박인데 FPP CFMD / DM 승인이 이메일·문서에 없는 스타일 {n}개{s}: {l}.",
                 n=len(rows), s=f" ({se})" if se else "", l=", ".join(f"{r[0]} ({ctx.t('cắt', '재단')} {r[5]})" for r in rows[:10]) or "–")
    return _answer(ctx, "approval_missing", text, {"count": len(rows)},
                   table={"cols": ["style", "factory", "cut", "missing"], "rows": [[r[0], r[2], r[5], r[4]] for r in rows]},
                   sources=["mart.mgr_action", "PRODUCTION PLAN", "fact.milestone (email)"], links=[{"tab": "actions", "label": "actions"}])


def a_daily_stale(ctx, e):
    rows, se = _actions(ctx, e, ("DAILY_STALE",))
    facs = sorted({r[2] for r in rows})
    text = ctx.t("{n} nhà máy có style đang may mà quá {d} ngày làm việc chưa gửi báo cáo ngày{s}: {l}.",
                 "봉제 중인데 근무일 {d}일 넘게 일일 보고가 없는 공장 {n}곳{s}: {l}.", n=len(facs), d=config.RULES["stale_weekdays"],
                 s=f" ({se})" if se else "", l=", ".join(f"{r[2]} ({r[1]}, {ctx.t('cuối', '마지막')} {r[5] or '–'})" for r in rows) or "–")
    return _answer(ctx, "daily_stale", text, {"count": len(facs), "factories": facs},
                   table={"cols": ["factory", "customer", "last report", "weekdays"], "rows": [[r[2], r[1], r[5], r[7]] for r in rows]},
                   sources=["mart.mgr_action", "DAILY PRODUCTION REPORT"], links=[{"tab": "health", "label": "health"}])


def a_material(ctx, e):
    rows = ctx.q("SELECT factory, customer, shipments, delayed, avg_delay_days, max_delay_days, last_etd FROM mart.material_delay ORDER BY delayed DESC")
    late, _ = _actions(ctx, e, ("MATERIAL_LATE",))
    tot, dl = sum(r[2] for r in rows), sum(r[3] for r in rows)
    text = ctx.t("{d} / {t} lô vật tư về nhà máy bị dời ETD (theo tiêu đề email). Lô về sau ngày cắt kế hoạch: {m}.",
                 "공장 입고 자재 {t}건 중 {d}건 ETD 연기 (이메일 제목 기준). 재단 계획일 이후 입고: {m}건.", d=dl, t=tot, m=len(late))
    return _answer(ctx, "material_delay", text, {"delayed": dl, "lots": tot, "after_cut": len(late)},
                   table={"cols": ["factory", "customer", "lots", "delayed", "avg days", "max days", "last ETD"], "rows": rows},
                   sources=["mart.material_delay", "email (subject)"], links=[{"tab": "ship", "label": "ship"}])


def a_changes(ctx, e):
    se = _season(ctx, e) if e["season"] else None
    w, p = _cust_sql(e, "s.customer")
    sql = f"""SELECT s.style_no, s.customer, count(*) FILTER (WHERE c.change_type IN ('FACTORY_MOVE', 'VERSION_FACTORY')) AS fac,
              count(*) FILTER (WHERE c.change_type IN ('QTY_NOTE', 'VERSION_QTY', 'EMAIL_QTY_PCT')) AS qty, count(*) AS n
              FROM fact.change c JOIN dim.style s USING (style_key) WHERE c.change_type <> 'FACTORY_FIXED'{w}
              {'AND s.season = ?' if se else ''} GROUP BY 1, 2 ORDER BY fac + qty DESC, n DESC LIMIT 10"""
    rows = ctx.q(sql, (*p, *((se,) if se else ())))
    if not rows:
        return _answer(ctx, "changes_most", ctx.t("Không có thay đổi nào.", "변경 내역이 없습니다."), {"top": None})
    r = rows[0]
    text = ctx.t("Style đổi nhiều nhất: {s} ({c}) — {f} lần đổi nhà máy, {q} lần đổi số lượng.", "가장 많이 변경된 스타일: {s} ({c}) — 공장 변경 {f}회, 수량 변경 {q}회.",
                 s=r[0], c=r[1], f=r[2], q=r[3])
    return _answer(ctx, "changes_most", text, {"top": r[0], "factory_changes": r[2], "qty_changes": r[3]},
                   table={"cols": ["style", "customer", "factory", "qty", "all"], "rows": rows},
                   sources=["fact.change", "ORDER RECAP (notes, versions)", "email"], links=[{"tab": "change", "label": "change"}])


def _week_range(ctx, k: int):
    today = dt.date.fromisoformat(ctx.today) if ctx.today else dt.date.today()
    start = today - dt.timedelta(days=today.weekday()) + dt.timedelta(weeks=k)
    return start, start + dt.timedelta(days=6)


def a_shipments_week(ctx, e):
    k = e["week"] if e["week"] is not None else 0
    a, b = _week_range(ctx, k)
    w, p = _cust_sql(e, "s.customer")
    rows = ctx.q(f"""SELECT s.style_no, s.customer, s.factory_code, l.lot_label, l.lot_etd, l.ship_mode, l.qty FROM fact.shipment_lot l
                     JOIN dim.style s USING (style_key) WHERE l.lot_etd BETWEEN ? AND ?{w} ORDER BY l.lot_etd""", (a, b, *p))
    plan = ctx.q(f"""SELECT style_no, customer, factory_code, etd, order_qty FROM mart.mgr_style WHERE etd BETWEEN ? AND ? AND is_active
                     AND NOT style_syn{w.replace('s.customer', 'customer')} ORDER BY etd""", (a, b, *p))
    facs = sorted({r[2] for r in rows if r[2]} | {r[2] for r in plan if r[2]})
    text = ctx.t("Tuần {a} – {b}: {n} lô đã có trong Shipment Status ({q} pcs); {m} style có ETD VN trong tuần ({pq} pcs). Nhà máy: {f}.",
                 "{a} – {b} 주: Shipment Status 선적 {n}건 ({q} pcs); ETD VN이 이번 주인 스타일 {m}개 ({pq} pcs). 공장: {f}.",
                 a=a, b=b, n=len(rows), q=nf(sum(r[6] or 0 for r in rows)), m=len(plan), pq=nf(sum(r[4] or 0 for r in plan)), f=", ".join(facs) or "–")
    return _answer(ctx, "shipments_week", text, {"lots": len(rows), "styles_etd": len(plan), "week_start": str(a)},
                   table={"cols": ["style", "customer", "factory", "ETD", "qty"], "rows": [[r[0], r[1], r[2], r[3], r[4]] for r in plan]},
                   sources=["fact.shipment_lot (Shipment Status)", "ORDER RECAP (ETD VN)"], links=[{"tab": "ship", "label": "ship"}])


def a_not_input(ctx, e):
    se = _season(ctx, e)
    w, p = _cust_sql(e)
    rows = ctx.q(f"""SELECT style_no, customer, factory_code, order_qty, cut_plan FROM mart.mgr_style WHERE season = ? AND is_active
                     AND NOT style_syn AND coalesce(output_qty, 0) = 0 AND coalesce(shipped, 0) = 0{w} ORDER BY cut_plan NULLS LAST""", (se, *p))
    qty = sum(r[3] or 0 for r in rows)
    text = ctx.t("{c}{se}: {n} style ({q} pcs) chưa có sản lượng may hay lô xuất nào; {k} style đã có ngày cắt kế hoạch.",
                 "{c}{se}: 봉제 실적·선적이 없는 스타일 {n}개 ({q} pcs); 그중 재단 계획일이 있는 스타일 {k}개.",
                 c=(e["customer"] + " ") if e["customer"] else "", se=se, n=len(rows), q=nf(qty), k=sum(1 for r in rows if r[4]))
    return _answer(ctx, "not_input", text, {"styles": len(rows), "qty": qty},
                   table={"cols": ["style", "customer", "factory", "qty", "cut plan"], "rows": rows[:100]},
                   sources=["mart.mgr_style", "DAILY PRODUCTION REPORT", "PRODUCTION PLAN"], links=[{"tab": "production", "label": "production"}])


def a_etd_passed(ctx, e):
    se = e["season"]
    w, p = _cust_sql(e)
    rows = ctx.q(f"""SELECT style_no, customer, factory_code, etd, order_qty, shipped FROM mart.mgr_style
                     WHERE risk_reason = 'ETD_PASSED_NOT_SHIPPED' AND NOT style_syn{w}{' AND season = ?' if se else ''} ORDER BY etd""",
                 (*p, *((se,) if se else ())))
    text = ctx.t("{n} style đã qua ETD VN mà chưa xuất đủ: {l}.", "ETD VN이 지났는데 선적이 끝나지 않은 스타일 {n}개: {l}.",
                 n=len(rows), l=", ".join(f"{r[0]} ({r[2]}, ETD {r[3]}, {nf(r[5] or 0)}/{nf(r[4])})" for r in rows[:10]) or "–")
    return _answer(ctx, "etd_passed", text, {"count": len(rows)}, table={"cols": ["style", "customer", "factory", "ETD", "order", "shipped"], "rows": rows},
                   sources=["mart.mgr_style", "ORDER RECAP", "Shipment Status"], links=[{"tab": "actions", "label": "actions"}])


def _factory_rows(ctx, se, customer=None):
    w, p = (" AND customer = ?", (customer,)) if customer else ("", ())
    return ctx.q(f"""SELECT factory_code, sum(styles), sum(qty), sum(lots_real), sum(on_time_real), sum(insp_real), sum(def_real)
                     FROM mart.mgr_factory WHERE season = ?{w} GROUP BY 1 ORDER BY 1""", (se, *p))


def a_factory_compare(ctx, e):
    se = _season(ctx, e) if e["season"] else "26FW"
    rows = _factory_rows(ctx, se, e["customer"])
    tab = [[r[0], r[1], r[2], pct(r[4], r[3]), pct(r[6], r[5]), r[3]] for r in rows]
    judged = [t for t in tab if t[3] is not None]
    best = max(judged, key=lambda t: (t[3], t[5])) if judged else None          # tie: more lots judged
    tab = [t[:5] for t in tab]
    worst = max((t for t in tab if t[4] is not None), key=lambda t: t[4], default=None)
    text = ctx.t("{se}: đúng hạn (lô đầu ≤ ETD VN) cao nhất {b} {bp}%; tỉ lệ lỗi cao nhất {w} {wp}% (điểm lỗi ÷ SL kiểm, Q24). Chỉ dữ liệu thật.",
                 "{se}: 납기 준수율(첫 선적 ≤ ETD VN) 최고 {b} {bp}%; 불량률 최고 {w} {wp}% (불량 포인트 ÷ 검품 수량, Q24). 실제 데이터만.",
                 se=se, b=best[0] if best else "–", bp=nf(best[3]) if best else "–", w=worst[0] if worst else "–", wp=nf(worst[4]) if worst else "–")
    return _answer(ctx, "factory_compare", text, {"best_on_time": best[0] if best else None, "worst_defects": worst[0] if worst else None},
                   table={"cols": ["factory", "styles", "qty", "on-time %", "defect %"], "rows": tab},
                   sources=["mart.mgr_factory", "Shipment Status", "ORDER RECAP", "KLMAS INSPECTION REPORT"], links=[{"tab": "factory", "label": "factory"}])


def a_factory_delay(ctx, e):
    f = e["factory"]
    se = e["season"]
    rows = ctx.q(f"""SELECT style_no, season, etd, first_lot_etd, delay_days FROM mart.mgr_style WHERE factory_code = ? AND delay_days IS NOT NULL
                     AND NOT ship_syn AND NOT style_syn{' AND season = ?' if se else ''} ORDER BY delay_days DESC""", (f, *((se,) if se else ())))
    if not rows:
        return _answer(ctx, "factory_delay", ctx.t("{f}: chưa có lô xuất thật để tính trễ.", "{f}: 지연을 계산할 실제 선적이 없습니다.", f=f), {"factory": f, "avg_delay": None})
    avg = round(sum(r[4] for r in rows) / len(rows), 1)
    text = ctx.t("{f}: trễ ETD trung bình {a} ngày trên {n} style đã xuất (lô đầu − ETD VN); trễ nhất {s} {d} ngày.",
                 "{f}: 선적된 스타일 {n}개 평균 ETD 지연 {a}일 (첫 선적 − ETD VN); 가장 늦은 스타일 {s} {d}일.", f=f, a=avg, n=len(rows), s=rows[0][0], d=rows[0][4])
    return _answer(ctx, "factory_delay", text, {"factory": f, "avg_delay": avg, "worst": rows[0][0], "n": len(rows)},
                   table={"cols": ["style", "season", "ETD VN", "first lot", "days"], "rows": rows[:30]},
                   sources=["mart.mgr_style", "Shipment Status", "ORDER RECAP"], links=[{"tab": "factory", "label": f}])


def a_factory_defects(ctx, e):
    f = e["factory"]
    rows = ctx.q("""SELECT d.code, any_value(d.name_ko), sum(d.minor + d.major) AS pts FROM core.qc_defect d
                    JOIN core.qc_inspection q ON q.file_id = d.file_id AND q.row_no = d.row_no WHERE q.factory_code = ? GROUP BY 1 ORDER BY pts DESC LIMIT 5""", (f,))
    trend = ctx.q("""SELECT strftime(month, '%Y-%m'), sum(defects), sum(inspected) FROM mart.mgr_quality WHERE factory_code = ? AND NOT is_synthetic
                     GROUP BY 1 ORDER BY 1""", (f,))
    tr = ", ".join(f"{m} {nf(pct(d, i))}%" for m, d, i in trend if i) or "–"
    if not rows:
        text = ctx.t("{f}: không có mã lỗi trong dữ liệu kiểm bên thứ ba (bảng kiểm KLMAS chỉ có tổng lỗi). Tỉ lệ lỗi theo tháng: {t}.",
                     "{f}: 제3자 검품 데이터에 불량 코드가 없습니다 (KLMAS 검품표는 불량 합계만). 월별 불량률: {t}.", f=f, t=tr) + ctx.t(" (điểm lỗi ÷ SL kiểm, Q24: một sản phẩm có thể nhiều điểm lỗi nên có thể > 100%).",
                                                     " (불량 포인트 ÷ 검품 수량, Q24: 한 제품에 불량이 여러 개일 수 있어 100%를 넘을 수 있음).")
        return _answer(ctx, "factory_defects", text, {"factory": f, "top_code": None},
                       table={"cols": ["month", "defects", "inspected"], "rows": trend}, sources=["mart.mgr_quality", "KLMAS INSPECTION REPORT"],
                       links=[{"tab": "quality", "label": f}])
    text = ctx.t("{f}: top mã lỗi (kiểm bên thứ ba, INPUT DATA): {l}. Tỉ lệ lỗi theo tháng: {t}.", "{f}: 상위 불량 코드 (제3자 검품, INPUT DATA): {l}. 월별 불량률: {t}.",
                 f=f, l=", ".join(f"{r[0]} {r[1] or ''} {nf(r[2])}" for r in rows), t=tr)
    return _answer(ctx, "factory_defects", text, {"factory": f, "top_code": rows[0][0]},
                   table={"cols": ["code", "name", "points"], "rows": rows}, sources=["core.qc_defect (INPUT DATA)", "mart.mgr_quality"],
                   links=[{"tab": "quality", "label": f}])


def a_factory_load(ctx, e):
    month = e["month"] or (dt.date.fromisoformat(ctx.today).month if ctx.today else dt.date.today().month)
    rows = ctx.q("""SELECT factory_code, sum(order_qty), count(*) FROM mart.mgr_style WHERE month(etd) = ? AND is_active AND NOT style_syn
                    AND etd >= DATE '2026-01-01' GROUP BY 1 ORDER BY 2 DESC""", (month,))
    if not rows:
        return _answer(ctx, "factory_load", ctx.t("Không có style nào có ETD trong tháng {m}.", "{m}월 ETD 스타일이 없습니다.", m=month), {"top": None})
    text = ctx.t("Tháng {m} (theo ETD VN): nhà máy nhận nhiều SL nhất là {f} với {q} pcs / {n} style.", "{m}월 (ETD VN 기준): 물량이 가장 많은 공장은 {f}, {q} pcs / 스타일 {n}개.",
                 m=month, f=rows[0][0], q=nf(rows[0][1]), n=rows[0][2])
    return _answer(ctx, "factory_load", text, {"top": rows[0][0], "qty": rows[0][1], "month": month},
                   table={"cols": ["factory", "qty", "styles"], "rows": rows}, sources=["mart.mgr_style", "ORDER RECAP (ETD VN)"],
                   links=[{"tab": "factory", "label": "factory"}])


TREND_NOTE = {"vi": "Chỉ 26FW và 27SS là dữ liệu thật (25SS, 25FW là giả định, không có size / màu); size có ở CHALLENGER 26FW và MIZUNO (DKM), màu / item / vải chỉ ở CHALLENGER.",
              "ko": "실제 데이터는 26FW, 27SS뿐입니다 (25SS, 25FW는 가정 데이터, 사이즈·컬러 없음). 사이즈는 CHALLENGER 26FW와 MIZUNO(DKM), 컬러·아이템·원단은 CHALLENGER만 있습니다."}


def _seasons_for(ctx, e, table):
    if e["season"]:
        return [e["season"]]
    ss = [r[0] for r in ctx.q(f"SELECT DISTINCT season FROM {table} ORDER BY season")]
    if e["half"]:
        ss = [s for s in ss if s.endswith(e["half"])]
    return ss


def a_trend_size(ctx, e):
    if e["styles"]:
        s = e["styles"][0]
        rows = ctx.q("""SELECT upper(regexp_replace(size_code, '\\s*\\(.*$', '')), sum(ordered) FROM mart.assortment WHERE style_no = ? GROUP BY 1 ORDER BY 2 DESC""",
                     (s["style_no"],))
        if not rows:
            return _answer(ctx, "trend_size", ctx.t("Chưa có dữ liệu size của {s} (khách này chưa gửi Shipment Status có assort). ", "{s}의 사이즈 데이터가 없습니다 (고객사 Shipment Status 미수신). ",
                                                    s=s["style_no"]) + TREND_NOTE[ctx.lang], {"available": False, "style": s["style_no"]},
                           sources=["mart.assortment (Shipment Status)"], links=[{"tab": "style", "style": s["nk"], "label": s["style_no"]}])
    w, p = _cust_sql(e)
    g = (" AND gender = ?", (e["gender"],)) if e["gender"] else ("", ())
    it = (" AND item_type = ?", (e["item"],)) if e["item"] else ("", ())
    out, facts = [], {"available": True}
    for se in _seasons_for(ctx, e, "mart.trend_size"):
        rows = ctx.q(f"SELECT size_code, sum(qty) FROM mart.trend_size WHERE season = ?{w}{g[0]}{it[0]} GROUP BY 1 ORDER BY 2 DESC", (se, *p, *g[1], *it[1]))
        tot = sum(r[1] for r in rows)
        if not tot:
            continue
        out.append((se, rows, tot))
        facts.setdefault("top_size", {})[se] = rows[0][0]
        facts.setdefault("top_share", {})[se] = pct(rows[0][1], tot)
    if not out:
        return _answer(ctx, "trend_size", ctx.t("Không có dữ liệu size cho bộ lọc này. ", "이 조건의 사이즈 데이터가 없습니다. ") + TREND_NOTE[ctx.lang], {"available": False})
    text = " ".join(ctx.t("{se}: size lớn nhất {s} ({p}% của {t} pcs).", "{se}: 최다 사이즈 {s} ({t} pcs 중 {p}%).", se=se, s=r[0][0], p=nf(pct(r[0][1], t)), t=nf(t))
                    for se, r, t in out) + " " + TREND_NOTE[ctx.lang]
    rows = [[se, r[0], r[1], pct(r[1], t)] for se, rr, t in out for r in rr]
    return _answer(ctx, "trend_size", text, facts, table={"cols": ["season", "size", "qty", "%"], "rows": rows},
                   sources=["mart.trend_size", "Shipment Status (assortment)"], links=[{"tab": "trends", "label": "trends"}])


def a_trend_color(ctx, e):
    w, p = _cust_sql(e)
    out, facts = [], {}
    for se in _seasons_for(ctx, e, "mart.trend_color"):
        rows = ctx.q(f"SELECT color, sum(qty) FROM mart.trend_color WHERE season = ?{w} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", (se, *p))
        if rows:
            out.append((se, rows))
            facts.setdefault("top_color", {})[se] = rows[0][0]
    if not out:
        return _answer(ctx, "trend_color", ctx.t("Không có dữ liệu màu. ", "컬러 데이터가 없습니다. ") + TREND_NOTE[ctx.lang], {})
    text = " ".join(ctx.t("{se}: top màu {l}.", "{se}: 상위 컬러 {l}.", se=se, l=", ".join(f"{c} {nf(q)}" for c, q in r)) for se, r in out) + " " + TREND_NOTE[ctx.lang]
    return _answer(ctx, "trend_color", text, facts, table={"cols": ["season", "color", "qty"], "rows": [[se, c, q] for se, r in out for c, q in r]},
                   sources=["mart.trend_color", "ORDER RECAP"], links=[{"tab": "trends", "label": "trends"}])


ITEM_NAME = {"vi": {"JK": "áo khoác", "PT": "quần dài", "SK": "váy", "WT": "áo nỉ", "LT": "áo thun dài tay", "ST": "áo thun ngắn tay",
                     "VT": "áo gile", "HP": "quần short", "IT": "áo trong", "OP": "đầm", "MK": "khẩu trang", "HC": "mũ", "GW": "găng tay"},
             "ko": {"JK": "자켓", "PT": "긴 바지", "SK": "스커트", "WT": "맨투맨", "LT": "긴팔 티", "ST": "반팔 티", "VT": "조끼", "HP": "반바지",
                    "IT": "이너", "OP": "원피스", "MK": "마스크", "HC": "모자", "GW": "장갑"}}


def item_label(ctx, code: str) -> str:
    g, i = code[:1], code[1:]
    gn = {"W": ctx.t("nữ", "여성"), "M": ctx.t("nam", "남성"), "U": ctx.t("unisex", "공용")}.get(g, "")
    return f"{code} ({ITEM_NAME[ctx.lang].get(i, i)} {gn})"


def a_trend_item(ctx, e):
    rows = ctx.q("""SELECT coalesce(gender, '?') || coalesce(item_type, '?'), sum(qty) FILTER (WHERE season = '26FW'), sum(qty) FILTER (WHERE season = '27SS')
                    FROM mart.trend_item GROUP BY 1""")
    rows = [(i, a or 0, b or 0, (b or 0) - (a or 0)) for i, a, b in rows]
    rows.sort(key=lambda r: r[3], reverse=True)
    top = rows[0] if rows else None
    text = ctx.t("Item tăng mạnh nhất 27SS so với 26FW: {i} (+{d} pcs: {a} → {b}). ", "26FW 대비 27SS에서 가장 많이 늘어난 아이템: {i} (+{d} pcs: {a} → {b}). ",
                 i=item_label(ctx, top[0]), d=nf(top[3]), a=nf(top[1]), b=nf(top[2])) + TREND_NOTE[ctx.lang] if top else TREND_NOTE[ctx.lang]
    return _answer(ctx, "trend_item", text, {"top_item": top[0] if top else None}, table={"cols": ["item", "26FW", "27SS", "change"], "rows": rows},
                   sources=["mart.trend_item", "ORDER RECAP (style code: gender + item)"], links=[{"tab": "trends", "label": "trends"}])


def a_trend_fabric(ctx, e):
    out, facts = [], {}
    for se in _seasons_for(ctx, e, "mart.trend_fabric"):
        rows = ctx.q("SELECT fabric_supplier, sum(styles), sum(qty) FROM mart.trend_fabric WHERE season = ? AND fabric_supplier <> '(?)' GROUP BY 1 ORDER BY 2 DESC LIMIT 5", (se,))
        if rows:
            out.append((se, rows))
            facts.setdefault("top_fabric", {})[se] = rows[0][0]
    text = " ".join(ctx.t("{se}: vải chính phổ biến nhất của {s} ({n} style).", "{se}: 가장 많이 쓴 메인 원단 공급처 {s} (스타일 {n}개).", se=se, s=r[0][0], n=r[0][1])
                    for se, r in out) + " " + ctx.t("File chỉ ghi nhà cung cấp + mã vải, không ghi thành phần.", "파일에는 원단 공급처와 품번만 있고 혼용률은 없습니다.") + " " + TREND_NOTE[ctx.lang]
    return _answer(ctx, "trend_fabric", text, facts, table={"cols": ["season", "supplier", "styles", "qty"], "rows": [[se, *x] for se, r in out for x in r]},
                   sources=["mart.trend_fabric", "ORDER RECAP (MAIN FABRIC)"], links=[{"tab": "trends", "label": "trends"}])


def a_trend_gender(ctx, e):
    rows = ctx.q("SELECT season, brand, gender, sum(qty) FROM mart.trend_item GROUP BY ALL ORDER BY 1, 2, 3")
    facts, parts = {}, []
    for se in sorted({r[0] for r in rows}):
        tot = sum(r[3] for r in rows if r[0] == se)
        w = sum(r[3] for r in rows if r[0] == se and r[2] == "W")
        facts.setdefault("women_share", {})[se] = pct(w, tot)
        parts.append(ctx.t("{se}: nữ {w}%, nam {m}%", "{se}: 여성 {w}%, 남성 {m}%", se=se, w=nf(pct(w, tot)),
                           m=nf(pct(sum(r[3] for r in rows if r[0] == se and r[2] == "M"), tot))))
    text = "CHALLENGER — " + "; ".join(parts) + ". " + TREND_NOTE[ctx.lang]
    return _answer(ctx, "trend_gender", text, facts, table={"cols": ["season", "brand", "gender", "qty"], "rows": rows},
                   sources=["mart.trend_item", "ORDER RECAP (style code)"], links=[{"tab": "trends", "label": "trends"}])


def a_proposals(ctx, e):
    w, p = _cust_sql(e, "s.customer")
    since = None
    if _has(question_lower(e), "tuần qua", "tuần trước", "7 ngày", "지난주", "지난 주", "last week"):
        since = (dt.date.fromisoformat(ctx.today) if ctx.today else dt.date.today()) - dt.timedelta(days=7)
    rows = ctx.q(f"""SELECT s.customer, c.change_type, count(*), min(c.fact_date), max(c.fact_date) FROM fact.change c JOIN dim.style s USING (style_key)
                     WHERE c.review_status = 'PENDING_REVIEW'{w}{' AND c.fact_date >= ?' if since else ''} GROUP BY 1, 2 ORDER BY 3 DESC""",
                 (*p, *((since,) if since else ())))
    n = sum(r[2] for r in rows)
    by = {}
    for r in rows:
        by[r[0]] = by.get(r[0], 0) + r[2]
    text = (ctx.t("Từ {d}: ", "{d} 이후: ", d=since) if since else "") + ctx.t("{n} đề xuất thay đổi từ email đang chờ duyệt ({b}); chưa áp vào ORDER RECAP hay số liệu nào.",
                 "승인 대기 중인 이메일 변경 요청 {n}건 ({b}); ORDER RECAP이나 수치에는 아직 반영되지 않았습니다.",
                 n=n, b=", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda x: -x[1])) or "–")
    return _answer(ctx, "proposals", text, {"pending": n, "by_customer": by},
                   table={"cols": ["customer", "type", "n", "first", "last"], "rows": rows}, sources=["fact.change (review_status = PENDING_REVIEW)", "email"],
                   links=[{"tab": "change", "label": "change"}])


def a_latest_email(ctx, e):
    s = e["styles"][0]
    r = ctx.one("""SELECT m.sent_at, m.subject, m.category, m.sender_email FROM bridge.email_style b JOIN fact.email m USING (msg_key)
                   JOIN dim.style st USING (style_key) WHERE st.style_nk = ? AND NOT m.is_sample ORDER BY m.sent_at DESC LIMIT 1""", (s["nk"],))
    if not r:
        return _answer(ctx, "latest_email", ctx.t("Chưa có email nào gắn với {s}.", "{s}와 연결된 이메일이 없습니다.", s=s["token"]), {"subject": None})
    text = ctx.t("Email gần nhất về {t} ({st}): {d} — \"{sub}\" (loại {c}). Nội dung chi tiết xem trong Style 360; AI đọc nội dung email (D-03) chưa bật.",
                 "{t} ({st}) 관련 최근 이메일: {d} — \"{sub}\" (유형 {c}). 자세한 내용은 Style 360에서 확인; 이메일 AI 분석(D-03)은 아직 꺼져 있습니다.",
                 t=s["token"], st=s["style_no"], d=r[0], sub=r[1], c=r[2] or "–")
    return _answer(ctx, "latest_email", text, {"subject": r[1], "sent_at": str(r[0])}, sources=["fact.email", "bridge.email_style"],
                   links=[{"tab": "style", "style": s["nk"], "label": s["style_no"]}])


def a_email_response(ctx, e):
    rows = ctx.q("""SELECT sender_party, sum(replies), sum(within_24h), median(median_reply_hours) FROM mart.mgr_email_response GROUP BY 1 ORDER BY 2 DESC""")
    k = next((r for r in rows if r[0] == "KLMAS"), None)
    text = ctx.t("KLMAS trả lời trong 24 giờ ở {p}% lần ({w}/{n} thư trả lời); trung vị theo tháng {h} giờ.",
                 "KLMAS는 회신의 {p}%를 24시간 안에 답했습니다 ({w}/{n}건); 월별 중앙값 {h}시간.",
                 p=nf(pct(k[2], k[1])) if k else "–", w=k[2] if k else 0, n=k[1] if k else 0, h=nf(k[3]) if k else "–")
    return _answer(ctx, "email_response", text, {"klmas_within24_pct": pct(k[2], k[1]) if k else None},
                   table={"cols": ["sender", "replies", "≤24h", "median h"], "rows": rows}, sources=["mart.mgr_email_response", "email"],
                   links=[{"tab": "change", "label": "change"}])


def a_synthetic(ctx, e):
    rows = ctx.q("""SELECT 'sim.style' t, count(*) FROM sim.style UNION ALL SELECT 'sim.shipment_lot', count(*) FROM sim.shipment_lot
                    UNION ALL SELECT 'sim.daily_output', count(*) FROM sim.daily_output UNION ALL SELECT 'sim.inspection', count(*) FROM sim.inspection""")
    text = ctx.t("Số giả định (nhãn \"Giả định\" trên trang, tắt bằng công tắc): mùa 25SS / 25FW (ASM-SIM-01), sản lượng ngày ở nhà máy không gửi báo cáo (ASM-SIM-02), "
                 "kết quả kiểm (ASM-SIM-03), lô xuất khách chưa gửi Shipment Status (ASM-SIM-04), mã lỗi theo Pareto (ASM-SIM-05). Định nghĩa còn chờ KLMAS: "
                 "tỉ lệ lỗi (ASM-QC-01, Q24), REJECT (ASM-QC-02, Q25), độ tươi (ASM-FRESH-01, Q32). Chi tiết: dw/docs/assumptions.md.",
                 "가정 수치(화면에 \"가정\" 표시, 스위치로 끔): 25SS / 25FW 시즌(ASM-SIM-01), 보고 없는 공장의 일일 생산량(ASM-SIM-02), 검품 결과(ASM-SIM-03), "
                 "Shipment Status 미수신 고객사 선적(ASM-SIM-04), 파레토 기반 불량 코드(ASM-SIM-05). KLMAS 확인 대기 정의: 불량률(ASM-QC-01, Q24), "
                 "REJECT(ASM-QC-02, Q25), 최신성(ASM-FRESH-01, Q32). 자세한 내용: dw/docs/assumptions.md.")
    return _answer(ctx, "synthetic", text, {"sim_rows": {r[0]: r[1] for r in rows}}, table={"cols": ["table", "rows"], "rows": rows},
                   sources=["schema sim", "dw/docs/assumptions.md"], synthetic=True, links=[{"tab": "health", "label": "health"}])


def a_file_latest(ctx, e):
    kind = "ORDER RECAP"
    w = " AND family LIKE ?" if e["customer"] else ""
    rows = ctx.q(f"""SELECT file_name, coalesce(report_date, file_date), season FROM etl.source_file WHERE is_current AND status = 'LOADED'
                     AND NOT is_sample AND file_name ILIKE '%ORDER RECAP%'{w} ORDER BY 2 DESC NULLS LAST""",
                 ((e["customer"] + "%",) if e["customer"] else ()))
    if not rows:
        return _answer(ctx, "file_latest", ctx.t("Không thấy {k} hiện hành.", "현행 {k} 파일이 없습니다.", k=kind), {"file": None})
    text = ctx.t("{k} mới nhất{c}: {f} (ngày {d}, mùa {s}).", "최신 {k}{c}: {f} (날짜 {d}, 시즌 {s}).", k=kind,
                 c=f" {e['customer']}" if e["customer"] else "", f=rows[0][0], d=rows[0][1], s=rows[0][2])
    return _answer(ctx, "file_latest", text, {"file": rows[0][0], "date": str(rows[0][1])}, table={"cols": ["file", "date", "season"], "rows": rows},
                   sources=["etl.source_file"], links=[{"tab": "health", "label": "health"}])


def a_recon(ctx, e):
    rows = ctx.q("SELECT check_name, count(*) FROM mart.mgr_recon GROUP BY 1 ORDER BY 2 DESC")
    sched = ctx.q("SELECT season, ref, detail FROM mart.mgr_recon WHERE check_name = 'SHIPPING SCHEDULE vs RECAP' ORDER BY 1, 2")
    n = sum(r[1] for r in rows)
    text = ctx.t("{n} dòng lệch số giữa các file: {l}. ORDER RECAP vs SHIPPING SCHEDULE: {s} dòng (vd. {e}).",
                 "파일 간 차이 {n}건: {l}. ORDER RECAP vs SHIPPING SCHEDULE: {s}건 (예: {e}).",
                 n=n, l=", ".join(f"{r[0]} {r[1]}" for r in rows), s=len(sched), e="; ".join(f"{r[1]} {r[2]}" for r in sched[:3]) or "–")
    return _answer(ctx, "recon", text, {"total": n, "schedule_vs_recap": len(sched)}, table={"cols": ["season", "style / file", "detail"], "rows": sched},
                   sources=["mart.mgr_recon", "SHIPPING SCHEDULE", "ORDER RECAP"], links=[{"tab": "health", "label": "health"}])


METRICS = {
    "on_time": (["đúng hạn", "on-time", "on time", "납기"], "Q21",
                "Đúng hạn = lô xuất đầu tiên có ETD ≤ ETD VN trong ORDER RECAP (số chính); số phụ cho trễ 7 ngày.",
                "납기 준수 = 첫 선적 ETD ≤ ORDER RECAP의 ETD VN (주 지표); 보조 지표는 7일 지연 허용."),
    "defect": (["tỉ lệ lỗi", "lỗi", "불량"], "Q24",
               "Tỉ lệ lỗi = điểm lỗi ÷ SL đã kiểm (bảng kiểm KLMAS dòng D ÷ C; INPUT DATA DEFECT QTY ÷ inspected).",
               "불량률 = 불량 포인트 ÷ 검품 수량 (KLMAS 검품표 D행 ÷ C행; INPUT DATA DEFECT QTY ÷ 검품 수량)."),
    "fresh": (["độ tươi", "최신성", "fresh"], "Q32",
              "Độ tươi = số ngày thứ 2–6 giữa báo cáo ngày cuối và hôm nay: ≤ 2 FRESH, 3–5 STALE, > 5 DARK.",
              "최신성 = 마지막 일일 보고와 오늘 사이의 평일 수: 2일 이하 FRESH, 3–5일 STALE, 5일 초과 DARK."),
    "risk": (["rủi ro", "위험"], "Q26",
             "Style rủi ro = còn hiệu lực, chưa xuất đủ và: ngày sẵn sàng dự báo + 12 ngày > RDD, hoặc BAL kế hoạch < 0, hoặc đã qua ETD.",
             "위험 스타일 = 유효·미선적이면서 예상 준비일 + 12일 > RDD, 또는 계획 BAL < 0, 또는 ETD 경과."),
    "bal": (["bal"], "Q16", "BAL = số ngày dư giữa ngày xong / xuất theo kế hoạch và hạn (theo quy tắc ghi trong từng file kế hoạch); âm = trễ.",
            "BAL = 계획 완료·출고일과 기한 사이의 여유 일수 (각 생산계획 파일의 규칙); 음수 = 지연."),
}


def a_metric(ctx, e, question=""):
    low = question.lower()
    for key, (words, qcode, vi, ko) in METRICS.items():
        if any(w in low for w in words):
            from .questions_bridge import title
            text = ctx.t(vi, ko) + " " + ctx.t("Chờ KLMAS xác nhận: {q}.", "KLMAS 확인 대기: {q}.", q=title(qcode))
            return _answer(ctx, "metric_explain", text, {"metric": key, "question": qcode}, sources=["dw/docs/metrics.md"])
    return _answer(ctx, "metric_explain", ctx.t("Chỉ số nào? Ví dụ: đúng hạn, tỉ lệ lỗi, độ tươi, BAL, style rủi ro.",
                                                 "어떤 지표인가요? 예: 납기 준수, 불량률, 최신성, BAL, 위험 스타일."), {"metric": None})


def a_questions(ctx, e, question=""):
    from .questions_bridge import pending_for
    rows = pending_for(question)
    text = ctx.t("Câu hỏi đang chờ KLMAS ảnh hưởng tới số liệu: {l}.", "수치에 영향을 주는 KLMAS 답변 대기 질문: {l}.", l="; ".join(f"{c}. {t}" for c, t in rows))
    return _answer(ctx, "questions_pending", text, {"codes": [c for c, _ in rows]}, table={"cols": ["code", "question"], "rows": rows},
                   sources=["analys-docs/open_questions.md", "kops_dw/questions.py"])


HANDLERS = {"style_status": _multi(a_style_status), "style_risk": _multi(a_style_risk), "risk_list": a_risk_list, "approval_missing": a_approval,
            "daily_stale": a_daily_stale, "material_delay": a_material, "changes_most": a_changes, "shipments_week": a_shipments_week,
            "not_input": a_not_input, "etd_passed": a_etd_passed, "factory_compare": a_factory_compare, "factory_delay": a_factory_delay,
            "factory_defects": a_factory_defects, "factory_load": a_factory_load, "trend_size": a_trend_size, "trend_color": a_trend_color,
            "trend_item": a_trend_item, "trend_fabric": a_trend_fabric, "trend_gender": a_trend_gender, "proposals": a_proposals,
            "latest_email": a_latest_email, "email_response": a_email_response, "synthetic": a_synthetic, "file_latest": a_file_latest,
            "recon": a_recon, "questions_pending": a_questions, "metric_explain": a_metric}


def samples() -> dict:
    p = config.DW_DIR / "eval" / "chat_samples.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def closest_samples(question: str, lang: str, n: int = 3) -> list[str]:
    words = set(re.findall(r"\w+", _plain(question)))
    pool = [q for grp in samples().get(lang, {}).values() for q in grp]
    scored = sorted(pool, key=lambda q: -len(words & set(re.findall(r"\w+", _plain(q)))))
    return scored[:n]


def ask(question: str, lang: str = "vi", filters: dict | None = None) -> dict:
    question = (question or "").strip()[:500]
    ctx = Ctx(lang, filters)
    try:
        e = extract(ctx, question)
        e["_q"] = question
        intent = classify(question, e)
        if not intent:
            ans = _answer(ctx, None, ctx.t("Tôi chưa hiểu câu này nên không trả lời (không đoán). Thử hỏi giống các câu mẫu:",
                                            "이 질문은 이해하지 못해 답하지 않습니다 (추측하지 않음). 아래 예시처럼 물어보세요:"))
            ans["suggestions"] = closest_samples(question, ctx.lang)
            return ans
        fn = HANDLERS[intent]
        ans = fn(ctx, e, question) if intent in ("metric_explain", "questions_pending") else fn(ctx, e)
        ans["entities"] = {k: v for k, v in e.items() if v and not k.startswith("_")}
        return ans
    finally:
        ctx.con.close()
