---
title: "KOPS MVP Phase 1 — kế hoạch thực hiện mở rộng data warehouse"
status: ready
created: 2026-10-19
spec: analys-docs/mvp_phase1_spec.md
---

# KOPS MVP Phase 1 — Kế hoạch thực hiện

**Mục tiêu:** mở rộng `dw/` để dashboard cho biết đúng tiến độ từng style, dự báo ngày xong bằng báo cáo sản xuất ngày, và chỉ ra nhà máy nào đang thiếu dữ liệu. Toàn bộ đặc tả nằm ở `analys-docs/mvp_phase1_spec.md`; tài liệu này chỉ chia việc, thứ tự và cách nghiệm thu.

**Đọc trước khi bắt đầu:** `GUIDELINES.md` → `dw/README.md` → `analys-docs/review_inspection_production.md` → `analys-docs/mvp_phase1_spec.md` → `analys-docs/open_questions.md` Phần 1.

## 1. Nguyên tắc làm việc

- Mỗi task một nhánh `feat/M1-xx-<tên-ngắn>` tách từ `main`, một PR. Không push thẳng lên `main`, không tự merge.
- Chạy được mọi lúc: sau mỗi task, `cd dw && .venv/bin/python -m kops_dw` phải build xong và **mọi golden test PASS**, kể cả test cũ.
- Code, comment, commit, PR bằng tiếng Anh, theo conventional commits. Tài liệu bằng tiếng Việt.
- Không sửa file trong `raw-docs/`. Không commit `dw/build/`, `raw-docs/`, dữ liệu thật hay tên kiểm viên.
- Gặp tình huống không có trong spec, hoặc số đo được khác golden number: **dừng, ghi lại, hỏi PO**. Không sửa test cho khớp code.
- Câu hỏi nghiệp vụ còn mở: dùng giả định trong `open_questions.md`, đặt giá trị vào `config.py` để đổi được, ghi rõ trong PR.

## 2. Danh sách task

Ước lượng theo giờ làm việc thực tế (đã có AI hỗ trợ). Cột "Vai trò" theo `GUIDELINES.md` §4.

| ID | Task | Vai trò | Phụ thuộc | Ước lượng |
|---|---|---|---|---|
| M1-01 | Quy ước thư mục nguồn + metadata file (brand, vendor, nhà máy, mùa) + `FILE_FOLDER_MISMATCH` | Data Engineer | — | 3h |
| M1-02 | Parser báo cáo sản xuất ngày (2 template) + giải quyết ngày báo cáo | Data Engineer | M1-01 | 8h |
| M1-03 | Core: last-seen, chuỗi sản lượng ngày, alias style Q27, chiều brand, `style_external` | Data Engineer | M1-02 | 5h |
| M1-04 | Dự báo ngày xong (rolling rate, chọn nguồn, độ tin cậy) + cập nhật `health` | Data Engineer | M1-03 | 4h |
| M1-05 | Độ tươi dữ liệu theo nhà máy và theo style | Data Engineer | M1-03 | 3h |
| M1-06 | Parser bảng kiểm (SL đạt, lọc nhà máy, style bộ, số kiểm viên) + trích `REQUEST ETD` | Data Engineer | M1-01 | 6h |
| M1-07 | Funnel style và màu × size + cờ số lượng | Data Engineer | M1-03, M1-06 | 4h |
| M1-08 | Dashboard: chọn brand, thẻ và bảng độ tươi, funnel và biểu đồ ngày trong Style 360, nguồn dự báo | Frontend — Dashboard | M1-04, M1-05, M1-07 | 8h |
| M1-09 | Golden test G1–G13 + cập nhật test cũ (W33) | QA | M1-04 → M1-07 | 3h |
| M1-10 | Cập nhật tài liệu: `dw/README.md`, `GUIDELINES.md` §7, `open_questions.md` (trạng thái R5/R7) | Tech Writer | M1-08, M1-09 | 2h |
| M1-11 | Review tổng + chạy lại từ thư mục sạch + báo cáo cho PO | Code Reviewer + BA | tất cả | 2h |

**Tổng khoảng 48 giờ.** Song song được: M1-06 với M1-02…M1-05; M1-08 bắt đầu khung giao diện khi M1-04 xong.

```
M1-01 ─┬─ M1-02 ── M1-03 ─┬─ M1-04 ─┐
       │                  ├─ M1-05 ─┼─ M1-08 ─┐
       └─ M1-06 ──────────┴─ M1-07 ─┘         ├─ M1-10 ── M1-11
                              M1-09 ──────────┘
```

## 3. Chi tiết và tiêu chí nghiệm thu

### M1-01 — Quy ước thư mục và metadata file
- **Làm:** `pipeline.discover()` quét đệ quy `raw-docs/PRODUCTION/**` và `raw-docs/INSPECTION/**`. `classify()` nhận thêm 2 parser `daily_production`, `inspection_tracker`. Hàm `file_meta(path, workbook)` trả brand, vendor, nhà máy, mùa theo spec §2. Thêm các cột `brand`, `vendor`, `factory` vào `etl.source_file`.
- **Nghiệm thu:**
  - File `DONG MY/261002 … (CHALLENGER - MTT)` → nhà máy MTT, trạng thái `DUPLICATE`, có `FILE_FOLDER_MISMATCH`.
  - File DHG → brand `8 SECONDS`, vendor `DHG(DAEHAN GROBAL)`, nhà máy `HAGACO`.
  - G1 đúng.

### M1-02 — Parser báo cáo sản xuất ngày
- **Làm:** `dw/kops_dw/ingest/daily_production.py`. Đọc theo nhãn header (spec §3.1); xác định ngày báo cáo theo spec §3.2. Mở workbook ở chế độ `read_only=True`: file 5–9 MB, khoảng 90 sheet.
- **Nghiệm thu:**
  - Nạp đủ 7 file, không có `PARSE_FAILED`.
  - G2, G3 đúng.
  - Sheet ẩn `7.281` của TRUONG PHUC → `SHEET_SKIPPED`.
  - Ô `#REF!` của TBM → NULL + `EXCEL_ERROR`.
  - Không có dòng nào có `size_code` rỗng trong `raw.daily_prod_row`.
  - Thời gian build tăng thêm không quá 60 giây.

### M1-03 — Core cho báo cáo ngày
- **Làm:** `core.daily_progress` (last-seen, spec §4.1), `core.daily_output_series` (§4.2), alias Q27 trong `config.STYLE_ALIASES`, cột `brand` cho `core.style_order` (= CHALLENGER), `core.style_external` cho style của 8 SECONDS. Áp quy tắc mã theo brand (§3.4).
- **Nghiệm thu:**
  - G4, G12 đúng.
  - `daily_progress` không lẫn hai brand.
  - Style `CHE…` có `STYLE_ALIAS_UNCONFIRMED`.

### M1-04 — Dự báo ngày xong
- **Làm:** `mart.style_forecast` theo spec §4.3. Thêm `rate_window = 3`, `rate_lookback_days = 10` vào `RULES`. `mart.style_360` lấy `projected_ready`, `days_late`, `forecast_source`, `forecast_confidence` từ đây. Hàm ngày làm việc (bỏ Chủ nhật) viết một lần, dùng chung.
- **Nghiệm thu:**
  - G6, G7 đúng.
  - Style chưa có báo cáo ngày vẫn dùng Production Status như cũ.
  - Không style nào có `days_late` mà thiếu `forecast_source`.

### M1-05 — Độ tươi dữ liệu
- **Làm:** `mart.factory_freshness`, `mart.style_freshness` theo spec §4.4. Đọc `KOPS_TODAY` (mặc định là ngày build).
- **Nghiệm thu:**
  - Với `KOPS_TODAY=2026-10-19`: G5, G8 đúng; TAN BINH MINH và TRUONG PHUC là FRESH.
  - Style của NATEXCO biến mất khỏi báo cáo khi chưa xong → `STOPPED_REPORTING`.

### M1-06 — Parser bảng kiểm
- **Làm:** `dw/kops_dw/ingest/inspection_tracker.py` + bảng theo spec §3.3. Map tên sheet sang nhà máy trong `config.py` (`TP`→TRUONG PHUC, `HÀ HIẾU`→HA HIEU, `FG`→FG VINA, `MTTD`→MTT…). Trích `REQUEST ETD m/d` thành `change_proposal` (nguồn INSPECTION). Không nạp tên kiểm viên vào core/mart.
- **Nghiệm thu:**
  - G9, G11 đúng.
  - Không có cột tên người nào trong core/mart.
  - Không tính tỷ lệ lỗi ở đâu cả.

### M1-07 — Funnel
- **Làm:** `mart.style_funnel`, `mart.funnel_assortment`, các cờ theo spec §4.5 (ghi vào `etl.data_issue` qua `sql/15_issues.sql`). Style bộ: SL đạt = min theo món.
- **Nghiệm thu:**
  - G10 đúng.
  - Với mọi style có đủ dữ liệu: `ordered ≥ cut ≥ input ≥ output` hoặc có cờ tương ứng.
  - Tổng funnel của mùa 26FW hiển thị được trên một dòng.

### M1-08 — Dashboard
- **Làm:** theo spec §6. Giữ hệ màu, sáng/tối và mobile như hiện tại (bảng màu đã kiểm, không thêm màu mới ngoài trạng thái FRESH/STALE/DARK dùng good/warning/critical kèm icon + chữ). Biểu đồ sản lượng ngày dùng `columns()` sẵn có.
- **Nghiệm thu:**
  - Chụp màn hình 8 tab, sáng và tối, desktop 1360px và mobile 390px. Không lỗi console, không cuộn ngang ở mobile.
  - Style 360 của CHF4MPT6444 cho thấy funnel, sản lượng ngày 11–15/10 (10, 30, 45, 50, 55) và dự báo 25/10.
  - Chọn brand 8 SECONDS chỉ hiện dữ liệu HAGACO.

### M1-09 — Golden test
- **Làm:** thêm G1–G13 vào `checks.py`; test đọc `KOPS_TODAY`. Sửa test W33 cũ (49 → 18), ghi chú lý do trong code.
- **Nghiệm thu:** `python -m kops_dw test` → ALL PASS. Thiếu nguồn thì SKIP, không FAIL.

### M1-10 — Tài liệu
- **Làm:** cập nhật `dw/README.md` (nguồn mới, quy ước thư mục, bảng mới, giới hạn), `GUIDELINES.md` §7 (golden numbers mới), `open_questions.md` (R5 ✅ một phần, R7), `review_inspection_production.md` nếu có số liệu thay đổi.
- **Nghiệm thu:** không còn chỗ nào trong tài liệu mâu thuẫn với code; link nội bộ đều mở được.

### M1-11 — Review và bàn giao
- **Làm:** xoá `dw/build/` và `dw/.venv/`, chạy lại từ đầu theo README. Review toàn bộ diff theo GUIDELINES; BA xác nhận các quy tắc nghiệp vụ khớp spec.
- **Nghiệm thu:** báo cáo cho PO theo mẫu ở mục 4, kèm ảnh chụp dashboard và danh sách câu hỏi cần KLMAS trả lời.

## 4. Mẫu báo cáo

Mỗi task kết thúc bằng một báo cáo trong PR hoặc thread:

```
**M1-xx (<tên task>): <DONE | PASS_WITH_GAPS | BLOCKED | FAIL | NOT_VERIFIED>**
- Phạm vi đã làm: …
- Nhánh / commit: …
- Lệnh đã chạy và kết quả: `KOPS_TODAY=2026-10-19 .venv/bin/python -m kops_dw` → <số PASS>/<tổng>, build <x> giây
- Golden numbers liên quan: G… = … (khớp / lệch + giải thích)
- Còn thiếu / rủi ro: …
- Câu hỏi cho PO: …
```

## 5. Dừng lại và hỏi PO khi

- Số đo được khác golden number trong spec §8.
- Gặp template báo cáo mới (nhà máy, brand hoặc bố cục khác hai template đã mô tả).
- Cần đổi một quy tắc đã ghi trong spec, hoặc cần trả lời một câu trong `open_questions.md` Phần 1.
- Sắp xoá dữ liệu, đổi cấu trúc thư mục `raw-docs/`, hoặc push lên `main`.
