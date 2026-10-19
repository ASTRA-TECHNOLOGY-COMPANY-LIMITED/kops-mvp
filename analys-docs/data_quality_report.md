# Data Quality Report

Mức độ: 🔴 Cao (sai số liệu báo cáo / mất dữ liệu) · 🟠 Trung bình (cần làm sạch trước khi nạp) · 🟢 Thấp (thẩm mỹ, chuẩn hoá)

Phạm vi kiểm tra: toàn bộ ô của 5 file (F3b trùng). Các con số dưới đây được tính lại bằng script, không dựa trên mẫu, trừ khi ghi chú.

## 1. Lỗi số liệu tổng (🔴)

| ID | File / vị trí | Vấn đề | Bằng chứng | Ảnh hưởng |
|---|---|---|---|---|
| DQ-01 | F1 `26FW-CLGR` dòng 53, 70, 83, 122 | **Vùng SUM của subtotal theo nhà máy sai/chồng lấn**: HA HIEU `=SUM(L41:L51)` (đúng ra L49:L52), NATEXCO `=SUM(L46:L82)` (đúng L71:L82), TRUONG PHUC `=SUM(L56:L69)` (bỏ sót dòng 54–55, lẫn dòng TIẾN THÀNH) | Grand total ORDER hiển thị **106,681** vs tổng thực **62,357**; OUTPUT 102,336 vs 60,289; INSPECTION 100,143 vs 58,972; SHIPPED 98,827 vs 57,948. Subtotal HA HIEU hiển thị 10,130 vs thực 1,440; NATEXCO 44,524 vs 5,920 | KPI dòng 1–3 và tỉ lệ % (dòng 123) sai |
| DQ-02 | F1 dòng 122 | Nhãn "6 FACTORY" nhưng dữ liệu có 8 nhà máy (TIẾN THÀNH, FG BAC GIANG nằm trong khối TRUONG PHUC/NATEXCO) | Đếm cột FACTORY | Subtotal theo nhà máy sai đối tượng |
| DQ-03 | F3/F4 `ORDER RECAP` dòng GRAND TOTAL | `#REF!` ở 40+ cột tổng (BO…DP) | Dòng 594 (F3) | Không có tổng vật tư/thanh toán |
| DQ-04 | F3 `DETAIL` cột E (FILE NO) | 100% `#REF!` (`=VLOOKUP(A13,#REF!,4,0)`) | 110/110 dòng | Mất liên kết file |
| DQ-05 | F3 `ORDER RECAP` cột BY, BZ | `#DIV/0!` ở 531 ô (`=BW/BU` khi BU trống) | Fill 531 | Cột tính toán vô nghĩa |
| DQ-06 | F3 `ORDER RECAP` cột BL dòng 4 mỗi block | `=#REF!` | Mọi block | |
| DQ-07 | F1/F2/F3 SHIPPED | Ba giá trị khác nhau cho cùng style (xem business_analysis §5.4); chỉ 21/100 style F1 = F3 | Bảng so sánh 3 chiều | Không có "một nguồn sự thật" |
| DQ-08 | F1 vs F3 vs F2 ORDER QTY | 4 style lệch số lượng (CHF3MPT6334, CHF3WPT6745, CHF3WSK6751, CHF3MJK6301) | 226 pcs chênh F1–F3 | Sai kế hoạch nếu chọn nhầm nguồn |

## 2. Định danh & tham chiếu (🔴/🟠)

| ID | Vấn đề | Chi tiết |
|---|---|---|
| DQ-10 🔴 | Mã style mâu thuẫn giữa file | CHF4WHP6851 ↔ CHF4WSK6851; CHF4WHP6852 ↔ CHF4WSK6852 (business_analysis §5.2) |
| DQ-11 🟠 | Mã style sai định dạng | `CHFWWT6817` (F2, thiếu chữ số mùa), `CHFG2WIT7957` (F4, 12 ký tự). Regex chuẩn đề xuất: `^CH[A-Z][0-9][MWU][A-Z]{2}[0-9]{4}$` |
| DQ-12 🟠 | Số thứ tự NO mâu thuẫn | F1 `7` vs F3 `F8` cho CHF3WVT6708 (F1 bị mất tiền tố, kiểu số) |
| DQ-13 🟠 | F2 số block trùng/nhảy | DM(27) có hai block `24)`; TP(16) hai block `19)`, `20)`; NATEXCO bắt đầu từ `2)`; TBM có `28)` hai lần, thiếu `34)` |
| DQ-14 🟠 | F2 style lặp ở nhiều sheet | CHE4WJK5843, CHE4WVT5847, CHE4UNW5485, CHE4MWT5406 xuất hiện 2 lần ở TP(16) và 1 lần ở NATEXCO(15) (block rỗng); CHF4WWT6818 có ở HA HIEU (có dữ liệu) và NATEXCO (rỗng) |
| DQ-15 🟠 | Tên nhà máy nhiều biến thể | xem business_analysis §5.5; dấu tiếng Việt không nhất quán (`TIẾN THÀNH`/`TIEN THANH`) |
| DQ-16 🟠 | Không có mã nhà máy, mã màu, mã lô xuất, số PO/invoice | Mọi liên kết phải dựa trên tên/nhãn văn bản |

## 3. Kiểu dữ liệu & định dạng (🟠)

| ID | Cột | Vấn đề | Ví dụ |
|---|---|---|---|
| DQ-20 | Ngày (F1 ETD VN, FPP CFMD, TOP SMPL, EXFACT ESTIMATED; F3 hầu hết cột milestone) | Trộn kiểu datetime và text tự do; text chứa nhiều sự kiện, thiếu năm | `7/29 + 7/31`, `8/1 SENT\n8/3 CMMT`, `1ST: ETD 08.12 - ETA 08.18, 2ND: ETD 09.10…`, `9/30ETD?`, `FACT SHIPPABLE: 6/15 EX-FACT`, `SAME AS 26SS` |
| DQ-21 | F3 milestone cột | Giá trị `00:00:00` (time 0) do VLOOKUP trả ô rỗng → hiển thị như ngày | DETAIL dòng 19 |
| DQ-22 | F4 ETD | 5 style ETD đầu năm 2026 trong mùa 27SS (ETD khác: 01–04/2027) → nghi sai năm | CHG1WJK7504 `2026-01-17`, CHG2WJK7604, CHG2MST7238, CHG2WST7651, CHFG2WIT7957 |
| DQ-23 | F2 nhãn lô xuất | ETA trước ETD; format không thống nhất | `9/20ETD-6/25ETA SEA` (25 ô), `8/12ETD- 8/18ETA` vs `8/12ETD-8/18ETA`, `10/15ETD-10/20ETA` (thiếu mode) |
| DQ-24 | Số lượng dạng text | `150P`, `200p`, `260720 REDUCED 170P➜136P` trong cột qty/ghi chú | F3 cột J/I |
| DQ-25 | Đơn giá vải (FAB) | Trộn số và text thay đổi giá `5500->5000`; **không có đơn vị tiền tệ** — trung vị theo C/O: KR ≈ 2,400 (KRW?), CN ≈ 4.19 (USD?), VN ≈ 0.85 (USD?) | 13 ô text |
| DQ-26 | Khổ vải | Text có ký hiệu inch `58"`, hoặc `PC` | FAB cột U |
| DQ-27 | C/O | Khoảng trắng đầu `' KR'`; `CH` (4 dòng ở 0519) nghi là `CN` | FAB cột T |
| DQ-28 | Mã màu | Viết nhiều kiểu, lỗi chính tả, ghi chú lẫn trong ô | `KHAKI GREY`/`K.GREY`/`K/GREY`/`K GREY`; `L/BEIGE`/`L.BEIGE`/`LIGHT BEIGE`/`LIGHT BIEGE`; `CHARCOAL`/`CHACOAL`; `OAT MEAL`/`OATMEAL`; `WHIE`; `MALANGE`; `CREAM\n(BE: INDIE PINK)`; `BEIGE???` |
| DQ-29 | Trường text đa dòng chứa cấu trúc | LOGO STATUS chứa danh sách trim có mã + kích thước | `1) H.T LOGO(1):\n-AP_TR02 H.T LOGO 3CM\n2) WAPPEN(1):\n-AP_WP16 2.2*8CM WAPPEN` |
| DQ-30 | Text đa ngôn ngữ | Tiếng Hàn, tiếng Việt có dấu, tiếng Anh trong cùng cột | 품명, `남)우븐디테일패치 후드 자켓`, `TIẾN THÀNH` → cần UTF-8, collation phù hợp |

## 4. Bố cục bảng tính gây rủi ro khi trích xuất (🟠)

- **Thông tin mã hoá bằng màu nền ô**: trạng thái style (KOREA SHIP OUT 99, CANCEL 3, PENDING 2 … trong F3; F4 chủ yếu chưa tô màu) và màu nhà máy (một số dùng theme color nên không đọc được mã RGB). Mất khi export CSV.
- **Block nhiều dòng / lưới ngang** (F2: 4 block/hàng; F3: 4 dòng/style; 120 cột) → không thể đọc bằng `read_excel` thông thường; cần parser theo template.
- **Header lặp & dòng tiêu đề trong vùng dữ liệu** (giá trị `COLOR `, `ORDER Q'TY`, `NOT FIXED` lọt vào cột COLOR khi parse thô).
- **Block khuôn rỗng**: F2 41 block, F3 9 block, F4 ~14 block.
- **Sheet ẩn chứa dữ liệu thật**: F2 `MTT(11)`, `HA HIEU(4)`; F3 `FAB(260519)`.
- **Merge cells**: 1,674 (F3), 1,995 (F4), 116–273/sheet (F2).
- Hàng nghìn công thức; giá trị lấy từ cache — nếu file chưa được tính lại trước khi lưu, giá trị có thể cũ. [R] Lưu cả công thức và giá trị cache.
- Ảnh thiết kế nhúng (170/164 ảnh) — dữ liệu phi cấu trúc, có thể trích riêng.
- Named range rác `À` = `#REF!` (F1, F2).

## 5. Dữ liệu thiếu (fill rate trên vùng style của ORDER RECAP F3)

| Nhóm cột | Fill | Nhận xét |
|---|---|---|
| Style, factory, color, qty, ETD, RDD | ~100% | Đủ |
| Milestone mẫu (R–AS) | 40–100% tuỳ cột | Text tự do |
| Line/worker, cutting, output, finishing (AT–BD) | 8–16 ô | Gần như không dùng |
| Pricing (BE–BG), FOB (CC chỉ có "KOREA"), PO NO (CF/CG) | ≤ 12 ô | Chưa dùng / ở file khác |
| Payment (CV–DF, DO–DP) | 12 ô (toàn 0) | Chưa dùng |
| F1 REMARK | 0% | Bỏ |
| F1 ETD/ETA ESTIMATED | 64% | |

## 6. Trùng lặp

| ID | Loại | Chi tiết | Xử lý đề xuất |
|---|---|---|---|
| DUP-1 | File | F3 và F3b giống hệt (MD5) | Nạp 1 lần; registry phát hiện qua hash |
| DUP-2 | Snapshot | FAB(260519) và FAB(0615): 937 dòng khớp khoá (style+color+part); 66 đổi nhà máy, 179 đổi PO yard | Nạp như 2 snapshot có `as_of_date` |
| DUP-3 | Dòng | FAB có 25–28 khoá (style+color+part) lặp trong cùng sheet | Cần thêm supplier/fabric vào khoá hoặc số dòng nguồn |
| DUP-4 | Dữ liệu dẫn xuất | DETAIL = VLOOKUP của ORDER RECAP | Không nạp DETAIL như nguồn; chỉ dùng để đối soát |
| DUP-5 | Cùng sự kiện ở nhiều file | ORDER QTY/SHIPPED ở F1, F2, F3 | Chọn nguồn hệ thống (system of record) cho từng thuộc tính (xem database_design §6) |

## 7. Bất thường nghiệp vụ cần xem xét

- 64/110 style F1 có SHIPPED > ORDER (over-ship 0.3–3%); 1 style shortage lớn (CHF4WPT6846 F2: 100/330, CHF4MJK6403 204/400, CHF4WJK6804 134/300, CHF4MJK6404 244/400 — đang trong tiến trình xuất).
- F1 có style INSPECTION > OUTPUT (ví dụ CHF4WHP6850 output 331, inspection 333).
- F2 có hai con số "shipped" trong cùng block không khớp nhau: ví dụ CHF3WLT6732 ô SHIPPED ở dòng `S/DATE` (cộng các ô cumulative theo màu) = 555 (BAL −45), trong khi dòng `TOTAL SHIPPED Q'TY+SMPL QTY` = 610 (cộng chi tiết lô + mẫu). [R] Bỏ qua mọi ô tổng nhập/tính trong file, tính lại từ dòng chi tiết.

## 8. Khuyến nghị bảo toàn giá trị nguồn & log
1. Lưu **giá trị gốc nguyên văn** (text, kiểu, công thức, toạ độ ô, màu nền) ở tầng raw cho mọi ô được trích.
2. Mỗi cột chuẩn hoá có cột `*_raw` hoặc liên kết `source_cell_id` để truy vết.
3. Bản ghi không parse được → bảng `etl.data_issue` (file, sheet, ô, quy tắc vi phạm, mức độ, trạng thái xử lý) — không loại bỏ âm thầm.
4. Giá trị mơ hồ (ngày không có năm, ETA < ETD, màu không map được) → nạp với cờ `needs_review` thay vì đoán.
5. Excel error (`#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`) → NULL ở tầng chuẩn hoá + issue log; giữ chuỗi lỗi ở raw.
