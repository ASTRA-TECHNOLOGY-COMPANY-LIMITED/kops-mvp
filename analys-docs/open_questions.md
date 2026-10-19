# Câu hỏi cần KLMAS trả lời

Tài liệu này dành cho **người phụ trách nghiệp vụ của KLMAS**, không cần biết kỹ thuật. Mỗi câu ghi rõ: mở file nào, sheet nào, ô hoặc dòng nào, đang thấy gì, và muốn hỏi gì. Có thể mở file và trả lời ngay, không cần hỏi lại ý câu hỏi.

**Cách trả lời:** điền vào dòng "**Trả lời của KLMAS:**" ngay dưới mỗi câu (gửi lại file này hoặc trả lời qua nhóm Zalo kèm mã câu, vd. "Q4: …"). Chưa chắc thì ghi "chưa rõ, sẽ hỏi lại X", vẫn có ích.

**Khi chưa có câu trả lời:** ASTRA vẫn làm tiếp theo cách hiểu ghi ở dòng "*Tạm hiểu*". Câu trả lời sau này chỉ cần sửa lại cấu hình, không phải làm lại.

## Viết tắt tên file

Tất cả file nằm trong thư mục `raw-docs/` mà KLMAS đã gửi. Ngày 19/10/2026 thư mục đã được sắp xếp lại theo loại tài liệu (xem `raw-docs/README.md`); đường dẫn dưới đây là đường dẫn mới.

| Viết tắt | Tên file đầy đủ | Người lập (theo tên file) |
|---|---|---|
| **[RECAP 26FW]** | `ORDER/CHALLENGER/26FW/261015 MJ) 26FW CHALLENGER ORDER RECAP.xlsb` | MJ |
| **[RECAP 27SS]** | `ORDER/CHALLENGER/27SS/261015 MJ) 27SS CHALLENGER ORDER RECAP.xlsb` | MJ |
| **[SHIPMENT]** | `TRACKING/CHALLENGER/26FW/261014R2 MJ) 26FW CHALLENGER ALL STYLES SHIPMENT STATUS.xlsx` | MJ |
| **[PRODUCTION STATUS]** | `TRACKING/CHALLENGER/26FW/261012 HUONG) 26FW CLGR PRODUCTION AND SHIPPING STATUS(~10.10).xlsx` | HUONG |
| **[BÁO CÁO NGÀY &lt;nhà máy&gt;]** | `PRODUCTION/CHALLENGER/26FW/<nhà máy>/… DAILY PRODUCTION REPORT.xlsx` | Nhà máy |
| **[BÁO CÁO NGÀY HAGACO]** | `PRODUCTION/DHG(DAEHAN GROBAL)/8 SECONDS/26FW/HAGACO/261015. DHG-HAGACO DAILY PRODUCTION REPORT.xlsx` | Nhà máy HAGACO |
| **[BẢNG KIỂM]** | `INSPECTION/ORDER_TRACKING/CHALLENGER/26FW/260727 HOA) 26SS CHALLENGER (TP+NATEXCO + MTT) KLMAS INSPECTION REPORT.xlsx` | HOA |
| **[DỮ LIỆU KIỂM BÊN THỨ BA]** | `INSPECTION/THIRD_PARTY/INPUT DATA.xlsx` | Văn phòng kiểm hàng |
| **[PHIẾU KIỂM]** | `INSPECTION/FORMS/KLMAS INSPECTION REPORT (FORM) - 2026.xlsx` (và `.pdf`) | — |
| **[BÁO CÁO KIỂM MẪU]** | `INSPECTION/SAMPLES/FNJWD8411 261001 (REPORT FJ).pdf`, ảnh phiếu đã điền `INSPECTION/SAMPLES/REPORT.jpg` | — |

Trong [RECAP], mỗi style chiếm một khối 4 dòng (dài hơn nếu có trên 4 màu). Dòng ghi ở đây là **dòng đầu của khối**: dòng có mã style ở cột D.

---

# Phần 1. Cần trả lời cho giai đoạn 1 (MVP)

Giai đoạn 1 là một **kho dữ liệu chung**: gom ORDER RECAP, Shipment Status, Production Status, báo cáo sản xuất ngày, bảng kiểm, email và biên bản họp vào một chỗ, rồi lên dashboard tiến độ, xuất hàng và đối soát. Chỉ cần trả lời các câu dưới đây.

## 1A. Cần trả lời trước buổi demo

Nếu hiểu sai các câu này, **con số chính trên dashboard sẽ sai**.

### Q1. Khi các file ghi số khác nhau, file nào là số đúng?

- **Ở đâu:** cùng style **CHF3MJK6301** (mã F1, nhà máy MTT) ở 3 file:

  | File | Vị trí | Số đặt hàng | Số đã xuất |
  |---|---|---|---|
  | [RECAP 26FW] | sheet `ORDER RECAP`, dòng 5, cột K (GRAND TTL) | **350** (BLACK 180 + CREAM 170, cột J dòng 5–6) | — |
  | [SHIPMENT] | sheet `MTT(11)`, khối "1) CHF3MJK6301" bắt đầu ở ô B4, dòng `S/DATE TTL` cột J | **332** | 352 (dòng `TOTAL SHIPPED Q'TY+SMPL QTY`) |
  | [PRODUCTION STATUS] | sheet `26FW-CLGR`, dòng 35, cột L (ORDER Q'TY) và cột R (SHIPPED Q'TY) | **350** | **348** |

- **Câu hỏi:** khi 3 file ghi khác nhau như trên, mỗi loại số nên lấy ở file nào?
  - Số lượng đặt theo màu: [RECAP] hay [SHIPMENT]?
  - Số lượng theo size: chỉ [SHIPMENT] có, đúng không?
  - Số đã xuất: [SHIPMENT] hay [PRODUCTION STATUS]?
  - Nhà máy hiện tại của style: [RECAP] cột E hay [PRODUCTION STATUS] cột F?
- **Gợi ý trả lời:** "Số đặt lấy theo ___; số đã xuất lấy theo ___; nhà máy lấy theo ___". Và (nếu biết) vì sao CHF3MJK6301 ở [SHIPMENT] chỉ có 332.
- *Tạm hiểu:* số đặt, màu, nhà máy theo [RECAP]; size và lô xuất theo [SHIPMENT]; đã may và đã kiểm theo báo cáo ngày của nhà máy (xem Q23).

**Trả lời của KLMAS:**

### Q23. Số "đã may" (OUTPUT) nên tin báo cáo ngày của nhà máy hay [PRODUCTION STATUS]?

- **Ở đâu:** style **CHF4MPT6444** (mã W33, nhà máy TBM, ETD 07/10):
  - [PRODUCTION STATUS], sheet `26FW-CLGR`, dòng 118: cột N (OUTPUT) = **10**, cột M (ONE DAY) = **10**. Tên file ghi số liệu "đến 10/10", ô AC1 ghi ngày 12/10.
  - [BÁO CÁO NGÀY TBM], cột "OUT PUT/ SL RA CHUYỀN" của style này qua từng sheet ngày: 11/10 ra 10 → 12/10 ra 30 → 13/10 ra 45 → 14/10 ra 50 → 15/10 ra 55. **Cộng dồn đến 15/10 là 190** (sheet `15.01`, dòng 5–8).
- **Vì sao hỏi:** nếu tính theo [PRODUCTION STATUS] (10 cái/ngày), hệ thống dự báo style này trễ **49 ngày**. Nếu tính theo báo cáo ngày (khoảng 50 cái/ngày), chỉ trễ khoảng **18 ngày**.
- **Câu hỏi:**
  1. Số "đã may" chính thức lấy từ báo cáo ngày của nhà máy, đúng không?
  2. [PRODUCTION STATUS] được tổng hợp từ đâu, ai cập nhật, mỗi ngày mấy giờ?
  3. Cột ONE DAY (cột M) là sản lượng của ngày nào: hôm qua, hôm nay, hay một con số kế hoạch?
- *Tạm hiểu:* báo cáo ngày là số chính thức; [PRODUCTION STATUS] dùng để đối chiếu; ONE DAY là sản lượng của ngày gần nhất.

**Trả lời của KLMAS:**

### Q24. Có còn báo cáo sản xuất ngày nào chưa gửi không?

- **Ở đâu:** thư mục `raw-docs/PRODUCTION/CHALLENGER/26FW/`. Ngày báo cáo cuối cùng nhận được của từng nhà máy:

  | Nhà máy | Có báo cáo từ | Đến | Ghi chú |
  |---|---|---|---|
  | TAN BINH MINH | 01/07 | 15/10 | đủ |
  | TRUONG PHUC | 06/07 | 14/10 | đủ |
  | MTT | 03/07 | 02/10 | thiếu 04/08 → 08/09 |
  | DONG MY | 13/07 | 28/09 | thiếu 17/08 → 08/09 |
  | HA HIEU | 26/09 | 28/09 | chỉ 2 ngày |
  | NATEXCO | 13/08 | **08/09** | ví dụ: style CHF4WVT6813 mới cắt 200/700 và chưa ra chuyền vào 08/09, nhưng [PRODUCTION STATUS] dòng của style này ghi đã may xong 700 |
  | TIEN THANH, FG VINA | — | — | không có file nào |

- **9 style đang chạy không có trong bất kỳ báo cáo ngày nào:** CHF2MPT6248, CHF3WVT6706, CHF4MJK6402, CHF4MJK6403, CHF4MJK6405, CHF4MJK6406, CHF4WJK6803, CHF4WJK6806, CHF4WVT6814.
- **Câu hỏi:** các khoảng thiếu ở trên là do nhà máy không gửi, do KLMAS chưa chuyển cho ASTRA, hay do giai đoạn đó không sản xuất? Nếu có file, xin gửi bổ sung (xem R7 ở cuối tài liệu).
- *Tạm hiểu:* thiếu file. Dashboard sẽ đánh dấu các nhà máy và style này là "thiếu dữ liệu".

**Trả lời của KLMAS:**

### Q4. Ba style đã giảm 20% ở ORDER RECAP, nhưng các file khác và thực tế xuất vẫn theo số cũ. Số nào đúng?

- **Ở đâu:**

  | Style (mã) | [RECAP 26FW] sheet `ORDER RECAP` | [PRODUCTION STATUS] dòng | [SHIPMENT] sheet `TBM(35)` |
  |---|---|---|---|
  | CHF3MPT6334 (F32) | dòng 141–142, cột I ghi `260720 REDUCED 180P➜144P` cho cả 2 màu → tổng **288** | dòng 104: đặt **360**, may 360, xuất **347** | khối "2) CHF3MPT6334" ô M4: đặt **360** |
  | CHF3WPT6745 (F38) | dòng 165–166: `REDUCED 170P➜136P` và `230P➜184P` → **320** | dòng 97: đặt **400**, may 400, xuất 402 | khối "8)" ô AI38: đặt **400** |
  | CHF3WSK6751 (F41) | dòng 177–178: `REDUCED 170P➜136P` và `200P➜160P` → **296** | dòng 98: đặt **370**, may 370, xuất 370 | khối "11)" ô X70: đặt **370** |

- **Điểm lạ:** ORDER RECAP ghi đã giảm từ ngày 20/07/2026 (`260720`), nhưng nhà máy vẫn may đủ số cũ và đã **xuất nhiều hơn số mới** (vd. CHF3MPT6334 xuất 347 trong khi đơn mới là 288).
- **Câu hỏi:**
  1. Buyer có thật sự giảm đơn 20% không, hay sau đó lại giữ số cũ?
  2. Nếu đã giảm, phần xuất dư (347 − 288 = 59 cái) được xử lý thế nào?
  3. Lần sau có đổi số lượng, file nào phải cập nhật trước?
- *Tạm hiểu:* lấy theo ORDER RECAP (số mới); dashboard đánh dấu 3 style này là "lệch giữa các file".

**Trả lời của KLMAS:**

### Q3. Một style mà mỗi file ghi một mã khác nhau. Mã nào đúng?

- **Ở đâu:**

  | Mã trong [RECAP 26FW] | Mã khác đang dùng ở |
  |---|---|
  | **CHF4WHP6851** (mã W40, dòng 371; [PRODUCTION STATUS] dòng 110 cũng dùng mã này) | **CHF4WSK6851** ở: [SHIPMENT] sheet `TBM(35)` ô M205; [RECAP 26FW] sheet `FAB(0615)` cột I dòng 788–799; [BÁO CÁO NGÀY TBM] từ sheet `25.08` đến `17.09` |
  | **CHF4WSK6852** (mã W41, dòng 375; sheet `FAB(0615)` cũng dùng mã này) | **CHF4WHP6852** ở: [SHIPMENT] sheet `TBM(35)` ô X205; [PRODUCTION STATUS] dòng 120 |
  | **CHF4WWT6817** (mã W22, dòng 293) | **CHFWWT6817** (thiếu số 4) ở [SHIPMENT] sheet `DM(27)` ô AI204 |

- **Câu hỏi:** với mỗi dòng, mã nào là mã đúng in trên nhãn sản phẩm? Mã kia là gõ nhầm, hay style đã từng đổi mã (ví dụ đổi từ quần HP sang váy SK)?
- *Tạm hiểu:* là cùng một style. Dùng mã trong [RECAP 26FW] và ghép dữ liệu các file khác vào.

**Trả lời của KLMAS:**

### Q27. Bốn mã style "CHE…" trong báo cáo ngày của TBM có phải gõ nhầm của "CHF…"?

- **Ở đâu:** [BÁO CÁO NGÀY TBM], cột C (S/NO):

  | Mã trong báo cáo ngày TBM | Có ở các sheet | Mã cùng số trong [RECAP 26FW] |
  |---|---|---|
  | CHE3WPT6986 | `06.07` → `10.08` | **CHF3WPT6986** (mã O9, dòng 433, nhà máy TBM) |
  | CHE3WSK6754 | `14.08` → `07.09` | **CHF3WSK6754** (mã F44, dòng 189, TBM) |
  | CHE4MPT6441 | `25.08` → `18.09` | **CHF4MPT6441** (mã W30, dòng 325, TBM) |
  | CHE4WPT6842 | `28.08` → `18.09` | **CHF4WPT6842** (mã W35, dòng 351, TBM) |

- **Lý do nghi ngờ:** chữ thứ 3 của mã (E hay F) là mùa. Cả 4 style `CHF…` đều thuộc TBM, đang chạy trong mùa 26FW, nhưng không xuất hiện trong báo cáo ngày của TBM dưới mã `CHF…`. Ngược lại, 4 mã `CHE…` không có trong ORDER RECAP.
- **Câu hỏi:** đây là nhà máy gõ nhầm chữ mùa (E thay vì F) phải không? Hay là 4 style mùa trước (reorder) đang may song song?
- *Tạm hiểu:* gõ nhầm. Ghép vào 4 style `CHF…` tương ứng.

**Trả lời của KLMAS:**

## 1B. Xác nhận trong buổi demo

Hệ thống đã chạy theo cách hiểu dưới đây. KLMAS chỉ cần xác nhận "đúng" hoặc sửa lại.

### Q2. "Số đã xuất" có tính cả hàng mẫu không?

- **Ở đâu:** style **CHF3MWT6306** (mã F9, nhà máy DONG MY):
  - [SHIPMENT], sheet `DM(27)`, khối "1) CHF3MWT6306" (ô B4): các lô xuất hàng cộng lại **395**; dòng `SMPL LIST` (mẫu đã gửi) **6**; dòng `TOTAL SHIPPED Q'TY+SMPL QTY` (ô J25) **401**.
  - [PRODUCTION STATUS], sheet `26FW-CLGR`, dòng 6, cột R (SHIPPED Q'TY) = **404**.
- **Câu hỏi:**
  1. Số "SHIPPED Q'TY" ở [PRODUCTION STATUS] có tính mẫu (shipping sample, photo sample) không?
  2. Khi báo cáo "đã xuất bao nhiêu % đơn hàng" cho buyer, KLMAS có tính mẫu không?
- *Tạm hiểu:* tách riêng hàng và mẫu; "% đã xuất" chỉ tính hàng, không tính mẫu.

**Trả lời của KLMAS:**

### Q6. Màu nền ô ở ORDER RECAP có còn là cách chính thức để ghi trạng thái style không?

- **Ở đâu:** [RECAP 26FW], sheet `ORDER RECAP`:
  - Bảng chú thích màu ở dòng 1–2: ô H1 NOT FIXED (xanh dương), J1 ON PRODUCTION, L1 KOREA SHIP OUT (xanh lá nhạt), Q1 UPDATE, H2 FIXED PRICE, J2 SEWING FINISHED, L2 CANCEL (đỏ), R2 PENDING STYLE.
  - Ví dụ khó hiểu:
    - **W3** CHF4MJK6403 (dòng 211): ô mã W3 (cột B) tô màu ON PRODUCTION, nhưng ô mã style (cột D) không tô màu.
    - **W4** CHF4MJK6404 (dòng 215), W5, W6, W12, W13, W14, W33, W38: không tô màu gì, dù đang sản xuất.
- **Câu hỏi:**
  1. Ô cột B và ô cột D tô khác màu thì theo ô nào?
  2. Style không tô màu nghĩa là gì: chưa cập nhật, hay đang ở trạng thái "bình thường"?
- *Tạm hiểu:* ưu tiên màu ô cột D, nếu không có thì lấy ô cột B; không có màu thì hiển thị "chưa có trạng thái". Tiến độ thật lấy từ báo cáo ngày, không phụ thuộc vào màu.

**Trả lời của KLMAS:**

### Q13. Danh sách nhà máy chính thức và các tên gọi khác nhau

- **Ở đâu:** cùng một nhà máy đang được viết nhiều cách:

  | Cách viết | Ở đâu |
  |---|---|
  | TAN BINH MINH, **TAN BINH MINH PLAN**, **TBM** | [RECAP 26FW] cột E (dòng 137 ghi "TAN BINH MINH PLAN"); [SHIPMENT] tên sheet `TBM(35)` |
  | TRUONG PHUC, **TP** | [SHIPMENT] sheet `TP(16)`; [BẢNG KIỂM] sheet `TP` |
  | DONG MY, **DM** | [SHIPMENT] sheet `DM(27)` |
  | **FG VINA** / **FG BAC GIANG** / **FG** | [RECAP 26FW] dòng 207 ghi "FG VINA"; [PRODUCTION STATUS] dòng 77 ghi "FG BAC GIANG"; [BẢNG KIỂM] sheet `FG` |
  | TIEN THANH / TIẾN THÀNH | [RECAP 26FW] dòng 219; [PRODUCTION STATUS] dòng 65 |
  | **SON HA**, **JM** | [RECAP 27SS] cột E (SON HA từ dòng 535, JM từ dòng 372) |
  | NTC, HH (trong ghi chú đổi nhà máy) | [RECAP 26FW] dòng cuối của khối, cột E, vd. `260407 FIXED FACT(NTC)` (khối dòng 5–8) |

- **Thêm:** trong [DỮ LIỆU KIỂM BÊN THỨ BA] (sheet DATA, cột I FACTORY, cột H VENDOR) có nhà máy **SON HA GLOBAL** và **FG** thuộc vendor DAEHAN GLOBAL KOREA.
- **Câu hỏi:** xin danh sách nhà máy KLMAS đang làm việc, mỗi nhà máy một tên chuẩn và các tên viết tắt. Cụ thể: FG VINA và FG BAC GIANG là một hay hai nhà máy? SON HA và JM là nhà máy nào? NTC = NATEXCO, HH = HA HIEU, đúng không?
- *Tạm hiểu:* như bảng trên; FG VINA và FG BAC GIANG là một; SON HA và JM tạm để riêng.

**Trả lời của KLMAS:**

### Q14. Xuất dư hoặc thiếu bao nhiêu thì vẫn coi là "đủ đơn"?

- **Ở đâu:** [PRODUCTION STATUS] dòng 6 (CHF3MWT6306): đặt 400, xuất 404. Dòng 104 (CHF3MPT6334): đặt 360, xuất 347.
- **Câu hỏi:** buyer CHALLENGER chấp nhận xuất dư/thiếu bao nhiêu % so với đơn (ví dụ ±3%, ±5%)? Có khác nhau theo loại hàng không?
- *Tạm hiểu:* ±5%.

**Trả lời của KLMAS:**

### Q15. Size "XXL" và "2XL" có phải là một?

- **Ở đâu:** [SHIPMENT]: phần lớn khối ghi size `2XL` (vd. sheet `DM(27)`, khối 19), một số khối ghi `XXL`. [BÁO CÁO NGÀY DONG MY] sheet `9.28` dòng 401 ghi `2XL`.
- **Câu hỏi:** XXL và 2XL có phải cùng một size không?
- *Tạm hiểu:* là một.

**Trả lời của KLMAS:**

### Q26. Style bộ 2 món (áo vest + áo khoác) được đếm thế nào?

- **Ở đâu:**
  - [RECAP 26FW] dòng 235: style **CHF4WJK6801** (mã W9, NATEXCO), đặt **350** (BLACK 180 + KHAKI GREY 170), chỉ có một dòng style.
  - [BẢNG KIỂM], sheet `NATEXCO`: dòng 4–6 ghi "CHF4WJK6801 - VEST -" và dòng 7–9 ghi "CHF4WJK6801 - JACKET-", mỗi món 350, kiểm và đếm riêng. Cột AA (TTL KLMAS PASSED) của dòng 9 ghi 392 cho phần JACKET, nhiều hơn 350.
- **Câu hỏi:**
  1. Đơn 350 là 350 **bộ** (= 350 vest + 350 khoác), đúng không?
  2. Khi xuất hàng, đếm theo bộ hay theo từng món?
  3. Vì sao phần JACKET đạt 392, nhiều hơn 350?
- *Tạm hiểu:* 350 bộ; số bộ đạt = số của món đạt ít hơn.

**Trả lời của KLMAS:**

### Q28. Dữ liệu của Daehan Global / 8 SECONDS có nằm trong giai đoạn 1 không?

- **Ở đâu:** [BÁO CÁO NGÀY HAGACO]: 8 style mã dạng `LEV-24059 #424939LYD`, cột BUYER ghi SAMSUNG, tổng đặt 12.740, đã may 10.230 (sheet `10.15`).
- **Câu hỏi:**
  1. KLMAS có muốn theo dõi đơn của Daehan Global / 8 SECONDS trên cùng hệ thống ngay giai đoạn 1 không?
  2. Ai được xem dữ liệu này? Người của CHALLENGER có được thấy không?
- *Tạm hiểu:* có nạp vào hệ thống nhưng tách riêng theo brand; dashboard mặc định chỉ hiện CHALLENGER; buyer CHALLENGER không thấy dữ liệu 8 SECONDS.

**Trả lời của KLMAS:**

### Q-T4. File được cập nhật bao lâu một lần, và để ở đâu?

- **Câu hỏi:**
  1. KLMAS muốn dashboard cập nhật mỗi ngày một lần (ví dụ 9 giờ sáng) hay nhiều lần trong ngày?
  2. Các file (ORDER RECAP, Shipment Status, báo cáo ngày của nhà máy, bảng kiểm) hiện đang lưu ở đâu: máy cá nhân, Google Drive, Zalo, email?
  3. Có thể thống nhất một thư mục chung theo cấu trúc `PRODUCTION/<brand>/<mùa>/<nhà máy>/` như KLMAS vừa gửi không?
- *Tạm hiểu:* cập nhật mỗi sáng; dùng một thư mục chung theo cấu trúc trên.

**Trả lời của KLMAS:**

### Q-T5. Ai sẽ xem dashboard ở giai đoạn 1?

- **Câu hỏi:** những ai cần xem: MR, QC, quản lý, ban giám đốc? Buyer có cần xem ở giai đoạn này không?
- *Tạm hiểu:* chỉ người nội bộ KLMAS và ASTRA; chưa mở cho buyer.

**Trả lời của KLMAS:**

## 1C. Dữ liệu cần KLMAS gửi thêm cho giai đoạn 1

| Mã | Cần gửi | Để làm gì | Trạng thái |
|---|---|---|---|
| R5 | Báo cáo sản xuất ngày và kế hoạch sản xuất của nhà máy | Tiến độ may, dự báo ngày xong | ✅ Đã nhận báo cáo ngày của 6 nhà máy CHALLENGER và HAGACO. Kế hoạch sản xuất: **chưa** |
| R7 | Báo cáo ngày còn thiếu: NATEXCO sau 08/09; HA HIEU trước 26/09; DONG MY 17/08 → 08/09 và sau 28/09; MTT 04/08 → 08/09 và sau 02/10; toàn bộ của TIEN THANH, FG VINA | Không bị "mù" tiến độ (Q24) | Chưa nhận |
| R8 | Bảng theo dõi kiểm hàng của các nhà máy còn thiếu (DONG MY, TAN BINH MINH), nếu có | Biết đã kiểm đạt bao nhiêu | Chưa nhận |

---

# Phần 2. Để sau giai đoạn 1

Không cần trả lời ngay. ASTRA sẽ hỏi lại khi làm tới phần liên quan.

### Q25. Số lỗi trong bảng kiểm được đếm thế nào? *(cần khi làm dashboard chất lượng)*

- **Ở đâu:** [BẢNG KIỂM], sheet `NATEXCO`, các dòng tổng ở cuối:
  - Dòng 38 (C — KLMAS TTL INSPECT QTY), cột AA: **1.407** cái đã kiểm.
  - Dòng 39 (D — KLMAS DEFECT QTY), cột AA: **946** lỗi.
  - Dòng 40 (E — DEFECT RATE), ngày 24/09 (cột I): **1,77** (= 177%), vì file lấy 85 lỗi chia 48 cái **đạt**.
  - Sheet ẩn `TP (4)`: 1.440 lỗi nhưng 0 cái kiểm.
- **Để so sánh:** trong [DỮ LIỆU KIỂM BÊN THỨ BA] (sheet DATA), với DISCOVERY và FILA thì SL lỗi (cột O) = tổng số đếm theo mã lỗi (cột Q + R), và tỷ lệ lỗi (cột S) = SL lỗi ÷ SL kiểm (cột M). Ví dụ dòng 2: 38 ÷ 212 = 17,9%. Bảng của HOA lại chia cho SL **đạt**.
- **Câu hỏi:** "DEFECT QTY" là số **sản phẩm bị lỗi** hay số **điểm lỗi** (một sản phẩm có thể có nhiều lỗi, sửa xong vẫn đạt)? Tỷ lệ lỗi chính thức tính trên số đã kiểm hay số đạt?
- *Tạm hiểu:* là số điểm lỗi; tỷ lệ = lỗi ÷ số đã kiểm. Giai đoạn 1 không hiển thị tỷ lệ lỗi.

**Trả lời của KLMAS:**

### Q5. Một "lô xuất" là gì? *(cần khi làm kế hoạch xuất, booking)*

- **Ở đâu:** [SHIPMENT], sheet `DM(27)`, ô B13 `8/12ETD-8/18ETA SEA`; sheet `TBM(35)` có `10/12ETD-10/12ETA AIR`; sheet `MTT(11)` có `10/06 ETD SHIPPING BY HC`.
- **Câu hỏi:** cùng một ngày ETD/ETA và cùng phương thức thì các nhà máy đi chung một booking/container, hay mỗi nhà máy một booking? Có số invoice hoặc B/L để phân biệt không? "HC" là hand carry?
- *Tạm hiểu:* chung một lô theo (ETD, ETA, phương thức); HC = hand carry.

**Trả lời của KLMAS:**

### Q7. RDD tính từ ETD cộng mấy ngày? *(cần khi làm lịch tính ngược từ RDD)*

- **Ở đâu:** [RECAP 26FW], sheet `ORDER RECAP`: ô L4 ghi `RDD (-12DAY)`, nhưng từ trang thứ 4 trở đi (ô L202, L268, L334…) lại ghi `RDD (-14DAY)`. Ô BB4 ghi `BUYER DEL (RDD-10)`. Sheet `DETAIL` ô L12 ghi `ETD VN (RDD-14 DAYS)`. Biên bản họp ngày 15/10 ghi ETD = RDD − 12 (tàu 7 ngày + nhập kho 5 ngày).
- **Câu hỏi:** quy tắc đúng hiện nay là RDD − 12, RDD − 14, hay tuỳ buyer/phương thức? "BUYER DEL (RDD-10)" là mốc gì?
- *Tạm hiểu:* ETD = RDD − 12.

**Trả lời của KLMAS:**

### Q8. Đơn giá vải ghi theo tiền gì? *(ngoài phạm vi hiện tại)*

- **Ở đâu:** [RECAP 26FW], sheet `FAB(0615)`, cột V (원단단가): dòng 6 ghi 4400 (nơi xuất vải cột T = KR), dòng 7 ghi `5500->5000` (KR), dòng 10 ghi 0.85 (VN), dòng 4 ghi 4.8 (CN).
- **Câu hỏi:** vải từ Hàn ghi bằng KRW, vải từ Trung Quốc và Việt Nam ghi bằng USD, đúng không? Đơn vị tính theo yard hay mét?

**Trả lời của KLMAS:**

### Q9. Các ký hiệu trong ghi chú vật tư nghĩa là gì? *(cần khi làm checklist vật tư)*

- **Ở đâu:** [PRODUCTION STATUS] cột U (PLAN MTR(FAB) SHIP DATE): dòng 6 `6/2ETD-6/6ETA G`, dòng 118 `6/15ETD-6/19ETA G OK`. [RECAP 26FW] các cột AA–AH (MATERIAL SHIP/ETA, LINING, SEWING, LABEL) có `L+P+SNAP`, `SBM`, `C1`.
- **Câu hỏi:** G, C, C1, L, P, OK, SNAP, SBM, L+P+W là gì? (Biên bản họp đã giải thích G = vải chính.)

**Trả lời của KLMAS:**

### Q10. "RE" và "CMMT" trong cột mẫu INLINE nghĩa là gì? *(cần khi theo dõi mốc mẫu)*

- **Ở đâu:** [PRODUCTION STATUS] cột J (INLINE SMPL): dòng 12 `7/16 SENT - 7/20 RE / 7/21 - 2ND SENT / 7/22 CMMT`; dòng 6 `8/1 SENT / 8/3 CMMT`.
- **Câu hỏi:** RE là mẫu bị trả lại (return) hay bị từ chối (reject)? CMMT là đã nhận comment của buyer?
- *Tạm hiểu:* RE = trả lại; CMMT = đã nhận comment.

**Trả lời của KLMAS:**

### Q11. Mã nhóm hàng trong mã style *(cần khi báo cáo theo loại hàng)*

- **Ở đâu:** chữ thứ 6–7 của mã style, vd. CHF3M**JK**6301. Các mã đang có: PT, LT, WT, JK, ST, SK, HP, VT, IT, MK, HC, GW, OP.
- **Câu hỏi:** xin bảng nghĩa của các mã (JK = jacket, PT = pants…), nhất là ST, IT, MK, HC, GW, OP, HP.

**Trả lời của KLMAS:**

### Q12. Quy tắc đặt mã style *(cần khi tự động nhận diện mã)*

- **Ở đâu:** mã dạng CH + **F** + **3** + M + JK + 6301. [RECAP 26FW] có cả mã bắt đầu bằng `CHF2` (dòng 537, 541) và `CHF5` (`CHF5UGW6070`, mã R4, dòng 545).
- **Câu hỏi:** chữ thứ 3 (E/F/G) có phải năm (2025/2026/2027), và số thứ 4 (1–4) là Xuân/Hè/Thu/Đông? Số 5 nghĩa là gì?

**Trả lời của KLMAS:**

### Q16. Năm ETD của 5 style 27SS *(không ảnh hưởng: cả 5 style đều đã huỷ)*

- **Ở đâu:** [RECAP 27SS], sheet `ORDER RECAP`, cột L: CHG1WJK7504 (dòng 25) 17/01/2026; CHG2WJK7604 (dòng 157) 14/03/2026; CHG2MST7238 (dòng 274) và CHG2WST7651 (dòng 348) 21/03/2026; CHFG2WIT7957 (dòng 681) 28/02/2026. Cả 5 đều có trạng thái CANCEL.
- **Câu hỏi:** chỉ để xác nhận: các ngày này đáng lẽ là năm 2027, đúng không?

**Trả lời của KLMAS:**

### Q17. 7 style có trong bảng vải nhưng không có trong ORDER RECAP *(cần khi làm checklist vật tư)*

- **Ở đâu:** [RECAP 26FW], sheet `FAB(0615)`, cột I (품번): CHF3UCP6382 (dòng 212), CHF4MCP6482 (214), CHF4UCP6484 (218), CHF4WCP6876 (222), CHF3MPT6332 (230), CHF3WPT6743 (331), CHF4WSK6851 (788, xem Q3).
- **Câu hỏi:** các style này đã huỷ, đổi mã, hay là phụ kiện (CP) quản lý ở file khác? Vải đã đặt cho chúng được xử lý thế nào?

**Trả lời của KLMAS:**

### Q18. Các khối style mùa trước "CHE4…" trong Shipment Status *(cần khi nạp dữ liệu mùa cũ)*

- **Ở đâu:** [SHIPMENT] sheet `TP(16)` từ dòng 147 và sheet `NATEXCO(15)` từ dòng 106: các khối CHE4WJK5843, CHE4WVT5847, CHE4UNW5485, CHE4MWT5406, CHE4WJK5841. Tất cả đều trống.
- **Câu hỏi:** các khối này còn cần không, hay là mẫu cũ còn sót lại?
- *Tạm hiểu:* bỏ qua.

**Trả lời của KLMAS:**

### Q19. Giá, thanh toán, PO, C/O đang được quản lý ở đâu? *(ngoài phạm vi hiện tại)*

- **Ở đâu:** [RECAP 26FW], sheet `ORDER RECAP`: cột BE (TARGET CMPH), BF (FIXED FACTORY), BG (FINAL 공장 가격 CMPH), CC (FOB PRICE), CF (PO NO// KOREA), CG (PO NO// CHINA), CV (CO SENDING), CW trở đi (thanh toán) gần như để trống.
- **Câu hỏi:** các thông tin này nằm ở file hay hệ thống nào khác? Có cần đưa vào hệ thống sau này không?

**Trả lời của KLMAS:**

### Q20. "(BE: …)" trong ô màu có phải là màu cũ trước khi đổi?

- **Ở đâu:** [RECAP 26FW], sheet `ORDER RECAP`, cột H: dòng 321 `CREAM (BE: INDIE PINK)`, dòng 347 `CREAM (BE: OATMEAL)`, dòng 407 `KHAKI GREY (BE: SAND)`.
- **Câu hỏi:** "BE:" nghĩa là "before" (màu trước khi đổi), đúng không?
- *Tạm hiểu:* đúng.

**Trả lời của KLMAS:**

### Q21. "해리감" trong cột PART của bảng vải là phần nào?

- **Ở đâu:** [RECAP 26FW], sheet `FAB(0615)`, cột Q (PART), dòng 345 (style CHF3WPT6746).
- **Câu hỏi:** 해리감 là phần vải nào của sản phẩm?

**Trả lời của KLMAS:**

### Q22. Có cần lưu ảnh thiết kế trong ORDER RECAP không?

- **Ở đâu:** [RECAP 26FW] cột G (DESIGN) có ảnh thiết kế của từng style.
- **Câu hỏi:** khi làm màn hình ORDER RECAP trên hệ thống, có cần hiển thị ảnh này không?
- *Tạm hiểu:* cần, ở giai đoạn làm ứng dụng.

**Trả lời của KLMAS:**

### Q29. KLMAS có số phút chuẩn (SMV) cho từng style hoặc loại hàng không? *(cần khi so sánh năng suất nhà máy)*

- **Ở đâu:** báo cáo ngày của nhà máy có cột số công nhân (`WORKERS SỐ CÔNG NHÂN`) và số chuyền. Nếu chỉ chia sản lượng cho số công nhân thì nhà máy may áo thun sẽ luôn "năng suất" hơn nhà máy may jacket.
- **Câu hỏi:** KLMAS hoặc nhà máy có bảng SMV (số phút may chuẩn cho một sản phẩm) không?

**Trả lời của KLMAS:**

### Dữ liệu kiểm hàng bên thứ ba (QI1–QI8)

Chỉ cần trả lời nếu PO quyết định đưa dashboard chất lượng kiểm hàng vào giai đoạn 1 (task M1-12). Phân tích chi tiết: `analys-docs/review_qc_third_party.md`.

### QI1. Cột "Pre-FINAL" nghĩa là gì?

- **Ở đâu:** [DỮ LIỆU KIỂM BÊN THỨ BA], sheet `DATA`, cột K (Pre-FINAL). Dòng 2 (style DWDV74066, ngày 01/06) ghi **0,17**; cùng dòng đó cột S (DEFECT RATE) ghi **0,179**. Cột K chỉ có giá trị ở khoảng 1.000 dòng.
- **Câu hỏi:** cột K là tỷ lệ lỗi của lần kiểm pre-final (kiểm trước khi kiểm cuối)? Hay tỷ lệ lỗi làm tròn? Khi nào thì ghi?

**Trả lời của KLMAS:**

### QI2. "PRE-INSPECTION" trong cột BRAND là brand nào?

- **Ở đâu:** sheet `DATA`, cột G (BRAND), **từ dòng 7.123 trở đi** (tháng 10/2026, 2.017 lần kiểm) ghi `PRE-INSPECTION` thay vì tên brand. Cột H (VENDOR) vẫn có: DAEHAN GLOBAL KOREA, SCORVV, EUNSUNG, MISEONG, FIL, KOFA… Các dòng này cũng thường trống cột A (LOCATION) và cột V (QC NAME).
- **Câu hỏi:**
  1. "PRE-INSPECTION" là một loại kiểm (kiểm trước) chứ không phải brand, đúng không?
  2. Brand thật của các lần kiểm này là gì (vd. DAEHAN GLOBAL → 8 SECONDS)?
  3. Có thể bổ sung tên kiểm viên và khu vực cho các dòng này không?

**Trả lời của KLMAS:**

### QI3. Cột "NUMBER ORDER" có phải là lần kiểm thứ mấy?

- **Ở đâu:** sheet `DATA`, cột E. Style DWDV74066 màu CRS: ngày 01/06 ghi 1, 02/06 ghi 2, 03/06 ghi 3, 16/06 ghi 4. Trên phiếu giấy, ô này tương ứng "차수 / lần".
- **Câu hỏi:** đây là lần kiểm thứ mấy của cùng style + màu, đúng không? Đếm theo màu hay theo cả style?

**Trả lời của KLMAS:**

### QI4. Một sản phẩm lỗi có thể ghi nhiều mã lỗi không?

- **Ở đâu:** sheet `DATA`:
  - Với DISCOVERY và FILA, SL lỗi (cột O) luôn bằng tổng số đếm theo mã (cột Q MINOR + cột R MAJOR). Ví dụ dòng 2–11: 38 = 1+5+2+1+1+6+12+2+7+1.
  - Với PRE-INSPECTION thì không. Ví dụ dòng 7.123 (RY6938P07R): SL lỗi **82** nhưng các mã chỉ cộng lại **5**. Có 285 lần kiểm như vậy.
- **Câu hỏi:** khi một sản phẩm có 2 lỗi, kiểm viên ghi 1 hay 2? Vì sao ở phần PRE-INSPECTION, tổng theo mã nhỏ hơn nhiều so với SL lỗi?

**Trả lời của KLMAS:**

### QI5. Khi nào kết quả là PASS, khi nào REJECT?

- **Ở đâu:**
  - [BÁO CÁO KIỂM MẪU] FNJWD8411, trang 1: tỷ lệ lỗi **23,9%**, kiểm 100%, kết quả **PASS**.
  - [DỮ LIỆU KIỂM BÊN THỨ BA] sheet `DATA`, cột U (REMARK): 264 dòng ghi `REJECT DEFECT xx%`, có lần chỉ 20,8%.
  - Trên [PHIẾU KIỂM], phần lấy mẫu có AQL major 2.5, minor 4.0.
- **Câu hỏi:**
  1. Với kiểm 100%, PASS nghĩa là "đã sửa hết hàng lỗi" chứ không theo tỷ lệ, đúng không?
  2. Với kiểm lấy mẫu, ngưỡng REJECT tính theo bảng AQL hay theo % riêng của từng brand?
  3. Sheet DATA không có cột kết quả. Có thể thêm cột PASS/REJECT không?

**Trả lời của KLMAS:**

### QI6. Các nhóm mã lỗi A–G dùng cho loại hàng nào?

- **Ở đâu:** [DỮ LIỆU KIỂM BÊN THỨ BA], sheet `CODE`: 296 mã chia nhóm A (62 mã), B (58), C (47), D (34), E (36), F (31), G (28). Dữ liệu hiện chỉ dùng nhóm A.
- **Câu hỏi:** đoán là A = quần áo, B = túi, C = giày, G = mũ. Còn D, E, F là gì? Phiếu giấy cho từng loại hàng có khác nhau không?

**Trả lời của KLMAS:**

### QI7. Có dòng nào bị nhập trùng không?

- **Ở đâu:** sheet `DATA`: có 266 nhóm lần kiểm trùng hoàn toàn style, màu, ngày, SL kiểm và kiểm viên.
- **Câu hỏi:** cùng ngày có thể kiểm cùng style + màu 2 lần với cùng số lượng (vd. 2 lô khác nhau) không? Nếu không thì đây là nhập trùng.

**Trả lời của KLMAS:**

### QI8. Ai nhập file INPUT DATA và nhập khi nào?

- **Câu hỏi:** file này có phải là nơi duy nhất tổng hợp mọi phiếu kiểm của văn phòng không? Ai nhập, nhập trong ngày hay cuối tuần? Báo cáo PDF gửi khách (như FNJWD8411) có được làm từ file này không, hay làm riêng?

**Trả lời của KLMAS:**

### Q-T6. Sẽ mở rộng sang brand nào tiếp theo?

- **Câu hỏi:** sau CHALLENGER (và 8 SECONDS), brand nào nên đưa vào tiếp theo? Brand đó có file ORDER RECAP / báo cáo kiểm theo mẫu riêng không?

**Trả lời của KLMAS:**

### Dữ liệu xin sau giai đoạn 1

| Mã | Cần gửi | Để làm gì | Trạng thái |
|---|---|---|---|
| R1 | ORDER RECAP, Shipment Status, Production Status của 1–2 mùa CHALLENGER đã kết thúc | So sánh các mùa, đánh giá nhà máy | Chưa nhận |
| R2 | Minimap / order list của ít nhất 2 brand khác | Tự động đọc minimap | Chưa nhận |
| R3 | 1 tuần báo cáo kiểm chi tiết (có mã lỗi, ảnh) và mẫu báo cáo kiểm của 3–6 brand | App kiểm hàng, PDF theo brand | Chưa nhận |
| R4 | Danh sách kiểm viên, khu vực, nhà máy phụ trách; địa chỉ các nhà máy | Gợi ý phân công kiểm viên | Chưa nhận |
| R6 | 20–30 email / tin nhắn Kakao với buyer (có thể che thông tin nhạy cảm) | Tự động đọc yêu cầu thay đổi, gợi ý trả lời | Chưa nhận |

---

# Phụ lục (dành cho đội dự án, không gửi KLMAS)

**Quyết định nội bộ ASTRA, không hỏi KLMAS:**
- **T1:** giai đoạn 1 chỉ báo cáo và đối soát từ file; ứng dụng nhập liệu làm sau.
- **T2:** hạ tầng production dự kiến PostgreSQL managed (AWS Singapore); giai đoạn 1 chạy DuckDB cục bộ.
- **T3:** chưa dùng công cụ BI ngoài; dùng dashboard HTML của kho dữ liệu.
- **T7:** lưu dữ liệu raw 2 năm.

**Giả định kỹ thuật đã áp dụng khi phân tích:**
- Số và ngày lấy từ giá trị Excel đã lưu (không tính lại công thức).
- `.xlsb` đọc qua bản chuyển bằng LibreOffice để lấy màu ô.
- PDF chỉ đọc phần chữ, chưa OCR các trang ảnh.
- Mọi thống kê là đếm đầy đủ, không lấy mẫu.

**Khi KLMAS trả lời:** PO ghi câu trả lời vào đây, kèm ngày và người trả lời. Sau đó cập nhật cấu hình tương ứng (`dw/kops_dw/config.py`) và golden test nếu số liệu thay đổi.
