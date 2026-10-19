# Document Inventory — file nguồn KLMAS

- Thư mục nguồn: `raw-docs/` (quét đệ quy, chỉ đọc; không có trong git, xin PO để lấy). Biên bản họp KOPS lần 1 (docx) chưa có trong manifest dưới đây; nội dung biên bản được dùng trực tiếp trong `roadmap.md` và `prototype/KOPS_prototype_architecture.md`.
- Ngày phân tích: 2026-10-16
- Tổng số file phát hiện: **6** (5 Excel, 1 PDF). Không có thư mục con.
- Không file nào bị khoá mật khẩu, hỏng hay không đọc được.
- Công cụ: `openpyxl` (xlsx), `pyxlsb` + bản chuyển đổi LibreOffice **trên bản sao** (xlsb), `pdftotext`/`pdfinfo`/render trang (PDF). Không chạy macro; công thức chỉ được đọc như văn bản, giá trị lấy từ cache đã lưu trong file.

> Quy ước: **[Q]** = quan sát trực tiếp từ dữ liệu; **[S]** = suy luận; **[R]** = khuyến nghị.

## 1. Manifest

| # | File | Định dạng | Kích thước | MD5 | Trạng thái xử lý |
|---|------|-----------|-----------|-----|------------------|
| F1 | `261012 HUONG) 26FW CLGR PRODUCTION AND SHIPPING STATUS(~10.10).xlsx` | xlsx | 58 KB | b8c5d001… | Đã xử lý toàn bộ (1 sheet) |
| F2 | `261014R2 MJ) 26FW CHALLENGER ALL STYLES SHIPMENT STATUS.xlsx` | xlsx | 434 KB | c4771db0… | Đã xử lý toàn bộ (6 sheet, gồm 2 sheet ẩn) |
| F3 | `261015 MJ) 26FW CHALLENGER ORDER RECAP.xlsb` | xlsb | 6.5 MB | 4fc356d2… | Đã xử lý toàn bộ (4 sheet, gồm 1 sheet ẩn) |
| F3b | `261015 MJ) 26FW CHALLENGER ORDER RECAP (1).xlsb` | xlsb | 6.5 MB | 4fc356d2… | **Bản trùng y hệt F3 (cùng MD5)** — không phân tích lại |
| F4 | `261015 MJ) 27SS CHALLENGER ORDER RECAP.xlsb` | xlsb | 18.9 MB | 7587e361… | Đã xử lý toàn bộ (2 sheet) |
| F5 | `261012 KLMAS 프로파일(KR).pdf` | PDF 1.6 (Adobe Illustrator) | 1.9 MB | 086b1f6d… | 19 trang; trích text + xem ảnh trang. Một số text nằm trong ảnh (chưa OCR đầy đủ) |

Quy ước tên file [Q/S]: `YYMMDD[Rn] <người phụ trách>) <mùa> <brand> <loại báo cáo>` — ví dụ `261014R2` = ngày 14/10/2026 bản sửa 2; `HUONG`, `MJ` là người lập; `CLGR` = CHALLENGER; `(~10.10)` = dữ liệu tính đến 10/10.

## 2. Chi tiết từng file

### F1 — 26FW CLGR Production and Shipping Status (HUONG, 12/10/2026)

| Mục | Nội dung |
|---|---|
| Sheet | `26FW-CLGR` (visible), A1:AX128, 54 ô merge, 421 công thức, 91 quy tắc conditional formatting, cột V ẩn, autofilter A5:AC128, named range lỗi `À` → `#REF!` |
| Mục đích | Bảng theo dõi tiến độ sản xuất & xuất hàng theo **style** cho mùa 26FW, nhóm theo nhà máy |
| Bố cục | Dòng 1–4: KPI tổng; dòng 5: header; dòng 6–120: 110 dòng style; 6 dòng subtotal theo nhà máy (`TOTAL n STYLES`); dòng 122 grand total; 123 tỉ lệ %; 124 `DAILY STATUS` |
| Cột chính | NO, MODE (M/W/UNI), TYPE (26FW-FALL/WINTER/ONLINE/REORDER), STYLE NO, ITEMS, FACTORY, ETD VN, RDD, FPP CFMD, INLINE SMPL, TOP SMPL, ORDER Q'TY, ONE DAY, OUTPUT, INSPECTION, SHIPPED Q'TY, 3 cột BAL (công thức), LOGO STATUS, PLAN MTR(FAB) SHIP DATE, CUTTING/INPUT/SEWING FINISH PLAN, EXFACT/ETD/ETA ESTIMATED, REMARK |
| Số bản ghi | 110 style; 8 nhà máy thực tế (DONG MY 28, TAN BINH MINH 37, TRUONG PHUC 15, MTT 13, NATEXCO 11, HA HIEU 4, TIẾN THÀNH 1, FG BAC GIANG 1) |
| Chất lượng | **Lỗi công thức subtotal nghiêm trọng** (xem data_quality_report DQ-01): grand total ORDER = 106,681 trong khi tổng thực = 62,357. Ngày lẫn text (`9/30ETD?`, `7/29 + 7/31`), REMARK rỗng 100%, cột RDD thứ hai (V) rỗng & ẩn |
| Quan hệ | Cùng tập style với F2/F3 (100/110 style khớp cả 3 file) |
| Độ tin cậy | Cao về cấu trúc; số tổng **không đáng tin** |

### F2 — 26FW Challenger All Styles Shipment Status (MJ, 14/10/2026, R2)

| Mục | Nội dung |
|---|---|
| Sheet | `DM(27)`, `MTT(11)` (**ẩn**), `HA HIEU(4)` (**ẩn**), `TP(16)`, `NATEXCO(15)`, `TBM(35)` — mỗi sheet = 1 nhà máy, số trong ngoặc = số style dự kiến; A1:BR~300; 116–273 merge/sheet; ~8,800 công thức |
| Mục đích | Chi tiết **color × size** của đơn hàng, từng lô xuất (theo ETD/ETA/phương thức) và mẫu (sample) gửi đi, cho từng style |
| Bố cục | **Không dạng bảng**: lưới 4 block ngang × N block dọc, mỗi block 11 cột (S/NO, COLOR, 6 cột size, TTL, SHIPPED, BAL). Trong block: tiêu đề `n) STYLE PRODUCTION DETAIL SHIP STATUS` → header size → các dòng ORDER theo màu → dòng `S/DATE TTL` → các lô xuất (nhãn kiểu `8/12ETD-8/18ETA SEA`) → `TOTAL SHIPPED Q'TY+SMPL QTY` → `SMPL LIST` → `BAL Q'TY` → các dòng mẫu (`8/8 SHIPPING SMPL`, `PHOTO SMPL`) |
| Số bản ghi | 144 block; **103 block có dữ liệu** (103 style), 41 block rỗng/khuôn mẫu. Sau khi trải phẳng: 2,342 dòng (846 ORDER, 997 SHIPMENT, 499 SAMPLE theo color×size) |
| Size run | XS–XL; XS–2XL; S–XXL; `F` (free size) |
| Phương thức vận chuyển | SEA, AIR, HC (hand carry — [S]) |
| Chất lượng | Block đánh số trùng/nhảy; mã style sai `CHFWWT6817`; 4 style mùa trước (CHE4…) lặp lại ở 2 sheet; màu viết nhiều kiểu (K.GREY/K/GREY/KHAKI GREY…); nhãn lô có ETA trước ETD (`9/20ETD-6/25ETA`) |
| Kiểm chứng | Bộ parser tái tính 100% block: tổng ORDER và tổng SHIPPED+SMPL khớp ô tổng của file |
| Độ tin cậy | Cao (số liệu chi tiết nhất hiện có) |

### F3 — 26FW Challenger Order Recap (MJ, 15/10/2026) — F3b là bản sao

| Mục | Nội dung |
|---|---|
| Sheet | `ORDER RECAP` (A1:DP639, 1,674 merge, 11,320 công thức, 170 ảnh nhúng — hình vẽ thiết kế), `DETAIL` (A1:V126, 1,939 công thức), `FAB(260519)` (**ẩn**, snapshot 19/05), `FAB(0615)` (snapshot 15/06) |
| Mục đích | **File master của mùa**: danh sách style, màu, số lượng, nhà máy, toàn bộ milestone mẫu/vật tư/sản xuất, lô xuất, kế hoạch nguyên liệu, (khung) giá & thanh toán |
| ORDER RECAP | Mỗi style = **block 4 dòng** (dòng 1: mã style/nhà máy/màu 1; dòng 2: mô tả EN, line; dòng 3: tên tiếng Hàn; dòng 4: vải chính + loại mùa). 120 cột chia nhóm: QC SMPL, REFERENCE SMPL, LOGO, FPP, MATERIAL SHIP/ETA, BULK PROCESS, PRODUCTION SMPL, line/worker, cutting/output/finishing, pricing (TARGET CMPH, FIXED FACTORY, FINAL 공장 가격), fabric consumption (BQ–BZ), FOB, PO NO (KOREA/CHINA), 1st–4th SHIP + SMPL, payment (CW–DP). Trạng thái **mã hoá bằng màu nền ô** (legend dòng 1–2: NOT FIXED, ON PRODUCTION, KOREA SHIP OUT, UPDATE, FIXED PRICE, SEWING FINISHED, CANCEL, PENDING STYLE) |
| Số bản ghi | 113 block style (110 hoạt động + 3 CANCEL), 261 dòng style×color, tổng 62,131 pcs; 9 block khuôn rỗng (W43–45, O23–25, S67–75). Phần cuối (dòng 593–631): SUB TOTAL, GRAND TOTAL (`#REF!` ở nhiều cột), bảng kế hoạch theo nhà máy và theo nhóm hàng |
| DETAIL | Bảng phẳng 1 dòng/style (110 dòng) dựng bằng `VLOOKUP` từ ORDER RECAP; cột FILE NO toàn `#REF!` |
| FAB(…) | Bảng phẳng: 1 dòng = style × màu × phần vải (PART: 몸판/배색/안감/주머니감/충전재…), nhà cung cấp, mô tả vải, C/O, khổ, đơn giá, thành phần, BT confirm, định mức (요척), ngày đặt, số yard đặt, ETD/ETA, số lượng đã giao, chênh lệch, các cột lô tàu (`ETD 0517 VESSEL …`). 939 dòng (0519) / 971 dòng (0615) |
| Chất lượng | Nhiều cột pricing/payment **gần như trống** (fill 8–12 ô); `#DIV/0!` ở BY/BZ toàn cột; `#REF!` ở BL và Grand total; header lặp trong vùng dữ liệu; số lượng màu dạng text `150P`; ghi chú trộn vào ô dữ liệu (`LIGHT BEIGE\n260415 칼라변경`) |
| Độ tin cậy | Cao cho style/màu/qty; Trung bình cho milestone (text tự do); Thấp cho pricing/payment (chưa dùng) |

### F4 — 27SS Challenger Order Recap (MJ, 15/10/2026)

| Mục | Nội dung |
|---|---|
| Sheet | `ORDER RECAP` (A1:DP776, 1,995 merge, 13,740 công thức, 164 ảnh), `DETAIL` (A1:V156) — **cùng template với F3**, không có sheet FAB |
| Mục đích | Master đơn hàng mùa 27SS (đang ở giai đoạn mẫu/chuẩn bị) |
| Số bản ghi | 143 block (137 hoạt động + 6 CANCEL), 375 dòng style×color, tổng 87,940 pcs; type 27SS-SPRING 28 / SUMMER 111 (+ESSENTIALS/ONLINE 35 theo line). Chưa có lô xuất nào |
| Chất lượng | 5 style có ETD năm 2026 đầu năm (2026-01-17, 03-14…) — gần như chắc chắn sai năm; mã `CHFG2WIT7957` sai định dạng; cột FACTORY chứa `260914 CANCEL`; legend màu nhà máy khác F3 (XUAN THANH, SUNVIET đổi mã màu) |
| Độ tin cậy | Trung bình (dữ liệu sớm, nhiều ô chưa điền) |

### F5 — KLMAS 프로파일 (KR) — hồ sơ năng lực công ty

| Mục | Nội dung |
|---|---|
| Trang | 19 trang A4 ngang, tạo bằng Illustrator 12/10/2026; text layer có nhưng nhiều nội dung nằm trong ảnh |
| Nội dung | Giới thiệu KLMAS (pháp nhân FDI tại Việt Nam; quản lý sản xuất, kiểm hàng QC, đào tạo, tư vấn cho may mặc & phụ kiện); lịch sử 1998–2022; sơ đồ tổ chức (HCM: quản lý, kế toán, HR; Hà Nội: hải ngoại, kiểm hàng, nội địa Hàn, phân tích dữ liệu); nhân sự (MR 14, QA/QC 65, quản lý 5); **quy trình 10 bước Production Management** (오더 의뢰 → 협상 → chọn nhà máy → FIT/PRE APPROVAL → FPP → matching chart → FPP confirm → INLINE + washing test → shipping sample → kiểm đóng gói & chứng từ/C/O); quy trình kiểm hàng 5 bước; danh sách brand quản lý sản xuất (có **CHALLENGER**) và brand kiểm hàng |
| Vai trò dữ liệu | **Không chứa dữ liệu giao dịch**; dùng làm từ điển nghiệp vụ: xác nhận chuỗi milestone và ý nghĩa FPP/INLINE/TOP/SHIPPING SMPL, C/O, matching chart |
| Hạn chế | Chưa OCR các trang ảnh (biểu đồ sản lượng, trang 4); không cần cho thiết kế DB |

## 3. File chưa xử lý
Không có. F3b được ghi nhận là bản trùng (MD5 giống F3) và loại khỏi phân tích.
