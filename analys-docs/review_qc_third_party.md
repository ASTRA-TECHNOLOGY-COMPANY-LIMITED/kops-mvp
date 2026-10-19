# Rà soát nguồn mới: quy trình và dữ liệu kiểm hàng bên thứ ba (19/10/2026)

Phạm vi: 5 file KLMAS gửi trong thư mục `INPUT DATA & ANALYSIS`. Sau khi sắp xếp lại, các file nằm ở `raw-docs/INSPECTION/THIRD_PARTY/`, `FORMS/` và `SAMPLES/` (xem `raw-docs/README.md`). Chỉ đọc. Số liệu đếm đầy đủ bằng script, không lấy mẫu.

> Quy ước: **[Q]** quan sát trực tiếp · **[S]** suy luận · **[R]** khuyến nghị

## 1. Bộ file này mô tả trọn quy trình kiểm hàng bên thứ ba

Đây là mảng kinh doanh thứ hai của KLMAS (biên bản họp mục 2-3: kiểm hàng cho khoảng 50 khách như FILA, Discovery). Năm file ghép lại thành một chuỗi hoàn chỉnh:

```
① Phiếu giấy tại nhà máy   →   ② Nhập Excel ở văn phòng     →   ③ Báo cáo PDF gửi khách
FORMS/…(FORM) - 2026.pdf         THIRD_PARTY/INPUT DATA.xlsx        SAMPLES/FNJWD8411 261001 (REPORT FJ).pdf
SAMPLES/REPORT.jpg (đã điền)     sheet DATA (1 dòng = 1 mã lỗi)     9 trang: kết quả, lỗi, đo size, ảnh
                                 sheet CODE (bảng mã lỗi)
```

| File | Nội dung [Q] |
|---|---|
| `FORMS/KLMAS INSPECTION REPORT (FORM) - 2026.pdf` / `.xlsx` | Phiếu kiểm trống, song ngữ Hàn–Việt. Phần đầu: PROMOTION (vendor), FACTORY, BRAND/PO, STYLE, ITEM, COLOR, ORDER/BOOK QTY, **lần kiểm (차수/lần)**, SL kiểm, SL lỗi minor/major, tỷ lệ lỗi, ngày, loại kiểm (**Sampling / 100%**), chữ ký kiểm viên và nhà máy. Phần giữa: lấy mẫu AQL (major 2.5, minor 4.0), Liner/Reversible/Detachable, nhận xét, **PASS/REJECT**. Phần dưới: lưới khoảng 60 mã lỗi chia 5 nhóm (vải chính, vải lót, phụ liệu, kỹ thuật may, hoàn thiện), mỗi mã có ô đếm mi/ma và ghi chú. File `.xlsx` có 3 sheet: mẫu báo cáo (B), mẫu "FOR QC" cũ và "FOR QC 2026" |
| `SAMPLES/REPORT.jpg` | Ảnh một phiếu đã điền tay: vendor KOFA, nhà máy APC, style QC6X380G34, màu ASH, đặt 250, kiểm 58, 6 lỗi minor (A23 ×3, A08 ×2, A37 ×1), 10,3%, ngày 15/10/2026, PASS |
| `THIRD_PARTY/INPUT DATA.xlsx` | Sheet **DATA**: 9.705 dòng = **3.124 lần kiểm** (01/06 → 17/10/2026). Mỗi lần kiểm có 1 dòng thông tin, tiếp theo là các dòng chỉ ghi mã lỗi (cột thông tin để "-"). Sheet **CODE**: 296 mã lỗi tiếng Hàn chia 7 nhóm A–G. Sheet **FORM**: dòng tiêu đề trống (mẫu nhập) |
| `SAMPLES/FNJWD8411 261001 (REPORT FJ).pdf` | Báo cáo hoàn chỉnh 9 trang: vendor MAVEN, nhà máy LONG PHUNG VU 2, brand FOOTJOY, áo vest lông vũ, kiểm 100% (348 cái), 83 lỗi = 23,9%, kết quả **PASS**. Có Pareto lỗi theo mã, biểu đồ tỷ lệ lỗi 2 lần gần nhất, bảng đo size (ảnh chụp bản viết tay), kiểm tra tài liệu (worksheet, PP/TOP comment), ảnh sản phẩm, ảnh kiểm viên, ảnh từng lỗi |

**[S]** Phiếu giấy và báo cáo PDF dùng cùng bộ mã lỗi với sheet CODE. Hiện mỗi lần kiểm phải ghi tay, nhập lại Excel, rồi dựng PDF bằng tay. Đây chính là quy trình "70–100 báo cáo/ngày" mà biên bản họp muốn số hoá.

## 2. Dữ liệu INPUT DATA: con số chính

| Chỉ số | Giá trị [Q] |
|---|---|
| Lần kiểm | 3.124 (261 tổ hợp style × màu, 184 mã style) |
| Thời gian | 01/06 → 17/10/2026 |
| SL đã kiểm / SL lỗi | 315.745 / 68.678 → **21,8%** |
| Điểm lỗi theo mã | 68.653 (major 47.140, minor 21.513) |
| Nhóm "brand" | DISCOVERY 1.009 lần kiểm; FILA 98; **PRE-INSPECTION 2.017** (không phải brand, xem §3.2) |
| Vendor / nhà máy / loại hàng | 23 / 31 / 33 |
| Khu vực | THAI BINH, HAI DUONG, NINH BINH, THANH HOA, HCM, NAM DINH |
| Kiểm viên | 37 cách ghi tên khác nhau (thường là nhóm "Binh, Thuy, Huong, Hue") |
| Năng suất | Trung bình 25,6 lần kiểm/ngày (cao nhất 194). Trung vị khoảng 600 cái kiểm/ngày cho mỗi nhóm kiểm viên |

### 2.1 Pareto lỗi (toàn bộ dữ liệu)

| Mã | Lỗi | Điểm lỗi | % | Cộng dồn |
|---|---|---|---|---|
| A08 | 오염/이염 (bẩn, lem màu) | 15.282 | 22,3% | 22,3% |
| A37 | 제사처리 (thừa chỉ) | 14.187 | 20,7% | 42,9% |
| A23 | 봉탈 (bung sút) | 4.854 | 7,1% | 50,0% |
| A26 | 파카링 (nhăn đường may) | 3.046 | 4,4% | 54,4% |
| A27 | 찝힘 (nhíu) | 2.888 | 4,2% | 58,6% |
| A42 | 아이롱상태 (lỗi là ủi) | 2.848 | 4,1% | 62,8% |
| A38 | 형태 불량 (lỗi hình dáng) | 2.312 | 3,4% | 66,2% |

**Insight [S]:** chỉ 2 lỗi hoàn thiện (bẩn và thừa chỉ) đã chiếm **43% tổng điểm lỗi**. Đây là lỗi khâu đóng gói/hoàn thiện, sửa được bằng quy trình chứ không phải lỗi kỹ thuật may. Phản hồi lỗi hằng ngày cho nhà máy (ý tưởng 21 trong roadmap) nhắm vào 2 mã này sẽ có hiệu quả lớn nhất.

### 2.2 Tỷ lệ lỗi theo nhà máy (≥ 30 lần kiểm)

Cao nhất: SON HA GLOBAL 56,2%, FG 42,2% (cả hai thuộc vendor **DAEHAN GLOBAL KOREA**), IVY 38,6%, HUNG THINH PHAT 36,9%, HAI DUONG 2 (DAEHAN) 36,6%, HOA HONG 35,0%.
Thấp nhất: NAM THUAN 10,3%, THO XUAN 15,6%, SEYANG 15,9%, GEU LIM THAI BINH 18,2%, DAC TRAN 18,6%.

**[S]** Tên SON HA và FG cũng xuất hiện ở phía sản xuất CHALLENGER (ORDER RECAP 27SS có nhà máy SON HA; 26FW có FG VINA). Hai mảng kinh doanh đang **dùng chung nhà máy**. Kho dữ liệu có thể cho ra một scorecard nhà máy chung (tiến độ từ mảng sản xuất, chất lượng từ mảng kiểm hàng). Đây là bằng chứng cho Q08.

### 2.3 Kết quả PASS / REJECT

- **[Q]** Báo cáo FNJWD8411: lỗi 23,9% nhưng kết quả **PASS** (kiểm 100%, hàng lỗi sửa lại rồi đạt). Trong INPUT DATA, cột REMARK có 30+ dòng `REJECT DEFECT xx%` với tỷ lệ từ 20,8% đến 60%.
- **[S]** Không có cột kết quả PASS/REJECT riêng. Ngưỡng từ chối không suy ra được (có PASS ở 23,9% và REJECT ở 20,8%). Rất có thể ngưỡng khác nhau theo brand hoặc loại kiểm (100% hay lấy mẫu).

## 3. Chất lượng dữ liệu

| # | Vấn đề [Q] | Ví dụ (file `INPUT DATA.xlsx`, sheet DATA) | Ảnh hưởng |
|---|---|---|---|
| 1 | Một lần kiểm trải trên nhiều dòng, dòng sau ghi `-` ở các cột thông tin | Dòng 2–11: cùng một lần kiểm DWDV74066 ngày 01/06, mỗi dòng một mã lỗi | Parser phải ghép theo khối: dòng có ORDER Q'TY là đầu lần kiểm mới |
| 2 | "Brand" = `PRE-INSPECTION` cho 2.017 lần kiểm (tháng 10) | Cột G từ khoảng dòng 7.123 trở đi | Không biết brand thật; vendor vẫn có (DAEHAN GLOBAL KOREA, SCORVV, EUNSUNG…) |
| 3 | Thiếu khu vực (cột A): 1.934 lần kiểm; thiếu tên kiểm viên (cột V): 2.115 lần kiểm, gần như toàn bộ là PRE-INSPECTION | — | Chưa phân tích được theo khu vực hay kiểm viên cho tháng 10 |
| 4 | Tổng điểm lỗi theo mã ≠ SL lỗi: 285 lần kiểm, chủ yếu ở PRE-INSPECTION | Dòng 7.123: RY6938P07R, SL lỗi 82 nhưng các mã cộng lại 5 | Hai cách nhập khác nhau trong cùng một sheet |
| 5 | PASS + DEFECT ≠ INSPECTION: 540 lần kiểm; cột PASS trống: 1.712 lần kiểm | Dòng 455: DWPTS8066 kiểm 18, đạt 18, lỗi 3 | Không tin được cột PASS; tính đạt = kiểm − lỗi |
| 6 | Có thể nhập trùng: 266 nhóm cùng style, màu, ngày, SL kiểm, kiểm viên | — | Cần KLMAS xác nhận trước khi cộng |
| 7 | Cột K "Pre-FINAL" gần bằng tỷ lệ lỗi nhưng không trùng | Dòng 2: K = 0,17, S = 0,179 | Không rõ nghĩa |
| 8 | Mã lỗi viết thường | 1 dòng ghi `a23` | Chuẩn hoá chữ hoa |
| 9 | Tên kiểm viên là chuỗi nhiều người | "Hoai, Yen, Ngoc, Nguyet" | Tách theo dấu phẩy nếu cần đếm theo người |

Bảng mã lỗi (sheet CODE): 296 mã, chia 7 nhóm A–G. **[S]** A = may mặc (dữ liệu hiện chỉ dùng nhóm A, 51 mã), B = túi (có "기리메" sơn cạnh, "자석" nam châm), C = giày ("앞코" mũi giày), G = mũ ("꼭지단추" nút đỉnh mũ). Cần KLMAS xác nhận (Q28).

## 4. Ý nghĩa cho MVP và các giai đoạn sau

1. **Dữ liệu sạch nhất và nhiều nhất hiện có.** Một bảng phẳng, có mã lỗi chuẩn, 4,5 tháng lịch sử, 23 vendor. Đưa vào kho dữ liệu rất rẻ (khoảng 1 ngày) và cho ngay một dashboard chất lượng có giá trị: Pareto lỗi, tỷ lệ lỗi theo nhà máy, vendor, tháng, loại hàng; số lần kiểm và năng suất kiểm viên.
2. **Đặc tả có sẵn cho app kiểm hàng (P3).** Phiếu FORM 2026 là bố cục màn hình nhập; sheet CODE là danh mục mã lỗi; báo cáo FNJWD8411 là mẫu PDF đầu ra. App chỉ cần thay bước "giấy → nhập lại Excel → dựng PDF".
3. **Scorecard nhà máy dùng chung cho 2 mảng** (§2.2), sau khi chuẩn hoá tên nhà máy (Q08).
4. **Đơn vị "lỗi" ở đây đã rõ hơn:** với DISCOVERY và FILA, SL lỗi = tổng số đếm theo mã, và tỷ lệ = lỗi ÷ SL kiểm. Đây là gợi ý trả lời Q22 cho bảng theo dõi của HOA, nhưng vẫn cần KLMAS xác nhận vì bảng của HOA cho số rất khác.

**[R] Đề xuất:** thêm task **M1-12** (tuỳ chọn, khoảng 8 giờ) vào Phase 1: nạp INPUT DATA + bảng mã lỗi và thêm tab "Chất lượng kiểm hàng" vào dashboard. Đây là phần demo được ngay cho mảng kiểm hàng mà không phải chờ app. Cần PO quyết định có đưa vào Phase 1 không (chi tiết ở `plans/MVP_PHASE1_PLAN.md`).

## 5. Câu hỏi mới cho KLMAS

Đã thêm vào `open_questions.md` (Q23–Q30, Ưu tiên 3; chỉ cần nếu làm M1-12).
