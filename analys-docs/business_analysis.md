# Business Analysis — KLMAS / CHALLENGER

> **[Q]** quan sát trực tiếp · **[S]** suy luận cần xác nhận · **[R]** khuyến nghị

## 1. Bối cảnh nghiệp vụ

- **[Q]** KLMAS là công ty FDI tại Việt Nam làm **quản lý sản xuất (production management) và kiểm hàng (QC)** cho các brand may mặc Hàn Quốc (PDF). KLMAS không tự sản xuất: đơn hàng được phân cho **nhà máy gia công** tại Việt Nam.
- **[Q]** Các file Excel đều thuộc brand **CHALLENGER** (mã style bắt đầu `CH`), mùa **26FW** (đang sản xuất/xuất hàng) và **27SS** (đang phát triển mẫu).
- **[S]** Buyer là chủ brand tại Hàn Quốc; hàng xuất từ cảng Việt Nam (Hải Phòng – cột `DEL EX-HAIPHONG`) sang Hàn (`RDD KOREA`).

## 2. Quy trình nghiệp vụ thể hiện trong dữ liệu

Chuỗi milestone ([Q] khớp giữa PDF trang 6 và các cột của ORDER RECAP/F1):

| # | Bước | Bằng chứng trong Excel |
|---|------|------------------------|
| 1 | Nhận đơn / chốt style, màu, số lượng | ORDER RECAP: STYLE, COLOR, ORDER Q'TY; ghi chú `260720 REDUCED 170P➜136P` |
| 2 | Đàm phán giá gia công (CMPH), số lượng, giao hàng | Cột TARGET CMPH / FIXED FACTORY / FINAL 공장 가격 (hầu như trống) |
| 3 | Chọn nhà máy, phân style | FACTORY; ghi chú `260407 FIXED FACT(NTC) / 260512 MOVED FACT` |
| 4 | Reference / Fit / Pre-approval sample | REFERENCE SMPL (`1ST REF SMPL: 4/1ETA ➜ 4/18 RETURN`), QC SMPL PROCESSING |
| 5 | FPP sample (Final Pre-Production) | FPP SMPL STATUS: IN HANOI, SEND TO FACT, SEND TO KOR, CFM DATE |
| 6 | Logo / artwork / trim | LOGO STATUS (`1) H.T LOGO(1): -AP_TR02 H.T LOGO 3CM`) |
| 7 | Nguyên phụ liệu (fabric, lining, label, tag) | MATERIAL SHIP/ETA; sheet FAB(…) với định mức, PO yard, ETD/ETA, lô tàu |
| 8 | Bulk process: pattern, worksheet, minimarker, material card | BULK PROCESS (PTTN, WORKSHEET, MINIMARKER, MTR CARD) |
| 9 | Inline sample, photo sample, TOP sample, wash test | PRODUCTION SMPL STATUS; F1: INLINE SMPL, TOP SMPL |
| 10 | Kế hoạch & thực hiện: cutting → input → sewing → finishing | F1: CUTTING/INPUT/SEWING FINISH PLAN; ORDER RECAP: CUTABLE DATE, OUTPUT, FINISHING |
| 11 | Sản lượng ngày, kiểm hàng (inspection), xuất hàng | F1: ONE DAY, OUTPUT, INSPECTION, SHIPPED |
| 12 | Xuất hàng từng lô (ETD/ETA, SEA/AIR/HC) + shipping sample | F2 block shipment; ORDER RECAP 1ST–4TH SHIP |
| 13 | Chứng từ, C/O, thanh toán gia công | CO SENDING, PAY DATE/U/P/AMOUNT (trống) |

Quy tắc ngày [Q]: `RDD = ETD VN + 12 ngày` (công thức `=L5+12`, đúng cho 110/110 style FW và 140/140 SS có ngày). **Mâu thuẫn**: header DETAIL ghi `ETD VN (RDD-14 DAYS)`, ORDER RECAP ghi `RDD (-12DAY)`, header F1 ghi `BUYER DEL (RDD-10)`.

## 3. Thực thể (entities) nhận diện được

| Thực thể | Loại | Nguồn | Khoá nhận dạng | Ghi chú |
|---|---|---|---|---|
| Brand / Buyer | Master | Brand col, PDF | `CHALLENGER` | PDF liệt kê ~30 brand khác → cần bảng brand |
| Season | Master | tên file, TYPE | `26FW`, `27SS` | |
| Collection / Mode | Lookup | TYPE / MODE | `26FW-FALL`, `26FW-WINTER`, `26FW-ONLINE (ESSENTIAL LINE)`, `REORDER`, `27SS-SPRING`, `27SS-SUMMER` | |
| Line | Lookup | ORDER RECAP dòng 2 cột C | `정상` (normal), `ESSNTIALS LINE (BE ONLINE SALES)`, `리오더` (reorder) | |
| Factory | Master | FACTORY, tên sheet F2, FAB | Tên (không có mã) | Nhiều biến thể tên (xem §5) |
| Style | Master | STYLE NO | `CHF3MWT6306` (11 ký tự) | Có cấu trúc (xem §4) |
| Style order (style trong 1 mùa) | Transaction header | NO (`F9`, `W30`, `O20`, `R1`, `SP1`, `S6`) | season + NO hoặc season + style | NO là số thứ tự nội bộ theo collection |
| Style colour | Transaction detail | COLOR | style + color | Màu viết tự do, cần chuẩn hoá |
| Size run & qty theo size | Transaction detail | F2 | style + color + size | Chỉ F2 có chi tiết size |
| Milestone / sample event | Event | nhiều cột text | style + loại milestone + lần | Dữ liệu dạng ghi chú (`7/16 SENT - 7/20 RE / 7/21 2ND SENT`) |
| Production plan & progress | Snapshot | F1 | style + ngày báo cáo | F1 là ảnh chụp tại 10–12/10 |
| Shipment (lô xuất) | Transaction | F2, ORDER RECAP | ETD + ETA + mode (+ nhà máy) | Không có số invoice/BL |
| Shipment line | Transaction detail | F2 | lô + style + color + size | |
| Sample dispatch | Transaction | F2 SAMPLE | ngày + loại mẫu + style + color + size | |
| Trim / logo component | Master + BOM | LOGO STATUS | mã như `AP_TR02`, `DW_EM003`, `DS_CHLB13`, `AC_CHPR06` | Tiền tố = nhà cung cấp [S]: AP, DW (DONGWON), DS, AC (ACAVA), ID, JY, FB |
| Fabric supplier | Master | FAB P | `예경`, `JBEE(제이비)`, `KYLIN`, `VINA_LOCAL` … | |
| Fabric item | Master | FAB R | `KDQ0693 (피케)` | Trộn mã + mô tả |
| Style fabric BOM | Transaction | FAB | style + color + part (+ supplier) | định mức (요척), PO yard, đơn giá, C/O |
| Fabric shipment | Transaction | FAB cột vessel | ETD + vessel + supplier | |
| Pricing / payment | Transaction | ORDER RECAP | style | Hiện **chưa có dữ liệu** |

## 4. Cấu trúc mã style [Q + S]

`CH F 3 M WT 6306`

| Vị trí | Ví dụ | Ý nghĩa | Bằng chứng |
|---|---|---|---|
| 1–2 | `CH` | Brand CHALLENGER | [Q] mọi style |
| 3 | `F`, `G`, `E` | Năm (E=2025, F=2026, G=2027) | [S] 26FW → F, 27SS → G, `CHE4…` xuất hiện như hàng mùa trước |
| 4 | `1`…`5` | Mùa con (1 Spring, 2 Summer, 3 Fall, 4 Winter, 5 ?) | [Q] FAB dùng `=MID(I,4,1)` làm SEASON; 27SS-SPRING = CHG1, SUMMER = CHG2; 26FW-FALL chủ yếu CHF3, WINTER CHF4 |
| 5 | `M`/`W`/`U` | Giới tính (MODE) | [Q] khớp cột MODE (UNI = U) |
| 6–7 | `WT`, `LT`, `JK`, `PT`… | Nhóm hàng (ITEM 복종) | [Q] FAB dùng `=MID(I,6,2)` làm ITEM |
| 8–11 | `6306` | Số thứ tự | [S] |

Nhóm hàng [S, đối chiếu mô tả]: JK jacket, VT vest, WT woven top, LT long-sleeve tee, ST short-sleeve tee, PT pants, SK skirt, HP half pants, OP one-piece, IT inner top, MK mask?, HC headwear/cap?, GW neck warmer (`UNI) PADDING NECK WARMER`), CP ?, WI ?.

[R] Lưu mã style nguyên văn và **tách các thành phần thành cột dẫn xuất** có kiểm tra; không dùng thành phần để thay thế cột MODE/TYPE gốc khi có mâu thuẫn (vd. reorder `CHF2…` nằm trong 26FW; `CHF2UMK6285` nằm trong 27SS).

## 5. Phân tích chéo tài liệu

### 5.1 Độ phủ style (26FW)

| Tập | Số style |
|---|---|
| F1 production status | 110 |
| F3 ORDER RECAP (block) | 113 (110 + 3 CANCEL: CHF3MPT6333, CHF3WLT6728, CHF3WVT6707 — qty 0) |
| F2 shipment status (block có dữ liệu) | 103 |
| Có mặt ở cả 3 file | 100 |
| FAB(0615) | 117 style (gồm 7 style không có trong recap: CHF3MPT6332, CHF3UCP6382, CHF3WPT6743, CHF4MCP6482, CHF4UCP6484, CHF4WCP6876, CHF4WSK6851 — [S] style bị drop hoặc đổi mã sau 15/06) |

Style có trong F1/F3 nhưng không có block dữ liệu ở F2: CHF2MPT6248, CHF2WPT6673 (reorder giao sớm), CHF3MJK6302, CHF4MJK6405, CHF4MPT6444, CHF4WHP6851, CHF4WJK6805, CHF4WJK6806 (block rỗng hoặc chưa tạo).

### 5.2 Mâu thuẫn mã style (cùng một sản phẩm, khác mã) — **giả thuyết, cần xác nhận**

| F1 | F3 ORDER RECAP | F2 | FAB |
|---|---|---|---|
| CHF4WHP6851 (W40, 330) | CHF4WHP6851 (330) | **CHF4WSK6851** (330, TBM) | CHF4WSK6851 |
| CHF4WHP6852 (W41, 500) | **CHF4WSK6852** (500) | CHF4WHP6852 (500) | — |
| CHF4WWT6817 (370) | CHF4WWT6817 | **CHFWWT6817** (lỗi gõ) | — |

### 5.3 Số lượng đặt hàng
- F1 tổng thực tế (cộng 110 dòng) = **62,357**; F3 = **62,131**. Chênh **226** được giải thích chính xác bởi 3 style mà F3 giảm 20%: CHF3MPT6334 (360→288), CHF3WPT6745 (400→320), CHF3WSK6751 (370→296). F2 vẫn giữ số cũ (360/400/370). → [S] F3 cập nhật mới nhất về qty, hoặc F3 phản ánh qty đã cắt cho một mục đích khác; **cần xác nhận**.
- CHF3MJK6301: F1/F3 = 350, F2 = 332 (F2 ghi tổng màu ORDER = 332).

### 5.4 Số lượng đã xuất — **ba con số khác nhau cho cùng một sự kiện**

Ví dụ CHF3MWT6306: F1 SHIPPED = 404 (10/10), F3 TOTAL SHIP = 399 (15/10), F2 = 395 hàng + 6 mẫu = 401 (14/10). Trên 100 style chung:

| So sánh | Số style khớp |
|---|---|
| F1 SHIPPED = F2 (hàng + mẫu) | 34 |
| F1 SHIPPED = F2 (chỉ hàng) | 40 |
| F3 TOTAL SHIP = F2 (hàng + mẫu) | 50 |
| F1 = F3 | 21 |

Tổng: F1 56,259 · F3 57,836 · F2 hàng 57,905 · F2 hàng+mẫu 58,410.
→ Nguyên nhân [S]: (a) khác ngày chụp (10/10, 14/10, 15/10), (b) định nghĩa "shipped" khác nhau (có/không tính mẫu), (c) nhập tay độc lập. [R] DB phải lưu **lô xuất ở mức chi tiết** và tính tổng, thay vì lưu con số tổng do người nhập.

### 5.5 Nhà máy (factory) — cùng thực thể, nhiều tên

| Chuẩn đề xuất | Biến thể quan sát |
|---|---|
| TAN BINH MINH | `TAN BINH MINH`, `TBM`, sheet `TBM(35)`, `TAN BINH MINH PLAN`, `FG VINA -> TBM` |
| TRUONG PHUC | `TRUONG PHUC`, `TP(16)`, `TRUONG PHUC TV` |
| DONG MY | `DONG MY`, `DM(27)` |
| TIEN THANH | `TIẾN THÀNH` (có dấu), `TIEN THANH` |
| FG BAC GIANG / FG VINA | F1 `FG BAC GIANG` ↔ F3 `FG VINA` cho cùng style CHF4MJK6402 ([S] cùng tập đoàn, khác xưởng) |
| HUY HOANG, SUJANG/HUY HUNG, HAGACO/TRUONG CHINH | Ghi chú đổi tên trong bảng tổng cuối ORDER RECAP |

Lịch sử chuyển nhà máy [Q]: FAB(0615) ghi CHF3MJK6301 ở HA HIEU, trong khi F1/F3 ở MTT kèm ghi chú `260512 MOVED FACT`; 66 dòng FAB đổi nhà máy giữa snapshot 19/05 và 15/06 (`FG VINA -> TBM`). → cần bảng **factory assignment có hiệu lực theo thời gian**.

### 5.6 Cột cùng nghĩa, khác tên

| Khái niệm | F1 | F3 ORDER RECAP | F3 DETAIL | F2 | FAB |
|---|---|---|---|---|---|
| Số thứ tự style | NO | B (NO) | NO | (số block, khác) | — |
| Mã style | STYLE NO | D (S/NO) | STYLE NO | trong tiêu đề block | 품번 |
| Nhà máy | FACTORY | E (FACT) | FACTORY | tên sheet | FAC (공장명) |
| Giới tính | MODE | (từ mã) | M/W | — | (từ mã) |
| Collection | TYPE | C dòng 4 | MODE | — | SEASON (khác nghĩa!) |
| Ngày xuất VN | ETD VN | ETD VIET / RDD(-12DAY) | ETD VN (RDD-14 DAYS) | nhãn lô | DUE DATE 기획 납기일(ETD) |
| Qty đặt | ORDER Q'TY | ORDER Q'TY (KOREA/GRAND TTL) | ORDER Q'TY | ORDER Q'TY (theo size) | 수량1 / 수량2 |
| Qty xuất | SHIPPED Q'TY | TOTAL SHIP QTY | SHIPPED Q'TY | SHIPPED / TOTAL SHIPPED+SMPL | — |
| Mô tả | ITEMS | dòng 2 (EN), dòng 3 (KR) | ITEMS | — | 품명 (KR) |

### 5.7 Cột cùng tên, khác nghĩa
- `SEASON`: FAB = chữ số mùa con (`3`); TYPE ở F1 = collection (`26FW-FALL`).
- `ETD`: ETD hàng thành phẩm (F1/F3) ≠ ETD vải (FAB cột AI) ≠ `PLAN MTR(FAB) SHIP DATE(ETA)`.
- `S/NO`: ORDER RECAP = style no; F2 = nhãn hàng (ORDER Q'TY / S/DATE).
- `BAL`: F1 có 3 cột `BAL W/ ORDER Q'TY` khác nhau (output−order, inspection−order, shipped−order); FAB `BAL /YDS` là vải.
- `RDD`: F1 có 2 cột RDD (H có dữ liệu, V rỗng/ẩn).

### 5.8 Master/reference vs transaction vs snapshot

| Loại | Dữ liệu |
|---|---|
| Master / reference | brand, season, collection, line, factory (+alias), style, color (+alias), size, item type, fabric supplier, fabric item, trim item, shipping mode, milestone type, status |
| Transaction | style order, order qty theo color/size, shipment + lines, sample dispatch, fabric PO/BOM, fabric shipment, factory price, payment |
| Snapshot (theo ngày báo cáo) | F1 (output/inspection/shipped tại 10–12/10), FAB(260519) vs FAB(0615), các con số tổng trong F2/F3 |
| Ghi chú tự do (cần tách) | milestone text, LOGO STATUS, REMARK, ghi chú lịch sử trong ô màu/qty/factory |

### 5.9 Logic tính toán quan sát được (công thức)
- `BAL = OUTPUT − ORDER`, `= INSPECTION − ORDER`, `= SHIPPED − ORDER` (F1).
- `RDD = ETD + 12`.
- F2: `TTL = SUM(sizes)`; `TOTAL SHIPPED+SMPL = SUM(lô) + SMPL LIST`; `BAL = TOTAL − ORDER`.
- F3: `CT (TOTAL SHIP) = SUM(color TTL)`, `CR = SUM(1st..4th ship + SMPL)`, `CU (SHORTAGE) = CT − K`; fabric: `BS = BQ*J` (cons × qty), `BT = BR − BS`, `BZ = BW/BU` (#DIV/0! khi BU trống).
- FAB: `AF (PO yard) = 수량1 × 발주요척`, `AK = SUM(cột lô tàu)`, `AL = AK − AF`.
- Các tỉ lệ dung sai: hầu hết style xuất **dư 0.5–3%** so với đơn (64/110 style ở F1 shipped > order) → [S] chính sách over-ship được chấp nhận; cần ngưỡng dung sai.

## 6. Use case dự kiến của DB [S]
1. Theo dõi tiến độ từng style/nhà máy (thay F1/DETAIL).
2. Theo dõi xuất hàng theo lô & color/size (thay F2).
3. Theo dõi milestone mẫu/vật tư (thay ORDER RECAP).
4. Theo dõi nguyên liệu (thay FAB).
5. Báo cáo tổng hợp mùa/nhà máy/nhóm hàng (thay bảng cuối ORDER RECAP) — tính từ dữ liệu chi tiết, không nhập tay.
6. Mở rộng cho brand khác (PDF cho thấy KLMAS quản lý nhiều brand) và cho QC/inspection (PDF mô tả dữ liệu kiểm hàng, báo cáo lỗi — chưa có file mẫu).
