"""Open KLMAS questions for the chatbot (F-04): titles from analys-docs/open_questions.md via kops_dw.questions."""
from __future__ import annotations

from kops_dw import questions

# metric words -> question codes that change the number
METRIC_QUESTIONS = {"đúng hạn": ["Q21"], "납기": ["Q21"], "lỗi": ["Q24", "Q25"], "불량": ["Q24", "Q25"], "độ tươi": ["Q32"],
                    "báo cáo ngày": ["Q22", "Q32"], "최신성": ["Q32"], "rdd": ["Q26"], "dung sai": ["Q13"], "mùa": ["Q33"],
                    "scorecard": ["Q21"], "hagaco": ["Q23"], "sản lượng": ["Q22", "Q02"]}


def title(code: str) -> str:
    t = questions.load().get(code)
    return f"{code}. {t}" if t else code


def pending_for(question: str) -> list[tuple[str, str]]:
    low = question.lower()
    codes = [c for w, cs in METRIC_QUESTIONS.items() if w in low for c in cs]
    if not codes:       # every question the dashboard numbers wait for (assumptions on screen)
        codes = [q for q in questions.ASSUMPTION_QUESTIONS.values() if q and q.startswith("Q")]
    titles = questions.load()
    return [(c, titles.get(c, "")) for c in dict.fromkeys(codes)]
