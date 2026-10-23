"""Vietnamese / Korean UI text of the manager dashboard (E-05).

The page is written in Vietnamese; every UI string goes through L('...') and is looked up in
templates/i18n/{vi,ko}.json (key = the Vietnamese text, placeholders {name}). The dictionaries are embedded into
build/manager.html at render time. `python -m kops_dw i18n` rewrites vi.json from the template and lists the keys
still missing in ko.json; the check fails while a key has no Korean text or Vietnamese text sits outside L().
"""
from __future__ import annotations

import json
import re

from . import config

TEMPLATE = config.DW_DIR / "templates" / "manager.html"
DICT_DIR = config.DW_DIR / "templates" / "i18n"
LANGS = ("vi", "ko")

_KEY = re.compile(r"(?<![\w.$])L\('((?:[^'\\]|\\.)*)'")
_VI = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]", re.I)
_PH = re.compile(r"\{(\w+)\}")
# Vietnamese UI words without diacritics (missed by _VI) seen in labels: a quoted string holding one of them is untranslated
_VI_ASCII = re.compile(r"""(['`>])\s*(?:Cao|May|SL|Sau|Xong|trang|theo|cho|khi)\b[^'`<]*""")
_EMBED = re.compile(r"/\*I18N\*/.*?/\*END_I18N\*/", re.S)


def _unescape(k: str) -> str:
    return re.sub(r"\\(.)", r"\1", k)


def template_keys(html: str | None = None) -> list[str]:
    html = html if html is not None else TEMPLATE.read_text(encoding="utf-8")
    return sorted({_unescape(k) for k in _KEY.findall(html)})


def load(lang: str) -> dict[str, str]:
    f = DICT_DIR / f"{lang}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def embed(html: str) -> str:
    """Put both dictionaries into the page (only the keys it uses)."""
    keys = set(template_keys(html))
    data = {lang: {k: v for k, v in load(lang).items() if k in keys} for lang in LANGS}
    return _EMBED.sub(lambda _: "/*I18N*/" + json.dumps(data, ensure_ascii=False) + "/*END_I18N*/", html, count=1)


def untranslated_text(html: str | None = None) -> list[str]:
    """Vietnamese text in the page that does not go through L() (comments and the <style> block excluded)."""
    html = html if html is not None else TEMPLATE.read_text(encoding="utf-8")
    body = re.sub(r"<style>.*?</style>|<!--.*?-->|/\*.*?\*/", "", html, flags=re.S)
    body = re.sub(r"(?m)(^|\s)//.*$", "", body)
    body = _KEY.sub("", body)
    return sorted({ln.strip()[:80] for ln in body.splitlines() if _VI.search(ln) or _VI_ASCII.search(ln)})


def sync() -> list[str]:
    """Rewrite vi.json from the template; return the keys missing in ko.json."""
    keys = template_keys()
    DICT_DIR.mkdir(parents=True, exist_ok=True)
    (DICT_DIR / "vi.json").write_text(json.dumps({k: k for k in keys}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ko = load("ko")
    return [k for k in keys if not ko.get(k)]


def check() -> list[tuple[str, bool, str]]:
    keys = template_keys()
    vi, ko = load("vi"), load("ko")
    missing = [k for k in keys if k not in vi or not ko.get(k)]
    ph = [k for k in keys if ko.get(k) and set(_PH.findall(k)) != set(_PH.findall(ko[k]))]
    loose = untranslated_text()
    return [
        ("UI text: every L() key has vi + ko text", not missing, "; ".join(missing[:5]) or f"{len(keys)} keys"),
        ("UI text: ko placeholders match the vi key", not ph, "; ".join(ph[:5]) or "ok"),
        ("UI text: no Vietnamese outside L() in manager.html", not loose, " | ".join(loose[:5]) or "0"),
    ]
