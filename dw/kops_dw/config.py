"""Paths, source discovery rules and configurable business rules for the KOPS DW MVP."""
from __future__ import annotations

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
DB_PATH = BUILD_DIR / "kops.duckdb"
DASHBOARD_PATH = BUILD_DIR / "dashboard.html"

# --- Business rules (configurable, pending KLMAS confirmation; see analys-docs/open_questions.md) ---
RULES = {
    "rdd_offset_days": 12,             # RDD = ETD VN + 12 (Q16)
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
