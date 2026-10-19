# ETL / ELT Pipeline Design

Mục tiêu: nạp các file Excel/PDF hiện hữu vào PostgreSQL theo Option B (`etl → raw → stg → core → mart`), idempotent, truy vết được, không mất dữ liệu, chịu được việc file bị xuất lại hằng ngày.

Công nghệ đề xuất [R]: Python 3.11 (`openpyxl`, `pyxlsb`, `pandas`, `pdfplumber`, `psycopg`), chạy theo lịch (cron / Windows Task Scheduler / Airflow nếu sau này mở rộng). LibreOffice headless chỉ dùng như phương án dự phòng để đọc màu nền ô của `.xlsb` (pyxlsb không đọc style) — luôn chạy trên **bản sao**.

## 0. Luồng tổng quát

```
Thư mục nguồn (drop folder)
   │  1. Register (hash, parse filename, phân loại template)
   ▼
etl.source_file ── duplicate? → đánh dấu duplicate_of, dừng
   │  2. Extract (theo định dạng)
   ▼
raw.sheet / raw.cell / raw.pdf_page        (giá trị nguyên văn + công thức + màu nền)
   │  3. Template parser (theo doc_type & version template)
   ▼
stg.* (text + cột parse, parse_ok)         → etl.data_issue (lỗi parse)
   │  4. Standardise (alias, ngày, số, màu, size, mã style)
   │  5. Validate (quy tắc DQ)              → etl.data_issue (lỗi nghiệp vụ)
   ▼
   6. Load core (upsert theo khoá tự nhiên, trong 1 transaction / file)
   ▼
core.*  → 7. mart views / materialized views  → 8. reconciliation report
```

## 1. Đăng ký file & theo dõi phiên bản

- Tính `sha256`; nếu đã tồn tại → `duplicate_of_file_id` (ví dụ F3b = F3) và không xử lý tiếp.
- Parse tên file: regex `^(\d{6})(R\d+)?\s+(\w+)\)\s+(\d{2}(?:SS|FW))\s+(.+)\.(xlsx|xlsb|xls|pdf)$` → `report_date`, `revision`, `author_tag`, `season_code`, `title`. Không khớp → vẫn đăng ký, `doc_type = UNKNOWN`, issue `FILENAME_UNPARSED`.
- Phân loại `doc_type` bằng **nội dung**, không chỉ tên file: dấu hiệu template (ô `A5='NO'` & `D5='STYLE NO'` → PRODUCTION_STATUS; tiêu đề block `n) … PRODUCTION DETAIL SHIP STATUS` → SHIPMENT_STATUS; sheet `ORDER RECAP` + `DETAIL` → ORDER_RECAP; PDF → PROFILE).
- **Chuỗi phiên bản**: cùng `(doc_type, season_code, author_tag)` → file có `report_date`/`revision` lớn hơn đặt `superseded_by_file_id` cho file cũ. Core luôn phản ánh bản mới nhất; snapshot cũ vẫn giữ trong `production_snapshot`, `style_fabric` (theo `as_of_date`).

## 2. Extract

| Định dạng | Cách đọc | Lưu ý |
|---|---|---|
| xlsx | `openpyxl` 2 lần: `data_only=True` (giá trị cache) và `data_only=False` (công thức); đọc `fill.fgColor`, `merged_cells`, `sheet_state` | Đọc cả sheet ẩn; không đánh giá lại công thức; không chạy macro |
| xlsb | `pyxlsb` (giá trị); màu nền ô & merge: chuyển bản sao sang xlsx bằng LibreOffice headless rồi đọc bằng openpyxl | Ghi `raw.sheet.dimension` và đối chiếu số ô giữa 2 cách đọc; ảnh nhúng (thiết kế) có thể trích riêng vào object storage (P) |
| xls (nếu có) | `xlrd` | |
| PDF | `pdfplumber` text layer; trang có `len(text) < ngưỡng` → `needs_ocr = true`, OCR bằng `tesseract` (kor+eng) nếu cần | PDF hiện tại chỉ là tài liệu tham chiếu |

Mọi ô không rỗng → `raw.cell` (giá trị text nguyên văn, số, kiểu, công thức, màu nền, merge). Lỗi Excel (`#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`) giữ nguyên ở raw với `value_type='e'`.

## 3. Template parsers (raw → stg)

| Parser | Logic | Kiểm tra nội bộ bắt buộc |
|---|---|---|
| `prod_status_v1` (F1) | Header ở dòng chứa `STYLE NO`; dòng dữ liệu = cột D khớp regex style; bỏ dòng có `TOTAL` ở cột B, dòng `G.TTL`, `DAILY STATUS` | Số dòng = số style trong KPI ô I2 (110) |
| `ship_status_v1` (F2) | Tìm ô tiêu đề block `^\s*\d+\)`; block cao tới block kế tiếp; cột size = 6 cột sau COLOR; các mốc `S/DATE`, `TOTAL SHIPPED…`, `SMPL LIST`, `BAL` xác định section ORDER/SHIPMENT/SAMPLE | Với mỗi block: Σ ORDER = ô TTL dòng S/DATE; Σ SHIPMENT + Σ SAMPLE = ô TOTAL SHIPPED (đã kiểm: 144/144 block đúng) |
| `order_recap_v1` (F3/F4) | Block bắt đầu khi cột D khớp regex style và cột C có brand; gom tới block kế; dòng màu = cột H không rỗng và không thuộc từ khoá header; milestone 40 cột → jsonb `{header: text}`; đọc màu nền ô B/D/E dòng đầu | Σ màu = cột K; số block có style = số style ở DETAIL + số CANCEL |
| `fab_v1` (FAB sheets) | Header dòng 3; dòng dữ liệu khi cột I khớp regex style; `as_of_date` từ tên sheet (`FAB(260519)` → 2026-05-19; `FAB(0615)` → 2026-06-15 với năm của mùa) | AF ≈ M×AB; AK = Σ cột lô tàu |

Template versioning: mỗi parser có `parser_version`; nếu dấu hiệu header không khớp (thêm/bớt cột) → run `FAILED` với issue `TEMPLATE_CHANGED`, không nạp một phần.

## 4. Chuẩn hoá (stg → giá trị chuẩn)

| Loại | Quy tắc |
|---|---|
| Mã style | `upper(trim())`; tra `core.style_alias` trước; kiểm tra regex `^CH[A-Z][0-9][MWU][A-Z]{2}[0-9]{4}$`; sai → vẫn tạo style với `is_code_valid=false` + issue (không đoán sửa) |
| Tên nhà máy / NCC / màu | `alias_norm = upper(unaccent(regexp_replace(trim(x), '\s+', ' ')))`; tra bảng alias; không thấy → issue `*_UNKNOWN`, đưa vào hàng chờ duyệt alias; **không tự tạo** master mới |
| Ngày (datetime Excel) | → `date`; giờ bỏ; serial 1900 (`1900-01-12` từ ô ETD rỗng) → NULL |
| Ngày dạng text `m/d` | Năm suy từ mùa: lấy năm gần ETD style nhất trong cửa sổ [ETD−12 tháng, ETD+3 tháng]; luôn lưu `raw_text`; đánh `is_estimated=true` khi có `?`, `PLAN`, `EST` |
| Chuỗi sự kiện | Tách theo `\n`, `+`, `&`, `,`, `➜`; mỗi token `m/d [SENT|RE|CMMT|REJECT|RETURN|ETA|ETD|2ND …]` → 1 `milestone_event` với `round_no` |
| Múi giờ | Ngày nghiệp vụ là ngày địa phương (VN/KR) → kiểu `date`, không dùng timestamp; metadata ETL dùng `timestamptz` (UTC) |
| Số lượng | `int`; bỏ hậu tố `P/p`, dấu phẩy; số thực có phần lẻ ở cột qty → issue |
| Yard, định mức | `numeric(10,2)`, `numeric(6,3)` — không dùng float |
| Tiền | `numeric(12,4)` + `currency char(3)`; nguồn không ghi đơn vị → `currency` NULL + issue `CURRENCY_MISSING` (hoặc suy theo C/O nếu nghiệp vụ duyệt quy tắc) |
| Giá đổi `5500->5000` | lấy giá sau mũi tên; lưu chuỗi gốc ở `unit_price_raw` |
| Mã có số 0 đứng đầu | Mọi mã (style, trim, order_no, fabric_code) lưu `text/varchar`, không bao giờ ép kiểu số |
| Văn bản đa ngôn ngữ | UTF-8; chuẩn hoá Unicode NFC (tiếng Việt có dấu tổ hợp & tiếng Hàn); giữ nguyên bản gốc ở `*_raw` |
| Ô trống / khoảng trắng / `' '` / `0` ở cột text | → NULL; `0` ở cột số giữ nguyên là 0 chỉ khi ô là số thật (không phải công thức trả 0 do ô tham chiếu rỗng — kiểm qua raw.formula) |
| Lỗi Excel | → NULL + issue `EXCEL_ERROR` (giữ ở raw) |
| Công thức | Không tính lại; dùng giá trị cache; cột thuần dẫn xuất (BAL, TTL, mirror BK–BP, DETAIL) không nạp core, chỉ dùng đối soát |
| Màu nền → trạng thái | Bảng `core.style_status.legend_fill_rgb`; màu theme không đọc được RGB → issue `STATUS_COLOR_UNKNOWN`, giữ trạng thái cũ |

## 5. Validation

| Mã quy tắc | Mức | Mô tả |
|---|---|---|
| REQ_FIELD | ERROR | style_no, season, collection, colour, qty bắt buộc |
| STYLE_NO_FORMAT | WARN | regex mã style |
| FK_UNRESOLVED | ERROR | factory/colour/size/supplier không map được |
| DUP_KEY | ERROR | trùng (style_order, colour) / (shipment, soc, size) trong cùng file |
| QTY_RANGE | WARN | qty < 0; shipped > order × 1.05 (ngưỡng P); inspection > output |
| DATE_RANGE | WARN | ngày ngoài [ETD − 12 tháng, ETD + 3 tháng]; ETA < ETD; RDD ≠ ETD + 12 |
| ETD_OUT_OF_SEASON | WARN | ETD không thuộc cửa sổ mùa (5 style 27SS) |
| INTERNAL_TOTAL | ERROR | Σ chi tiết ≠ ô tổng trong file (block F2, màu F3) |
| XSRC_MISMATCH | WARN | Giá trị lệch giữa các nguồn (order qty F1/F3/F2; shipped F1/F2/F3; factory) |
| STYLE_NOT_IN_ORDER | INFO | Style có ở FAB/F2 nhưng không có ở ORDER RECAP |
| EXCEL_ERROR | INFO | ô lỗi Excel ở cột được nạp |
| TEMPLATE_CHANGED | ERROR | header không khớp version parser |

Mức ERROR ở dòng → dòng đó không vào core (nằm ở stg với `parse_ok=false`) nhưng run vẫn tiếp tục (`PARTIAL`); ERROR ở cấp template → run `FAILED`, rollback.

## 6. Load core

- Một transaction / file. Thứ tự: master (brand, season, collection, factory/colour/size alias đã duyệt, style) → style_order → colour → size qty → factory_assignment → milestone → snapshot/plan → shipment → shipment_line → sample → fabric.
- Upsert theo khoá tự nhiên:
  - style: `style_no`
  - style_order: `(season, style, collection)`
  - style_order_color: `(style_order, color)`
  - order_qty_size: `(soc, size)`
  - shipment: `(season, etd, eta, mode)`; shipment_line: `(shipment, soc, size)`
  - production_snapshot / plan: `(style_order, as_of_date, source_file)`
  - style_fabric: `(source_file, as_of_date, source_row)`
- Dữ liệu "trạng thái hiện tại" (qty màu, size, lô xuất, milestone) từ file mới hơn **thay thế** dữ liệu cùng phạm vi từ file cũ hơn của cùng nguồn (delete-then-insert theo `(season, doc_type)` trong transaction) → tránh trùng khi file xuất lại; các bản ghi bị thay vẫn truy vết được qua `raw`.
- Dữ liệu snapshot (production_snapshot, style_fabric) **cộng dồn** theo `as_of_date`.
- Thay đổi so với lần nạp trước: ghi `style_order_status_history`, `order_qty_change`, `factory_assignment` (đóng `valid_to`, mở dòng mới).

## 7. Incremental & đồng bộ

| Tình huống | Xử lý |
|---|---|
| File mới | Đăng ký → xử lý đầy đủ |
| Cùng nội dung, khác tên (bản sao `(1)`) | Hash trùng → bỏ qua |
| Phiên bản mới của cùng báo cáo (ngày/revision lớn hơn) | Xử lý; đánh `superseded_by` cho bản cũ; thay thế dữ liệu "hiện tại" của phạm vi đó |
| File cũ nạp sau file mới (backfill) | Chỉ nạp snapshot; không ghi đè dữ liệu hiện tại (so `report_date`) |
| File bị sửa tại chỗ (cùng tên, hash khác) | Coi như phiên bản mới; giữ cả hai trong registry |
| File bị xoá khỏi thư mục | Không xoá dữ liệu; đánh dấu `source_file.missing_at` (P) |
| Template đổi | Run FAILED + issue `TEMPLATE_CHANGED`; cập nhật parser version |

## 8. Logging, audit & phục hồi

- `etl.ingestion_run`: thời gian, phiên bản parser, số dòng đọc/parse/nạp/từ chối theo bảng (jsonb `counts`).
- `etl.data_issue`: mọi lỗi kèm `cell_ref` để người dùng mở đúng ô trong Excel; trạng thái OPEN/ACCEPTED/FIXED/IGNORED.
- Báo cáo sau mỗi run: `mart.v_reconciliation_reported_vs_computed` + danh sách issue ERROR/WARN mới.
- Phục hồi: mỗi run một transaction → lỗi thì rollback toàn bộ core; `raw` giữ lại để debug. Có thể **dựng lại core từ raw** bằng cách chạy lại parser (raw là nguồn bất biến). Backup PostgreSQL hằng ngày (pg_dump) + PITR nếu dùng managed service.
- File nguồn không bao giờ bị sửa/di chuyển bởi pipeline (chỉ đọc); xử lý xlsb trên bản sao tạm.

## 9. Lộ trình triển khai

1. **Tuần 1–2**: tạo schema; seed master (brand, season, collection, line, item_type, size, mode, milestone_type, status, factory + alias, colour + alias) cùng nghiệp vụ; parser F2 (đã có prototype, kiểm 144/144 block) và F3 block/colour.
2. **Tuần 3**: parser F1 (snapshot/plan), FAB; validation + issue log; mart views.
3. **Tuần 4**: parser milestone text; báo cáo đối soát; chạy song song với Excel 2–4 tuần.
4. **Sau đó**: chuyển dần nhập liệu sang app/form ghi trực tiếp vào core (bỏ raw/stg cho phần đó); bổ sung dữ liệu QC/inspection.
