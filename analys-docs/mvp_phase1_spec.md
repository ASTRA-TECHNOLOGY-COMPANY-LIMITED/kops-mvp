# MVP Phase 1 — Spec mở rộng data warehouse: tiến độ may, kiểm hàng, dự báo

Tài liệu này là **đặc tả** cho các đề xuất trong `review_inspection_production.md` §3. Người làm (người hoặc agent) code theo tài liệu này; kế hoạch và thứ tự task ở `plans/MVP_PHASE1_PLAN.md`.

- Nền tảng hiện có: `dw/` (DuckDB, các lớp `etl → raw → stg → core → mart`, dashboard HTML, 19 golden test). Xem `dw/README.md`.
- Quy tắc chung: `GUIDELINES.md`. Đặc biệt: file nguồn chỉ đọc; tổng luôn tính từ chi tiết; mọi bất thường ghi vào `etl.data_issue` kèm vị trí; không tự quyết câu hỏi nghiệp vụ.
- Câu hỏi còn mở liên quan: Q01, Q02, Q03, Q05, Q06, Q11, Q15 (`open_questions.md`, Ưu tiên 1–2). Code theo giả định ghi ở đó, để cấu hình được.

## 1. Mục tiêu và phạm vi

**Mục tiêu:** dashboard cho biết **đúng** mỗi style đang ở đâu (đặt → cắt → may → kiểm đạt → xuất), **khi nào xong**, và **dữ liệu của nhà máy nào đang thiếu**.

| Trong Phase 1 | Ngoài Phase 1 |
|---|---|
| Nạp báo cáo sản xuất ngày (template CHALLENGER và HAGACO) | Tỷ lệ lỗi, scorecard kiểm viên (chờ Q24) |
| Nạp SL kiểm đạt theo ngày từ bảng kiểm | Năng suất theo công nhân / xếp hạng nhà máy theo năng suất (chờ Q41) |
| Dự báo ngày xong bằng sản lượng các ngày gần nhất | Lịch T&A, cảnh báo qua Zalo/email |
| Độ tươi dữ liệu theo nhà máy và theo style | Nạp sheet FAB, checklist vật tư |
| Funnel đặt → cắt → vào chuyền → ra chuyền → kiểm đạt → xuất | App nhập liệu, đăng nhập, RLS thật |
| Chiều khách/brand (CHALLENGER, 8 SECONDS) | Buyer portal |
| Yêu cầu đổi ETD trong ghi chú bảng kiểm → hàng chờ duyệt | Áp thay đổi tự động |
| Metadata file lấy từ nội dung và tên file (không phụ thuộc thư mục cục bộ) + kiểm tra file đặt nhầm | Tự đồng bộ từ Google Drive của KLMAS (backlog D-13, chờ Q08) |

## 2. Nguồn file và metadata

**Bản gốc nằm trên Google Drive của KLMAS.** `raw-docs/` là bản tải về cục bộ, tên file giữ nguyên như trên Drive. Cây thư mục dưới đây do đội dự án tự sắp cho dễ tìm; KLMAS không dùng cây này và Drive có cấu trúc khác. Vì vậy metadata của file lấy từ **nội dung và tên file** trước; thư mục cục bộ chỉ là phương án cuối. Khi sau này đồng bộ thẳng từ Drive, file có thể nằm ở bất kỳ thư mục nào mà pipeline vẫn phải nhận đúng.

Cây thư mục cục bộ:

```
raw-docs/
├── COMPANY/ · MEETINGS/                                 # hồ sơ công ty, biên bản họp
├── ORDER/<BRAND>/<MÙA>/                                 # ORDER RECAP
├── TRACKING/<BRAND>/<MÙA>/                              # Production & Shipping Status, Shipment Status
├── PRODUCTION/<BRAND>/<MÙA>/<NHÀ MÁY>/                  # báo cáo ngày, brand trực tiếp (CHALLENGER)
├── PRODUCTION/<VENDOR>/<BRAND>/<MÙA>/<NHÀ MÁY>/         # báo cáo ngày, brand qua vendor (DHG/8 SECONDS/26FW/HAGACO)
├── INSPECTION/ORDER_TRACKING/<BRAND>/<MÙA>/             # bảng theo dõi kiểm (đơn KLMAS)
├── INSPECTION/THIRD_PARTY/ · FORMS/ · SAMPLES/          # kiểm hàng bên thứ ba, mẫu phiếu, mẫu báo cáo
├── inbox/*.eml                                          # email thật (không commit)
└── _DUPLICATES/ · _REORG/                               # bị pipeline bỏ qua
```

Cách xác định metadata của một báo cáo ngày (theo thứ tự ưu tiên):

| Trường | 1. Lấy từ | 2. Nếu không có | 3. Nếu vẫn không có |
|---|---|---|---|
| Nhà máy | Tiêu đề ô A1 (`26FW- MTT FACT…`, `26FW- HAGACO-…`) | Tên file (`(CHALLENGER - MTT)`) | Thư mục cuối |
| Brand | Tên file (`CHALLENGER`, `CLGR`) hoặc ánh xạ vendor trong `config.VENDOR_BRAND` (`DHG` → `8 SECONDS`) | Thư mục cục bộ (ghi `METADATA_FROM_FOLDER`, INFO) | `CHALLENGER` |
| Vendor/khách | Tên file (`DHG-HAGACO`) qua `config.VENDOR_BRAND` | Thư mục cục bộ `PRODUCTION/<X>/` khi có cấp brand bên dưới | = brand |
| Mùa | Tên file (`26FW`) | Thư mục cục bộ | Lỗi `SEASON_UNKNOWN` |

Mô tả đầy đủ cấu trúc: `raw-docs/README.md` (sắp xếp lại ngày 19/10/2026). Pipeline đã quét đệ quy và bỏ qua thư mục bắt đầu bằng `_`. Khi 3 nguồn cho nhà máy không khớp nhau (trường hợp thật trước đây: file MTT đặt trong thư mục `DONG MY/`, nay đã chuyển vào `_DUPLICATES/`), dùng nguồn ưu tiên cao nhất và ghi `FILE_FOLDER_MISMATCH` (WARN). File trùng nội dung (sha256) → `DUPLICATE`, không nạp lại.

## 3. Nguồn mới và hợp đồng dữ liệu

### 3.1 Báo cáo sản xuất ngày (`daily_production`)

**Bố cục [Q]:** mỗi sheet là một ngày. Header ở 2 dòng: dòng nhóm (`CUTTING/SL CẮT`, `SEND PRINTING/ EMB/ PL`, `RETURNED PRINTING/ EMB`, `IN PUT/SL VÀO CHUYỀN`, `OUT PUT/ SL RA CHUYỀN`) và dòng con (`TODAY`, `TTL (ĐẾN HÔM NAY)`, `BAL`). Dòng đầu của mỗi style mang style, chuyền, số công nhân, ETD/RDD, màu; các dòng sau chỉ có size. Có dòng tổng theo màu (không có size), dòng `TTL`, dòng `GRAND TOTAL`.

**Bắt buộc parse theo nhãn header, không theo vị trí cột.** Template CHALLENGER có 47–48 cột; template HAGACO có 41 cột, không có cột in/thêu, có thêm `FINAL ETD HAI PHONG`, `RDD`, `RMKS`.

| Cột đích (`raw.daily_prod_row`) | Nhận diện header | Ghi chú |
|---|---|---|
| `style_raw` | `S/NO` | Kế thừa xuống các dòng dưới. Template HAGACO có thể chứa `RDD 1ST: 10/27` sau xuống dòng: tách ra `style_note` |
| `line_no`, `workers` | `LINE NO…`, `WORKERS…` | Kế thừa trong cùng style |
| `etd`, `rdd` | `ETD`, `FINAL ETD…`, `RDD` | Chỉ để tham khảo; nguồn chính vẫn là ORDER RECAP |
| `color` | `COLOR` | Kế thừa; bỏ dòng có color = `TTL` |
| `size_code` | `SIZE` | Không có size → dòng tổng → bỏ. Alias XXL → 2XL |
| `order_qty` | `ORDERQTY` / `ORDER/QTY` | |
| `cut_today`, `cut_ttl` | nhóm CUTTING, con TODAY / TTL | |
| `print_send_ttl`, `print_return_ttl` | nhóm SEND/RETURNED PRINTING, con TTL | Chỉ template CHALLENGER |
| `input_today`, `input_ttl` | nhóm IN PUT | |
| `output_today`, `output_ttl` | nhóm OUT PUT | |
| `factory`, `brand`, `vendor`, `season` | §2 | |
| `report_date`, `sheet`, `sheet_hidden`, `file_id`, `row_no` | §3.2 | |

Giá trị lỗi Excel (`#REF!`, `#DIV/0!`) → NULL + issue `EXCEL_ERROR` (INFO, gộp theo sheet). Không nạp các cột BAL (là công thức).

### 3.2 Ngày báo cáo

Ô ngày trong sheet **không tin được** [Q]: TBM có serial đảo ngày/tháng (45664 = 07/01/2025 thay vì 01/07/2026), text `13/7/2025` sai năm; HAGACO có năm 2024.

Thuật toán:
1. **Quy ước tên sheet theo file:** nếu có sheet nào mà số đầu > 12 thì file dùng `dd.mm` (TBM), ngược lại dùng `m.d`.
2. **Năm** = năm của mùa (26FW → 2026; mùa SS: tháng 7–12 là năm trước).
3. **Sửa lỗi gõ tháng:** duyệt sheet theo ngày tăng dần. Nếu ngày của một sheet lùi hơn 30 ngày so với sheet liền trước (vd. `13.01` sau `12.10`), dùng tháng của sheet liền trước rồi ghi `REPORT_DATE_FIXED` (INFO).
4. Tên sheet không phải ngày hợp lệ (`7.281`, `Sheet1`): bỏ qua, ghi `SHEET_SKIPPED` (INFO).
5. Ô ngày trong sheet là datetime hợp lệ nhưng lệch hơn 1 ngày so với ngày suy ra → ghi `REPORT_DATE_CONFLICT` (WARN), vẫn dùng ngày suy ra từ tên sheet.
6. Hai sheet cùng ngày của cùng nhà máy (file khác nhau) → lấy file có `file_date` mới hơn.

### 3.3 Bảng kiểm hàng (`inspection_tracker`)

**Bố cục [Q]:** mỗi sheet là một nhà máy (`TP`, `HÀ HIẾU`, `FG`, `NATEXCO`, `MTT`, `MTTD`). Sheet `TP (2)`…`(5)` (ẩn) là các đợt cũ. Dòng 2 là header (`STYLE NO`, `COLOR`, `QUANTITY ORDER`…), dòng 3 là ngày kiểm. Ô style có thể là `CHF4WJK6801\n- VEST -` (style bộ). Cuối sheet có các dòng tổng A–G (đạt, đạt/QC, SL kiểm, SL lỗi, tỷ lệ lỗi, số kiểm viên, tên kiểm viên). Cột Remark có ETD và `REQUEST ETD m/d`.

| Bảng đích | Nội dung | Quy tắc |
|---|---|---|
| `raw.inspection_cell` | style, món (`VEST`/`JACKET`/rỗng), màu, ngày, SL đạt, sheet, ô | Nạp mọi sheet, kể cả sheet ẩn |
| `core.inspection_passed` | (style, món, màu, ngày) → SL đạt | Trùng giữa các sheet → lấy **max** một lần. **Chỉ nhận** khi nhà máy của sheet = nhà máy của style trong ORDER RECAP; không khớp thì bỏ và ghi `INSPECTION_STYLE_FACTORY_MISMATCH` (WARN) |
| `core.inspection_day` | (nhà máy, ngày) → SL kiểm (dòng C), số kiểm viên (dòng F) | **Không nạp tên kiểm viên** (dữ liệu cá nhân, chưa cần ở Phase 1) |
| `stg.inspection_remark` | `REQUEST ETD m/d` → đề xuất đổi ETD | Đưa vào `core.change_proposal`, nguồn `INSPECTION`, trạng thái `PENDING_REVIEW` |

**Không nạp** dòng D (SL lỗi) và E (tỷ lệ lỗi) vào core/mart cho tới khi có câu trả lời Q24; chỉ giữ ở raw.

Style bộ (Q11): SL đạt của style = **min** theo món (một bộ chỉ đủ khi có cả 2 món); vẫn hiển thị từng món trong Style 360.

### 3.4 Mã style

- Mỗi brand có quy tắc mã riêng (đặt trong `config.py`):
  - CHALLENGER: `^CH[A-Z][0-9][MWU][A-Z]{2}[0-9]{4}$`
  - 8 SECONDS: `^LEV-[0-9]{5}` (giữ phần sau `#` làm `style_variant`)
- Bổ sung alias chưa xác nhận (Q06): `CHE3WPT6986→CHF3WPT6986`, `CHE3WSK6754→CHF3WSK6754`, `CHE4MPT6441→CHF4MPT6441`, `CHE4WPT6842→CHF4WPT6842`. Áp alias ở mọi nguồn qua `core.style_key()`; ghi `STYLE_ALIAS_UNCONFIRMED`.

## 4. Quy tắc tính toán

### 4.1 Lần xuất hiện cuối (last-seen)

Nhà máy xoá style đã xong khỏi sheet ngày [Q], nên tiến độ của một (nhà máy, style, màu, size) là dòng ở **ngày báo cáo lớn nhất mà dòng đó còn xuất hiện**. Tiến độ style = tổng các dòng last-seen. Lưu kèm `last_seen_date` của style.

### 4.2 Chuỗi sản lượng ngày

`output_day(style, d)` = tổng `output_today` của style trong sheet ngày `d`. Nếu `output_today` trống mà `output_ttl` có, dùng chênh lệch `output_ttl` so với ngày báo cáo trước.

### 4.3 Dự báo ngày xong (thay `daily_output` của Production Status)

```
as_of        = last_seen_date của style (nguồn báo cáo ngày)
rate         = trung bình output_day của 3 ngày báo cáo gần nhất có output_day > 0, trong 10 ngày trước as_of
               (không có → default_daily_output = 45, confidence = LOW)
remaining    = order_qty (ORDER RECAP) − output_ttl (last-seen)
finish_date  = as_of + ceil(remaining / rate) ngày làm việc (thứ 2–thứ 7)
ready_date   = finish_date + ready_buffer_days (5 ngày lịch)
days_late    = ready_date − ETD VN
```

- `rate_window` (3) và `rate_lookback_days` (10) đặt trong `RULES`.
- **Chọn nguồn:** dùng báo cáo ngày khi `last_seen_date ≥ as_of của Production Status`; ngược lại dùng Production Status như hiện tại. Ghi nguồn vào `forecast_source`.
- **Độ tin cậy:** HIGH = có ≥ 3 ngày sản lượng và báo cáo cuối ≤ 2 ngày làm việc trước ngày build; MEDIUM = có dữ liệu nhưng không đạt HIGH; LOW = dùng mặc định.
- `remaining ≤ 0` → không dự báo, style coi như đã may xong.

### 4.4 Độ tươi dữ liệu

`today` = ngày build, ghi đè bằng biến môi trường `KOPS_TODAY` (để test cố định).

| Mức | Theo nhà máy: số ngày làm việc từ báo cáo ngày gần nhất tới `today` |
|---|---|
| FRESH | ≤ 2 |
| STALE | 3–5 |
| DARK | > 5, hoặc nhà máy có style đang chạy mà chưa từng có báo cáo |

Theo style đang chạy, chưa xuất đủ:
- `NO_REPORT`: chưa từng xuất hiện trong báo cáo ngày.
- `STOPPED_REPORTING`: last-seen output < SL đặt **và** nhà máy đó đã có báo cáo ở ngày sau `last_seen_date` (style biến mất khi chưa xong).
- `STALE`: theo mức của nhà máy.

### 4.5 Funnel số lượng

Mỗi style (và mỗi màu × size khi có): `ordered` (ORDER RECAP; màu × size từ Shipment Status) → `cut` → `input` → `output` (báo cáo ngày, last-seen) → `passed` (kiểm đạt) → `shipped` (Shipment Status, không gồm mẫu) + `sample`.

Cờ (issue hoặc cột trong mart):
- `CUT_SHORT`: cut < ordered × (1 − tolerance) và nhà máy đã có báo cáo sau ngày cut cuối cùng thay đổi.
- `OUTPUT_GT_CUT`: output > cut.
- `PASSED_GT_ORDER`: passed > ordered × (1 + tolerance), với tolerance = `qty_tolerance_pct`.
- `OUTPUT_MISMATCH_PS`: output last-seen khác output của Production Status, khi hai ngày nguồn cách nhau ≤ 1 ngày.

## 5. Mô hình dữ liệu bổ sung

| Lớp | Bảng | Khoá / ghi chú |
|---|---|---|
| raw | `daily_prod_row` | file_id, sheet, row_no |
| raw | `inspection_cell`, `inspection_day_raw` | file_id, sheet, row_no, col_no |
| stg | `inspection_remark` | file_id, style, text |
| core | `daily_progress` | (brand, season, factory, style_no, color, size_code), last-seen |
| core | `daily_output_series` | (brand, season, factory, style_no, report_date) |
| core | `inspection_passed`, `inspection_day` | §3.3 |
| core | `style_order` + cột `brand`, `vendor` | brand từ ORDER RECAP = CHALLENGER |
| core | `style_external` | style chỉ có trong báo cáo ngày của brand khác (8 SECONDS): không có ORDER RECAP, lấy SL đặt từ báo cáo ngày |
| mart | `style_forecast` | §4.3, mỗi style một dòng |
| mart | `factory_freshness`, `style_freshness` | §4.4 |
| mart | `style_funnel`, `funnel_assortment` | §4.5 |
| mart | `style_360` | thêm cột từ `style_forecast` và `style_funnel`; `health` dùng dự báo mới |

Mọi bảng mới có `brand`. Truy vấn mart cho dashboard nhận tham số brand; mặc định CHALLENGER (Q15).

## 6. Thay đổi dashboard

| Nơi | Thay đổi |
|---|---|
| Thanh trên cùng | Thêm chọn **brand** cạnh chọn mùa |
| Tổng quan | Thẻ "Độ tươi dữ liệu": số nhà máy FRESH / STALE / DARK |
| Control Tower | Bảng "Độ tươi theo nhà máy" (báo cáo gần nhất, số ngày, style không có báo cáo). Danh sách "cần chú ý" dùng dự báo mới, thêm cột nguồn dự báo và độ tin cậy |
| Style 360 | Funnel (thanh ngang 6 bước) + biểu đồ cột sản lượng ngày + ma trận màu × size thêm cut/output/passed. Style bộ hiển thị từng món |
| Thay đổi & Email | Đề xuất đổi ETD từ bảng kiểm (nguồn INSPECTION) chung hàng chờ với email |
| Đối soát & chất lượng | Mã issue mới (§7); bảng "Output: báo cáo ngày vs Production Status" |
| Nguồn & lineage | Cột brand, nhà máy, ngày báo cáo nhỏ nhất và lớn nhất của từng file |

Không hiển thị tỷ lệ lỗi hay tên kiểm viên.

## 7. Mã issue mới

`FILE_FOLDER_MISMATCH`, `SEASON_UNKNOWN`, `REPORT_DATE_FIXED`, `REPORT_DATE_CONFLICT`, `SHEET_SKIPPED`, `EXCEL_ERROR`, `INSPECTION_STYLE_FACTORY_MISMATCH`, `CUT_SHORT`, `OUTPUT_GT_CUT`, `PASSED_GT_ORDER`, `OUTPUT_MISMATCH_PS`, `STYLE_NOT_IN_ORDER` (đã có, nay áp cho cả báo cáo ngày và bảng kiểm).

## 8. Golden numbers mới (đo trên dữ liệu ngày 19/10/2026)

Chạy với `KOPS_TODAY=2026-10-19`. Mọi số dưới đây đã được tính bằng script độc lập. Nếu triển khai cho số khác, **phải giải thích trong PR** chứ không tự sửa test cho khớp.

| # | Kiểm tra | Giá trị |
|---|---|---|
| G1 | File báo cáo ngày tìm thấy / trùng / nạp (2 bản trùng đã nằm trong `_DUPLICATES/`, bị bỏ qua) | 7 / 0 / 7 |
| G2 | Ngày báo cáo cuối theo nhà máy | DONG MY 28/09, HA HIEU 28/09, MTT 02/10, NATEXCO 08/09, TAN BINH MINH 15/10, TRUONG PHUC 14/10, HAGACO 15/10 |
| G3 | Sheet TBM `13.01`, `14.01`, `15.01` | Thành 13/10, 14/10, 15/10, có `REPORT_DATE_FIXED` |
| G4 | Style CHALLENGER có trong báo cáo ngày (sau alias Q05 + Q06) | 101, khớp ORDER RECAP cả 101 |
| G5 | Style CHALLENGER đang chạy không có báo cáo ngày nào (`NO_REPORT`) | 9 |
| G6 | CHF4MPT6444 (W33): output last-seen / rate / ready / days_late | 190 / 50 / 2026-10-25 / 18 |
| G7 | CHF4WPT6846: output / ready / days_late | 290 / 2026-10-21 / 14 |
| G8 | Mức độ tươi NATEXCO | DARK |
| G9 | Bảng kiểm: dòng bị loại vì sai nhà máy | 12 dòng (CHF4WJK6801 ở sheet HÀ HIẾU, FG, MTTD) |
| G10 | `PASSED_GT_ORDER` | CHF4WJK6991 (1.381 / 1.000), CHF4WJK6801-JACKET (392 / 350) |
| G11 | Đề xuất đổi ETD từ Remark bảng kiểm | 8 |
| G12 | HAGACO / 8 SECONDS, sheet 15/10 | 8 style, đặt 12.740, ra chuyền 10.230 |
| G13 | 19 golden test cũ | Vẫn PASS (riêng giá trị days_late W33 trong test cũ đổi từ 49 sang 18, ghi chú lý do) |
