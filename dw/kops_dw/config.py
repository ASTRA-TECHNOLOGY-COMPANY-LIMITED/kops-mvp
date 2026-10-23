"""Paths, source discovery rules and configurable business rules for the KOPS DW MVP."""
from __future__ import annotations

import datetime as dt
import os
import shutil
from pathlib import Path

DW_DIR = Path(__file__).resolve().parent.parent          # kops-mvp/dw
REPO_DIR = DW_DIR.parent                                 # kops-mvp
RAW_DOCS_DIR = Path(os.environ.get("KOPS_RAW_DOCS", REPO_DIR / "raw-docs"))
INBOX_DIRS = [Path(p) for p in os.environ.get("KOPS_INBOX", "").split(os.pathsep) if p] or [
    REPO_DIR / "raw-docs" / "inbox",      # real emails (.eml), local only
    DW_DIR / "samples" / "inbox",         # SAMPLE emails shipped with the repo
]
BUILD_DIR = Path(os.environ.get("KOPS_BUILD", DW_DIR / "build"))
CACHE_DIR = BUILD_DIR / "cache"
# Incremental store (manifest + parse results as Parquet). Safe to delete: the next build parses everything again.
LAKE_DIR = Path(os.environ.get("KOPS_LAKE", BUILD_DIR / "lake"))
QUARANTINE_PATH = BUILD_DIR / "quarantine.csv"
# Parsing runs in N worker processes (1 = in the build process, easier to debug); each file has a time limit.
WORKERS = int(os.environ.get("KOPS_WORKERS", min(8, os.cpu_count() or 2)))
PARSE_TIMEOUT = int(os.environ.get("KOPS_PARSE_TIMEOUT", 600))      # seconds per file, 0 = no limit
# Excel files whose header layout is not in dw/templates/known_templates.json are quarantined (templates.py).
TEMPLATE_CHECK = os.environ.get("KOPS_TEMPLATE_CHECK", "1") == "1"
# Report files above this size are not opened (metadata only, quarantined as TOO_LARGE); technical documents
# (work sheets, comments, CAD...) are never opened whatever their size (docmeta.py). Emails/mailboxes are exempt.
MAX_PARSE_MB = float(os.environ.get("KOPS_MAX_PARSE_MB", 30))
DB_PATH = BUILD_DIR / "kops.duckdb"
DASHBOARD_PATH = BUILD_DIR / "dashboard.html"

# --- Business rules (configurable, pending KLMAS confirmation; see analys-docs/open_questions.md) ---
RULES = {
    "rdd_offset_days": 12,             # RDD = ETD VN + 12 (Q17)
    "ready_buffer_days": 5,            # finishing + inspection after sewing
    "default_daily_output": 45,        # pcs/day when factory has not reported (meeting example)
    "ontime_tolerance_days": 7,        # first lot ETD <= style ETD + 7 => on time
    "qty_tolerance_pct": 5,            # Q12
    "as_of_fallback": "2026-10-12",    # when a file carries no report date
}

# --- Master data aliases (normalised upper/unaccented text -> canonical code) ---
FACTORY_ALIASES = {
    "DONG MY": "DONG MY", "DM": "DONG MY",
    "TAN BINH MINH": "TAN BINH MINH", "TBM": "TAN BINH MINH", "TAN BINH MINH PLAN": "TAN BINH MINH",
    "TRUONG PHUC": "TRUONG PHUC", "TP": "TRUONG PHUC", "TRUONG PHUC TV": "TRUONG PHUC",
    "MTT": "MTT", "NATEXCO": "NATEXCO", "NTC": "NATEXCO",
    "HA HIEU": "HA HIEU", "HH": "HA HIEU",
    "TIEN THANH": "TIEN THANH", "FG BAC GIANG": "FG BAC GIANG", "FG VINA": "FG VINA",
    "XUAN THANH": "XUAN THANH", "SUNVIET": "SUNVIET", "PHAM GIA": "PHAM GIA",
    "HUY HOANG": "HUY HOANG", "MINH TUAN": "MINH TUAN", "THANH VAN": "THANH VAN", "AYM": "AYM",
}
FACTORY_ALIASES.update({
    # factories seen in other customers' ORDER RECAP / PRODUCTION PLAN (20-21/10/2026; names pending Q08)
    "SON HA": "SON HA", "SON HA GLOBAL": "SON HA", "JM": "JM", "HAGACO": "HAGACO", "HGC": "HAGACO",
    "B85": "B85", "XT": "XUAN THANH", "WISER MAX": "WISER MAX", "HA THANH": "HA THANH",
    "HA THANH PLAN": "HA THANH", "GIA NGUYEN": "GIA NGUYEN", "TRI DUC": "TRI DUC", "FG": "FG VINA",
    "SH": "SON HA",
})

# --- Customers (who orders from KLMAS) and brands; first matching key wins (title, file name, then folder) ---
CUSTOMER_KEYS = [
    ("CHALLENGER", "CHALLENGER"), ("CLGR", "CHALLENGER"),
    ("DAEHAN", "DHG"), ("DHG", "DHG"), ("8SECONDS", "DHG"), ("8 SECONDS", "DHG"), ("BPK", "DHG"),
    ("BEANPOLE", "DHG"), ("XEXYMIX", "DHG"),
    ("JBEE", "JBEE"), ("JBSC", "JBEE"), ("KOFA", "KOFA"),     # JBSC: JBEE's mail domain jbeesc.com ("BLACKYAK", "KOFA"),
    ("MIZUNO", "DKM"), ("DKMS", "DKM"), ("DKM", "DKM"), ("DAKYUNG", "DKM"), ("다경", "DKM"),
]
BRAND_ALIASES = {"8S": "8 SECONDS", "8SECONDS": "8 SECONDS", "BPK": "BEANPOLE KIDS", "BEANPOLE KIDS": "BEANPOLE KIDS",
                 "CLGR": "CHALLENGER"}

# --- Email ---
# Sender domains that belong to KLMAS (used to tell buyer -> KLMAS replies apart). Fill in when known.
KLMAS_EMAIL_DOMAINS: list[str] = [d for d in os.environ.get("KOPS_KLMAS_DOMAINS", "klmasvn.com").split(",") if d]
# Rule-based categories (first match = primary). Keywords in EN / KO / VI, matched case-insensitively.
EMAIL_CATEGORIES = [
    ("CANCEL", ["cancel", "취소", "huỷ", "hủy"]),
    ("QTY", ["quantity", "qty", "reduce", "increase", "수량", "감량", "증량", "số lượng", "giảm số", "tăng số"]),
    ("ETD", ["etd", "ship date", "delay", "postpone", "납기", "지연", "선적일", "giao hàng", "chậm", "trễ", "dời"]),
    ("COLOR_SIZE", ["colour", "color", "size", "컬러", "색상", "사이즈", "màu", "kích cỡ"]),
    ("SAMPLE", ["fpp", "top sample", "pp sample", "sample", "comment", "approve", "샘플", "컨펌", "승인", "mẫu", "duyệt"]),
    ("MATERIAL", ["fabric", "trim", "accessor", "원단", "부자재", "vải", "phụ liệu", "npl"]),
    ("INSPECTION", ["inspection", "aql", "final inspect", "검품", "검사", "kiểm hàng", "kiểm tra"]),
    ("SHIPMENT", ["booking", "b/l", "invoice", "container", "forwarder", "선적", "부킹", "xuất hàng", "đặt tàu"]),
    ("QUALITY", ["defect", "claim", "complaint", "불량", "클레임", "lỗi", "khiếu nại"]),
    ("PRICE_PO", ["price", "fob", "cmpt", "purchase order", "단가", "가격", "발주", "giá", "đơn giá"]),
    ("STATUS", ["status", "update", "progress", "진행", "현황", "tình trạng", "tiến độ"]),
]
# Ambiguous numeric dates like 05/10/2026 are read day/month (VN, KR exports). Set KOPS_EMAIL_DMY=0 for US m/d.
EMAIL_DMY = os.environ.get("KOPS_EMAIL_DMY", "1") == "1"
# Mailboxes (.mbox / .pst, ingest/mailbox.py): what is not loaded as business email. Comma-separated env overrides.
def _env_list(name, default):
    v = os.environ.get(name)
    return [x.strip() for x in v.split(",") if x.strip()] if v is not None else default


def _env_date(name):
    v = os.environ.get(name)
    return dt.date.fromisoformat(v) if v else None


MAIL_EXCLUDE_FOLDERS = _env_list("KOPS_MAIL_EXCLUDE_FOLDERS", [
    "Spam", "Junk", "Junk E-mail", "Junk Email", "Trash", "Deleted Items", "Deleted Messages", "Bin", "Drafts",
    "Outbox", "RSS Feeds", "Sync Issues", "Conflicts", "Calendar", "Contacts", "Tasks", "Notes", "Journal",
    "스팸", "스팸메일함", "휴지통", "지운 편지함", "임시 보관함", "임시보관함", "Thư rác", "Thùng rác", "Nháp"])
MAIL_ALLOW = [x.lower() for x in _env_list("KOPS_MAIL_ALLOW", [])]     # senders/domains never filtered
MAIL_SINCE, MAIL_UNTIL = _env_date("KOPS_MAIL_SINCE"), _env_date("KOPS_MAIL_UNTIL")

# Optional LLM extractor (off by default; needs PO decision P2 in plans/EMAIL_READINESS_PLAN.md).
EMAIL_LLM = os.environ.get("KOPS_EMAIL_LLM", "0") == "1"
EMAIL_LLM_MODEL = os.environ.get("KOPS_EMAIL_LLM_MODEL", "claude-sonnet-5-5")

# How the DW MVP covers the 14 requirements from KOPS meeting #1 (req_no -> status, where, next step).
REQUIREMENT_COVERAGE = {
    1: ("PARTIAL", "Ingest ORDER RECAP -> core.style_order (style master)", "AI nhận dạng minimap nhiều brand (D-07)"),
    2: ("PARTIAL", "Email -> stg.email_change -> tab Thay đổi (chờ duyệt)", "Thay rule-based bằng LLM + bước duyệt trong app (P-05)"),
    3: ("PARTIAL", "Lineage: mọi dòng có file, sheet, ô gốc", "Đăng nhập theo người + audit log (F-04)"),
    4: ("DONE", "Tab Nhà máy & NCC: gom style theo nhà cung cấp vải", "Nạp sheet FAB để có tên vải chi tiết (D-05)"),
    5: ("DONE", "Tab Thay đổi: lịch sử SL/màu từ ghi chú ORDER RECAP + email", "Ghi lịch sử khi sửa trực tiếp trong app (D-08)"),
    6: ("PARTIAL", "DW là nguồn duy nhất; mọi tổng tính từ chi tiết", "Export lại đúng mẫu Excel cũ (D-11)"),
    7: ("DONE", "Tab Xuất hàng: chọn style -> assortment màu x size, từng lô", "-"),
    8: ("PARTIAL", "Control Tower: dự kiến xong vs ETD, danh sách rủi ro", "Lịch T&A theo mốc + thông báo Zalo/email (P-01, P-03)"),
    9: ("TODO", "-", "Nạp FAB + checklist vật tư (D-05, P-04)"),
    10: ("OUT", "-", "Ngoài phạm vi MVP (cần API hãng tàu)"),
    11: ("TODO", "-", "PWA kiểm hàng (Q-02); kết quả kiểm sẽ nạp vào DW"),
    12: ("TODO", "-", "Phân công kiểm viên (Q-05)"),
    13: ("PARTIAL", "Control Tower + Xuất hàng là nền cho buyer dashboard", "Buyer portal có đăng nhập, RLS theo brand (D-10)"),
    14: ("PARTIAL", "Email + biên bản họp đã vào DW (nguồn cho kho tri thức)", "Trợ lý soạn trả lời có duyệt (A-04, A-05)"),
}

# Style codes that differ between files (open question Q05: not confirmed by KLMAS yet).
STYLE_ALIASES = {
    "CHFWWT6817": "CHF4WWT6817",   # typo in Shipment Status
    "CHF4WSK6851": "CHF4WHP6851",  # Shipment Status vs ORDER RECAP
    "CHF4WHP6852": "CHF4WSK6852",  # Shipment / Production Status vs ORDER RECAP
}

SHIPMENT_SHEET_FACTORY = {"DM": "DONG MY", "MTT": "MTT", "HA HIEU": "HA HIEU", "TP": "TRUONG PHUC",
                          "NATEXCO": "NATEXCO", "TBM": "TAN BINH MINH"}


def find_soffice() -> str | None:
    """LibreOffice is needed to read cell fills (status colours) from .xlsb files."""
    env = os.environ.get("KOPS_SOFFICE")
    if env:
        return env
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    mac = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    return mac if Path(mac).exists() else None
