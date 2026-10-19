# Database Design Recommendation

> **[Q]** quan sát · **[S]** suy luận · **[R]** khuyến nghị · **(P)** = bảng/cột tạm thời (provisional), cần xác nhận nghiệp vụ

## 1. Giả định thiết kế

| Hạng mục | Giả định | Cơ sở |
|---|---|---|
| Khối lượng | ~100–150 style/mùa/brand, ~300–400 style×màu, ~5–10k dòng chi tiết (size×lô) mỗi mùa; vài trăm nghìn ô raw mỗi lần nạp | [Q] đếm từ file |
| Tần suất cập nhật | File được xuất lại hàng ngày/vài ngày (tên file có ngày + revision R2) | [Q] tên file |
| Người dùng đồng thời | < 30 (nhân viên MR/QC/quản lý theo PDF: 14 MR, 65 QC, 5 quản lý) | [S] |
| Use case chính | Theo dõi vận hành + báo cáo; giai đoạn 1 vẫn nhập liệu bằng Excel, DB nạp từ file | [S] |
| Tích hợp | Chưa biết (ERP, Power BI, app nội bộ?) | → open_questions |
| Đa ngôn ngữ | Tiếng Anh, Hàn, Việt có dấu | [Q] |
| Mở rộng | Nhiều brand (PDF liệt kê ~30 brand), thêm dữ liệu QC/inspection | [S] |

## 2. Lựa chọn công nghệ

| Tiêu chí | **PostgreSQL** | SQL Server | MySQL | DuckDB / warehouse (BigQuery…) |
|---|---|---|---|---|
| Phù hợp khối lượng nhỏ, OLTP + báo cáo | Rất tốt | Rất tốt | Tốt | Tốt cho phân tích, yếu cho nhập liệu đồng thời |
| Ràng buộc toàn vẹn (FK, CHECK regex, partial unique, exclusion constraint cho khoảng thời gian) | Đầy đủ | Tốt (không có exclusion constraint) | Hạn chế hơn (CHECK regex từ 8.0.16, không partial index) | Hạn chế |
| Lưu raw bán cấu trúc (JSONB) | JSONB + GIN index | JSON (nvarchar) | JSON | Tốt |
| Unicode KR/VN, collation | ICU collation | NVARCHAR + collation | utf8mb4 | Tốt |
| Chi phí | Miễn phí, nhiều managed service | License (trừ Express ≤10GB) | Miễn phí | Thấp |
| Hệ sinh thái BI (Power BI, Metabase, Superset) | Tốt | Tốt nhất với Power BI | Tốt | Trung bình |

**[R] Chọn PostgreSQL 15+.** Lý do: khối lượng nhỏ không cần kho phân tích riêng; cần ràng buộc mạnh để chặn các lỗi đang thấy (mã style sai, tên nhà máy lệch, tổng sai); JSONB thuận tiện cho tầng raw; chi phí 0. Nếu công ty đã chuẩn hoá trên Microsoft (M365/Power BI/AD) thì SQL Server là lựa chọn tương đương — thiết kế logic dưới đây giữ nguyên, chỉ đổi kiểu dữ liệu.

## 3. Phương án kiến trúc

### Option A — CSDL quan hệ chuẩn hoá cho vận hành (chỉ tầng core)
Parser đọc Excel → ghi trực tiếp vào bảng core chuẩn hoá.
- ➕ Đơn giản, ít bảng, truy vấn nhanh.
- ➖ Mất dấu vết nguồn; khi parser sai hoặc template đổi thì không phục dựng được; không so sánh được snapshot giữa các lần xuất file; khó xử lý các giá trị mơ hồ.

### Option B — Raw layer + staging + core quan hệ + mart (một DB PostgreSQL, nhiều schema) ✅
`etl` (registry, run, issue) → `raw` (ô nguyên văn) → `stg` (dòng đã trải phẳng theo template) → `core` (mô hình chuẩn hoá) → `mart` (view báo cáo).
- ➕ Truy vết từng con số về ô nguồn; nạp lại được (idempotent); lưu lịch sử snapshot; tách biệt lỗi parse và lỗi nghiệp vụ; khi chuyển sang nhập liệu trực tiếp trên app, chỉ bỏ tầng raw/stg.
- ➖ Nhiều bảng hơn (48 bảng + view), cần job ETL.

### Option C — Data warehouse/lakehouse (star schema) (không khuyến nghị lúc này)
- ➖ Quá mức so với khối lượng; không hỗ trợ tốt cập nhật vận hành; chi phí vận hành cao.

| Tiêu chí | A | **B** | C |
|---|---|---|---|
| Độ phức tạp | Thấp | Trung bình | Cao |
| Bảo trì khi template Excel đổi | Kém | Tốt | Trung bình |
| Hiệu năng truy vấn | Tốt | Tốt (mart view/materialized view) | Tốt |
| Toàn vẹn dữ liệu & truy vết | Trung bình | **Cao** | Trung bình |
| Chi phí triển khai | Thấp | Trung bình | Cao |
| Mở rộng (brand mới, QC, app nhập liệu) | Trung bình | **Tốt** | Tốt cho BI, kém cho app |

**[R] Option B.** Nó giải quyết trực tiếp vấn đề lớn nhất quan sát được: cùng một con số có 3 giá trị ở 3 file và các tổng bị công thức làm sai — DB phải giữ chi tiết + nguồn gốc, rồi tự tính tổng.

## 4. Mô hình khái niệm (conceptual)

```
BRAND 1─* SEASON 1─* COLLECTION
STYLE (mã sản phẩm, bất biến) 1─* STYLE_ORDER (style trong 1 mùa/collection)
STYLE_ORDER 1─* STYLE_ORDER_COLOR 1─* ORDER_QTY_SIZE
STYLE_ORDER *─* FACTORY  (qua FACTORY_ASSIGNMENT có hiệu lực theo thời gian)
STYLE_ORDER 1─* MILESTONE_EVENT (mẫu REF/FPP/INLINE/TOP/PHOTO, vật tư, kế hoạch sản xuất)
STYLE_ORDER 1─* PRODUCTION_SNAPSHOT (output/inspection/shipped theo ngày báo cáo)
SHIPMENT 1─* SHIPMENT_LINE *─1 STYLE_ORDER_COLOR (+ size)
SAMPLE_DISPATCH 1─* SAMPLE_DISPATCH_LINE *─1 STYLE_ORDER_COLOR
STYLE_ORDER 1─* STYLE_FABRIC *─1 FABRIC *─1 SUPPLIER
FABRIC_SHIPMENT 1─* FABRIC_SHIPMENT_LINE *─1 STYLE_FABRIC
STYLE_ORDER *─* TRIM_ITEM (qua STYLE_TRIM)
STYLE_ORDER 1─* FACTORY_PRICE (P), PAYMENT (P)
SOURCE_FILE 1─* INGESTION_RUN 1─* RAW_CELL, DATA_ISSUE; mọi bảng core trỏ về source
```

Quy trình nghiệp vụ được phủ: nhận đơn → phân nhà máy → phát triển mẫu → nguyên phụ liệu → sản xuất → kiểm → xuất hàng → chứng từ/thanh toán (khung).

**Quyết định quan trọng**
1. Tách **STYLE** (mã sản phẩm) khỏi **STYLE_ORDER** (đơn của style trong một mùa) vì cùng một mã có thể reorder ở mùa khác (`CHF4WPT5822` reorder trong 26FW; `CHE4…` xuất hiện trong file 26FW).
2. Số lượng tổng (order/shipped) **không lưu như dữ liệu gốc** ở core — được tính từ dòng chi tiết; con số tổng do người nhập chỉ lưu ở `production_snapshot.*_reported` để đối soát.
3. **Shipment** là lô xuất hợp nhất (ETD+ETA+mode) dùng chung giữa các nhà máy [Q: cùng nhãn `8/12ETD-8/18ETA SEA` xuất hiện ở nhiều sheet].
4. Milestone dạng **bảng sự kiện** (EAV có kiểu) thay vì ~40 cột ngày, vì dữ liệu nguồn là chuỗi sự kiện (SENT → RE → 2ND SENT → CMMT) chứ không phải một ngày.
5. Trạng thái style lấy từ màu nền ô → lưu `status_code` + lịch sử.

## 5. Logical schema

Kiểu dữ liệu theo PostgreSQL. `audit` = các cột chuẩn `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz`, `source_file_id bigint FK`, `ingestion_run_id bigint FK`. DDL đầy đủ ở `schema.sql`.

### 5.1 Schema `core` — tham chiếu

| Bảng | Mục đích | Cột chính (kiểu, null) | PK | FK | Unique / Check | Index |
|---|---|---|---|---|---|---|
| `brand` | Brand/buyer | brand_code varchar(20) NN, brand_name text NN | brand_id | — | brand_code | — |
| `season` | Mùa | brand_id NN, season_code varchar(10) NN (`26FW`), season_year smallint NN, half char(2) NN CHECK in (SS,FW) | season_id | brand | (brand_id, season_code) | — |
| `collection` | Collection/mode | season_id NN, collection_code text NN (`26FW-FALL`), channel varchar(10) (OFFLINE/ONLINE), is_reorder bool NN | collection_id | season | (season_id, collection_code) | — |
| `product_line` | Line: NORMAL/ESSENTIALS/REORDER | line_code PK, name_kr, name_en | line_code | — | — | — |
| `item_type` | Nhóm hàng (JK, PT…) | item_type_code char(2) PK, name_en, name_kr, category (TOP/BOTTOM/OUTER/ACC) | item_type_code | — | — | — |
| `factory` | Nhà máy gia công | factory_code varchar(20) NN, name_canonical text NN, name_vi text, location text, is_active bool | factory_id | — | factory_code; name_canonical | — |
| `factory_alias` | Biến thể tên | alias_norm text NN (upper, bỏ dấu, trim), factory_id NN, alias_raw text | alias_norm | factory | — | factory_id |
| `color` | Màu chuẩn | color_code varchar(30) NN (`KHAKI_GREY`), color_name text NN | color_id | — | color_code | — |
| `color_alias` | Biến thể màu | alias_norm text PK, color_id NN | alias_norm | color | — | color_id |
| `size` | Size | size_code varchar(10) PK, sort_order smallint NN; alias (`2XL`=`XXL`?) qua `size_alias` | size_code | — | — | — |
| `shipping_mode` | SEA/AIR/HC | mode_code PK, name | | | | |
| `milestone_type` | Loại milestone | milestone_code PK (`REF_SMPL`, `FPP_CFM`, `INLINE_SMPL`, `TOP_SMPL`, `PHOTO_SMPL`, `SHIPPING_SMPL`, `WASH_TEST`, `LOGO`, `MTR_ETA`, `PTTN`, `WORKSHEET`, `MINIMARKER`, `MTR_CARD`, `CUTTING`, `INPUT`, `SEWING_FINISH`, `EXFACT`…), stage, sort_order | | | | |
| `style_status` | Trạng thái | status_code PK (NOT_FIXED, FIXED_PRICE, ON_PRODUCTION, SEWING_FINISHED, KOREA_SHIP_OUT, CANCEL, PENDING), legend_color_rgb | | | | |
| `supplier` | NCC vải/phụ liệu | supplier_name NN, supplier_type (FABRIC/TRIM), country_code char(2) | supplier_id | — | (supplier_type, supplier_name) | — |
| `supplier_alias` | | alias_norm PK, supplier_id NN | | | | |

### 5.2 Schema `core` — sản phẩm & đơn hàng

| Bảng | Mục đích | Cột chính | PK | FK | Unique / Check | Index |
|---|---|---|---|---|---|---|
| `style` | Mã sản phẩm (bất biến) | style_no varchar(12) NN; brand_id NN; gender char(1) (M/W/U); item_type_code; year_code char(1); subseason_digit char(1); serial char(4); description_en text; name_kr text; is_code_valid bool NN (generated từ regex) | style_id | brand, item_type | style_no; CHECK gender | (brand_id), (item_type_code) |
| `style_alias` | Mã thay thế/lỗi gõ | alias_style_no PK, style_id NN, reason text, confirmed bool NN default false | | style | | style_id |
| `style_order` | Style trong một mùa/collection | season_id NN; collection_id NN; style_id NN; order_no varchar(10) (`F9`, `W30`); line_code; status_code NN; etd_vn date; rdd_kr date; etd_raw text; main_fabric_text text; main_fabric_supplier_text; cancelled_at date; remarks text; audit | style_order_id | season, collection, style, product_line, style_status | (season_id, style_id, collection_id); (season_id, order_no) where order_no not null; CHECK rdd ≥ etd | (style_id), (status_code), (etd_vn) |
| `style_order_status_history` | Lịch sử trạng thái | style_order_id, status_code, valid_from timestamptz, source_file_id | (style_order_id, valid_from) | | | |
| `style_order_color` | Màu của đơn | style_order_id NN; color_id NN; color_raw text NN; seq smallint; order_qty int NN CHECK ≥0 (qty theo màu do buyer chốt); note text | soc_id | style_order, color | (style_order_id, color_id) | color_id |
| `order_qty_size` | Qty theo size | soc_id, size_code, qty int NN CHECK ≥0 | (soc_id, size_code) | soc, size | — | — |
| `order_qty_change` | Lịch sử thay đổi qty (từ ghi chú `260720 REDUCED 170P➜136P`) | soc_id, change_date date, qty_before int, qty_after int, note_raw | change_id | soc | | soc_id |
| `factory_assignment` | Phân nhà máy theo thời gian | style_order_id NN, factory_id NN, valid_from date NN, valid_to date, is_planned bool, note_raw | assignment_id | style_order, factory | EXCLUDE overlap (style_order_id, daterange) ; 1 dòng `valid_to is null` / style_order | (factory_id) |
| `style_trim` | Logo/label/trim | style_order_id NN, group_no smallint, trim_group text (`H.T LOGO`, `WAPPEN`), trim_item_id, spec_text, qty_per smallint | style_trim_id | style_order, trim_item | | style_order_id |
| `trim_item` | Mã trim | trim_code varchar(20) NN (`AP_TR02`), supplier_prefix varchar(5), trim_type, description | trim_item_id | supplier (P) | trim_code | — |

### 5.3 Schema `core` — tiến độ

| Bảng | Mục đích | Cột chính | PK | Unique / Check |
|---|---|---|---|---|
| `milestone_event` | Sự kiện mẫu/vật tư/kế hoạch | style_order_id NN, milestone_code NN, round_no smallint NN default 1, action varchar(12) (PLAN/SENT/RECEIVED/RETURN/REJECT/CMMT/CFM/ETD/ETA), event_date date, is_estimated bool NN, detail text, raw_text text NN, source_cell_ref text | event_id | index (style_order_id, milestone_code); CHECK event_date between 2020 and 2035 |
| `production_snapshot` | Số liệu báo cáo theo ngày | style_order_id NN, as_of_date date NN, daily_output int, output_qty int, inspected_qty int, shipped_qty_reported int, source_file_id NN | snapshot_id | (style_order_id, as_of_date, source_file_id); CHECK qty ≥ 0 |
| `production_plan` | Kế hoạch sản xuất (nhiều lần sửa) | style_order_id, as_of_date, cutting_plan, input_plan, sewing_finish_plan, exfact_est, etd_est, eta_est, plan_raw | plan_id | (style_order_id, as_of_date, source_file_id) |

### 5.4 Schema `core` — xuất hàng & mẫu

| Bảng | Mục đích | Cột chính | PK | Unique / Check |
|---|---|---|---|---|
| `shipment` | Lô xuất hợp nhất | season_id NN, etd date, eta date, mode_code, label_raw text NN, needs_review bool NN (ETA<ETD, thiếu năm) | shipment_id | (season_id, etd, eta, mode_code); CHECK eta ≥ etd OR needs_review |
| `shipment_line` | Qty xuất | shipment_id NN, soc_id NN, size_code NN, factory_id (nhà máy xuất), qty int NN CHECK > 0, source_cell_ref | shipment_line_id | (shipment_id, soc_id, size_code) |
| `sample_dispatch` | Gửi mẫu | style_order_id NN, sample_type (SHIPPING/PHOTO/FPP/INLINE/TOP), dispatch_dates date[], label_raw NN, destination (P) | sample_dispatch_id | — |
| `sample_dispatch_line` | | sample_dispatch_id, soc_id, size_code, qty CHECK > 0 | id | (sample_dispatch_id, soc_id, size_code) |

### 5.5 Schema `core` — nguyên liệu

| Bảng | Mục đích | Cột chính | PK | Unique / Check |
|---|---|---|---|---|
| `fabric` | Vải | supplier_id, fabric_code text, description text NN, construction (WOVEN/KNIT), composition text, width_inch numeric(5,1), width_raw text | fabric_id | (supplier_id, description) |
| `style_fabric` | BOM vải theo style×màu×part (snapshot) | style_order_id NN, garment_color_id, fabric_color text, part_code (BODY/CONTRAST1/LINING/POCKETING/PADDING…), part_raw NN, fabric_id, origin_country char(2), unit_price numeric(12,4), unit_price_raw text, currency char(3) **(P)**, consumption_order numeric(6,3), consumption_fpp, consumption_factory, po_date, po_qty_yd numeric(10,2), color_cfm_date, bt_submit_date, bt_reject_date, bt_cfm_date, exp_ship_date, etd, eta, shipped_yd numeric(10,2), as_of_date NN, source_row int NN | style_fabric_id | (style_order_id, garment_color_id, part_raw, fabric_id, as_of_date, source_row) |
| `fabric_shipment` | Lô tàu vải | etd date, mode_code, vessel_label text NN, suppliers_raw text | fabric_shipment_id | (etd, vessel_label) |
| `fabric_shipment_line` | | fabric_shipment_id, style_fabric_id, qty_yd numeric(10,2) | id | (fabric_shipment_id, style_fabric_id) |

### 5.6 Schema `core` — thương mại (P)
`factory_price` (style_order_id, price_type TARGET/FIXED/FINAL, cmph numeric(10,4), washing, embo, others, currency char(3), effective_date), `factory_payment` (style_order_id, pay_date, unit_price, qty, amount, currency), `trade_document` (style_order_id, doc_type PO_KR/PO_CN/CO/HS_CODE, doc_no, sent_date). Chưa có dữ liệu thực → tạo khung, không nạp.

### 5.7 Schema `etl`, `raw`, `stg`, `mart`

| Bảng | Mục đích |
|---|---|
| `etl.source_file` | Registry: path, file_name, sha256 (unique), size, mtime, report_date (parse từ tên), revision, author_tag, season_code, doc_type (PRODUCTION_STATUS/SHIPMENT_STATUS/ORDER_RECAP/PROFILE), duplicate_of_file_id, superseded_by_file_id |
| `etl.ingestion_run` | Mỗi lần nạp: file_id, parser_name, parser_version, started_at, finished_at, status, counts jsonb |
| `etl.data_issue` | Log lỗi/mơ hồ: run_id, file_id, sheet, cell_ref, entity, rule_code, severity, raw_value, message, status (OPEN/ACCEPTED/FIXED/IGNORED), resolved_by, resolved_at |
| `raw.sheet` | sheet_name, state (visible/hidden), dimension, merged_count |
| `raw.cell` | file_id, sheet_id, row, col, a1_ref, value_text, value_num, value_type, formula, fill_rgb, number_format, is_merged — PK (sheet_id,row,col) |
| `stg.*` | Bảng theo template: `stg.prod_status_row` (F1), `stg.ship_block_line` (F2), `stg.recap_style_block`, `stg.recap_color_row` (F3/F4), `stg.fab_row` (FAB) — giữ kiểu text + cột đã parse + `parse_ok` |
| `mart.*` (view) | `v_style_order_summary` (order/ship/sample/balance tính từ chi tiết, nhà máy hiện tại, trạng thái), `v_factory_summary`, `v_shipment_by_style_color_size`, `v_reconciliation_reported_vs_computed`, `v_fabric_balance` |

### 5.8 Audit & lịch sử
- Mọi bảng core: `created_at`, `updated_at`, `source_file_id`, `ingestion_run_id`.
- Lịch sử tường minh: `factory_assignment` (valid_from/to), `style_order_status_history`, `order_qty_change`, `production_snapshot`/`production_plan`/`style_fabric` theo `as_of_date`.
- [R] Bật trigger audit chung (`audit.row_change` lưu old/new jsonb) khi bắt đầu cho phép sửa trực tiếp trong app.

## 6. Hệ thống ghi nhận (system of record) cho từng thuộc tính

| Thuộc tính | Nguồn ưu tiên | Nguồn đối soát | Lý do |
|---|---|---|---|
| Style, mô tả EN/KR, collection, line, màu, qty theo màu, ETD/RDD, milestone, vải chính | F3/F4 ORDER RECAP (bản mới nhất) | F1, DETAIL | File master, cập nhật mới nhất |
| Qty theo size; lô xuất; mẫu gửi | F2 SHIPMENT STATUS | F3 1ST–4TH SHIP | Chi tiết nhất, tự nhất quán (100% block khớp tổng) |
| Output, inspection, daily output, kế hoạch cutting/input/sewing | F1 PRODUCTION STATUS | — | Chỉ F1 có |
| BOM vải, PO yard, lô vải | F3 FAB(sheet mới nhất); sheet cũ = snapshot lịch sử | F3 BQ–BZ | |
| Trạng thái style | Màu nền ô ORDER RECAP | F1 KPI | |
| Nhà máy hiện tại | F3 ORDER RECAP | F1, F2 (tên sheet), FAB | Có ghi chú MOVED FACT |

Khi hai nguồn mâu thuẫn: không ghi đè; ghi `etl.data_issue` (rule `XSRC_MISMATCH`) và hiển thị trong `mart.v_reconciliation_reported_vs_computed`.

## 7. Chuẩn hoá & hợp nhất

| Nguồn | Xử lý | Bảng đích |
|---|---|---|
| F1 1 dòng/style | Tách: style_order (thuộc tính tĩnh), production_snapshot (số liệu theo ngày), production_plan, milestone_event (FPP/INLINE/TOP), style_trim (LOGO STATUS). **Bỏ** dòng subtotal/total/KPI | nhiều bảng |
| F2 lưới block | Trải phẳng (unpivot) block → color×size; ORDER → order_qty_size; lô → shipment + shipment_line; mẫu → sample_dispatch(+line). Bỏ các dòng TTL/BAL | |
| F3/F4 block 4 dòng × 120 cột | Gom 4 dòng thành 1 style_order; dòng màu → style_order_color; 40 cột milestone → milestone_event (unpivot); cột vật tư → style_fabric (chỉ khi FAB không có); 1ST–4TH SHIP chỉ dùng đối soát; pricing/payment → bảng (P) | |
| F3 DETAIL | **Không nạp** (dẫn xuất) — chỉ đối soát | |
| FAB(…) | 1 dòng = style_fabric (snapshot `as_of` theo tên sheet); cột lô tàu (AZ…) unpivot → fabric_shipment_line | |
| PDF | Nạp nội dung tham chiếu: milestone_type (10 bước), danh sách brand, (P) bảng tổ chức | |

- Lookup: brand, season, collection, line, item_type, factory(+alias), color(+alias), size, mode, milestone_type, status, supplier(+alias).
- Junction: style_order↔factory (theo thời gian), style_order↔trim_item, style_fabric↔fabric_shipment.
- Nhóm lặp: cột size (XS…2XL), cột lô 1ST–4TH SHIP, cột lô tàu vải, cột milestone → đều unpivot thành dòng.
- Phi chuẩn hoá có chủ đích: chỉ ở `mart` (view/materialized view) cho báo cáo; core không lưu tổng.
- **Không gộp** chỉ vì trùng tên cột: `SEASON` (FAB) ≠ collection; ETD vải ≠ ETD thành phẩm; `BAL` mỗi nơi một nghĩa.

## 8. Kế hoạch index
- FK đều có index (PostgreSQL không tự tạo).
- `style(style_no)` unique; `style_alias(alias_style_no)`; `factory_alias(alias_norm)`; `color_alias(alias_norm)` cho lookup nhanh khi nạp.
- `style_order(season_id, status_code)`, `style_order(etd_vn)` cho báo cáo lịch xuất.
- `shipment(etd)`, `shipment_line(soc_id)`.
- `milestone_event(style_order_id, milestone_code, round_no)`.
- `raw.cell(file_id, sheet_id)` + GIN trên `etl.data_issue(rule_code, status)` nếu khối lượng lớn.
