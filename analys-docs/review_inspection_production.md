# Rà soát nguồn mới: INSPECTION và PRODUCTION (19/10/2026)

Phạm vi: 10 file `.xlsx` mới trong `raw-docs/INSPECTION/` và `raw-docs/PRODUCTION/`. *(Ngày 19/10 `raw-docs` đã được sắp xếp lại: bảng kiểm nay ở `INSPECTION/ORDER_TRACKING/CHALLENGER/26FW/`, 2 bản trùng ở `_DUPLICATES/`; xem `raw-docs/README.md`.)* Chỉ đọc, không sửa file nguồn. Số liệu dưới đây được tính bằng script trên dữ liệu thật, đối chiếu với kho `dw/build/kops.duckdb` (ORDER RECAP, Production Status, Shipment Status).

> Quy ước: **[Q]** quan sát trực tiếp · **[S]** suy luận · **[R]** khuyến nghị cho MVP

## 1. Danh mục

| Nhóm | File | Nội dung | Ghi chú |
|---|---|---|---|
| PRODUCTION / CHALLENGER / 26FW | 6 nhà máy: DONG MY, HA HIEU, MTT, NATEXCO, TAN BINH MINH, TRUONG PHUC | **Báo cáo sản xuất ngày** (Daily Production Report): mỗi sheet là một ngày; mỗi dòng là style × màu × size; có cắt / in-thêu / vào chuyền / ra chuyền, mỗi công đoạn chia TODAY / TTL / BAL; kèm chuyền số, số công nhân, ETD | 476 sheet, khoảng 43.900 dòng màu × size. Cùng một template (47 cột), riêng TBM có 48 cột |
| PRODUCTION / DHG (DAEHAN GLOBAL) / 8 SECONDS / 26FW | 1 file, nhà máy HAGACO | Báo cáo sản xuất ngày của **một khách khác** (buyer SAMSUNG, mã style dạng `LEV-24059 #424939LYD`) | Template khác: không có cột in/thêu, có cột RDD và RMKS |
| INSPECTION | 1 file, người lập HOA | **Bảng theo dõi kiểm hàng của KLMAS** theo nhà máy: SL đạt theo ngày, theo style × màu; dòng tổng gồm SL kiểm, SL lỗi, số kiểm viên, tên kiểm viên | 10 sheet (5 ẩn). Đây là bảng tổng hợp, **không phải** báo cáo kiểm chi tiết theo mã lỗi |

**Bản trùng [Q]:** `261016R … TBM` giống hệt `261016 … TBM` (cùng MD5). File `261002 … (CHALLENGER - MTT)` có ở cả thư mục `MTT/` và `DONG MY/`; bản trong `DONG MY/` là đặt nhầm thư mục.

## 2. Phát hiện chính

### 2.1 Báo cáo ngày cho thấy Production Status chậm và cảnh báo trễ hiện tại bị thổi phồng

- **[Q] Style W33 CHF4MPT6444 (TBM):** Production Status (ngày 12/10) ghi đã may 10, SL/ngày 10, nên DW dự báo trễ **49 ngày**. Báo cáo ngày của TBM cho thấy sản lượng ra chuyền tăng dần: 10 → 30 → 45 → 50 → 55 pcs/ngày (11/10 đến 15/10). Đến 15/10 đã ra chuyền **190/350**.
- **[S]** Với khoảng 55 pcs/ngày, còn 160 pcs, dự kiến xong may khoảng 19/10 (nghỉ Chủ nhật), sẵn sàng xuất khoảng 24/10, tức trễ khoảng **17 ngày** so với ETD 07/10 (không phải 49). Bảng kiểm hàng cũng ghi "REQUEST ETD 10/15" và "10/20" cho nhiều style cùng đợt.
- **[Q] 14 / 101 style** có SL ra chuyền trong báo cáo ngày khác Production Status. Lệch lớn nhất: CHF4WPT6846 (290 so với 50), CHF4MJK6404 (380 so với 227).
- **[R]** Dùng báo cáo ngày làm nguồn sự thật cho tiến độ may. Dự báo dùng **trung bình trượt 3–5 ngày gần nhất** thay cho SL của một ngày. Production Status chỉ dùng để đối soát.

### 2.2 Báo cáo ngày không đều và có lúc ngừng hẳn

| Nhà máy | Ngày đầu | Ngày cuối | Khoảng trống > 3 ngày |
|---|---|---|---|
| TAN BINH MINH | 01/07 | **15/10** | 2 lần × 5 ngày |
| TRUONG PHUC | 06/07 | **14/10** | không |
| MTT | 03/07 | 02/10 | 35 ngày (04/08 → 08/09) |
| DONG MY | 13/07 | 28/09 | 22 ngày, 13 ngày |
| HA HIEU | 26/09 | 28/09 | chỉ có 2 ngày |
| NATEXCO | 13/08 | **08/09** | 22 ngày |

- **[Q]** Báo cáo cuối của NATEXCO là 08/09, lúc đó CHF4WVT6813 mới cắt 200/700 và chưa ra chuyền. Production Status ngày 12/10 lại ghi style này đã xong. Phần sản xuất sau 08/09 không có báo cáo ngày nào.
- **[Q]** 14 / 110 style đang chạy **không khớp được với báo cáo ngày nào**. Sau khi map 4 mã TBM gõ sai chữ mùa (§2.9), còn **9 style thật sự không có báo cáo**: NATEXCO 4, HA HIEU 2, TBM 1, TIEN THANH 1, FG VINA 1.
- **[R]** Thêm chỉ số **độ tươi dữ liệu** cho từng nhà máy (số ngày kể từ báo cáo gần nhất) lên Control Tower, cảnh báo khi quá 2 ngày làm việc. Đây là cách sớm nhất để biết tiến độ đang "mù".

### 2.3 Ngày tháng trong báo cáo ngày không đáng tin

- **[Q] TBM:** ô ngày ở C2 lẫn nhiều kiểu: số serial Excel bị đảo ngày/tháng (45664 = 07/01/2025 thay vì 01/07/2026), text `13/7/2025` (sai năm), tên sheet `13.01`, `14.01`, `15.01` thực ra là 13–15/10. Các file khác dùng tên sheet `m.d` (`9.28`), còn TBM dùng `dd.mm` (`28.09`).
- **[Q] DHG:** cột "FINAL ETD HAI PHONG" ghi năm 2024 cho đơn mùa 26FW.
- **[Q]** TRUONG PHUC có sheet ẩn `7.281` (bản nháp trùng ngày 28/7).
- **[R]** Lấy ngày báo cáo theo thứ tự: tên sheet (biết quy ước từng nhà máy) → ngày trong ô → kiểm tra bằng năm của mùa và bằng ngày trên tên file. Lệch thì ghi issue `REPORT_DATE_CONFLICT`. Không bao giờ tin riêng ô C2.

### 2.4 Sheet "co lại" khi style xong, nên phải lấy lần xuất hiện cuối của từng style

- **[Q]** Sheet mới nhất của TBM (15/10) chỉ còn 2 style, trong khi TBM có 36 style trong tháng 7–10: nhà máy xoá dòng style đã xong khỏi sheet ngày.
- **[R]** Parser lấy snapshot **cuối cùng của từng style** (style × màu × size) trên toàn bộ sheet, không chỉ đọc sheet mới nhất. Bỏ qua bản trùng theo MD5.

### 2.5 Có đủ dữ liệu để theo dõi trọn chuỗi số lượng ở mức màu × size

- **[Q]** 67 style CHALLENGER còn trong sheet cuối của từng nhà máy: đặt 40.367 → cắt 39.867 → vào chuyền 38.247 → ra chuyền 37.026.
- **[Q]** Có cắt thiếu: CHF4WVT6813 mới cắt 200/700 tính đến 08/09. DHG `LEV-26109` đợt 2 cắt 947/1.700.
- **[Q]** 1 style lệch SL đặt: CHF4WLT6836 báo cáo ngày ghi 340, ORDER RECAP ghi 350.
- **[R]** Gộp với Shipment Status (đã xuất theo màu × size) thành **funnel** cho mỗi style: đặt → cắt → vào chuyền → ra chuyền → kiểm đạt → xuất. Đây chính là yêu cầu #6 và #7 trong buổi họp, và là màn hình buyer muốn xem.

### 2.6 Năng suất theo chuyền: có tín hiệu nhưng cần chuẩn hoá theo loại hàng

- **[Q]** Trung vị số pcs / công nhân / chuyền-ngày: DONG MY 17, TBM 8,8, TRUONG PHUC 6,8, NATEXCO 5,2, MTT 3,6, HAGACO 5,4.
- **[S]** Không so sánh trực tiếp được: DONG MY chủ yếu làm áo thun, MTT và NATEXCO làm jacket. Ngoài ra cột số công nhân thường chỉ ghi ở dòng đầu mỗi style.
- **[R]** Chỉ đưa vào scorecard khi đã chuẩn hoá theo nhóm hàng (mã item trong style: JK, WT, PT…) hoặc theo SMV, nếu KLMAS có số liệu SMV.

### 2.7 Bảng kiểm hàng: dùng được cho SL đạt, chưa dùng được cho chất lượng

- **[Q]** 20 style, 34 ngày kiểm (27/07–14/10), 16 tên kiểm viên (có cả "THỜI VỤ" là kiểm viên thời vụ). 1–2 kiểm viên/ngày cho mỗi nhà máy.
- **[Q] Định nghĩa lỗi không rõ:** "DEFECT QTY" thường lớn hơn nhiều so với SL kiểm (ví dụ NATEXCO 946 lỗi / 1.407 kiểm). Dòng "DEFECT RATE" của file tính bằng lỗi ÷ **SL đạt** (ra 177%). Sheet ẩn `TP (4)` có 1.440 lỗi nhưng 0 SL kiểm.
- **[S]** Rất có thể "lỗi" là số điểm lỗi tìm thấy (một sản phẩm có thể có nhiều lỗi, sửa xong vẫn đạt), không phải số sản phẩm bị loại. Bảng không có mã lỗi, ảnh hay AQL.
- **[Q] Copy-paste lẫn dữ liệu:** các sheet `HÀ HIẾU`, `FG`, `MTTD` vẫn còn dòng của CHF4WJK6801 (style của NATEXCO) chép từ sheet NATEXCO, nhưng gắn vào header ngày của sheet mới, nên cùng con số xuất hiện ở ngày khác. Cộng thô sẽ ra 2.611 đạt cho một đơn 350.
- **[Q] Sheet ẩn là các đợt cũ chồng lên nhau:** `TP (2)`, `(3)`, `(4)` lặp lại cùng style.
- **[Q] Bộ 2 món:** CHF4WJK6801 được kiểm riêng VEST và JACKET (mỗi món 350). ORDER RECAP chỉ có 1 dòng style.
- **[Q]** Cột Remark chứa **yêu cầu đổi ETD** dạng tự do: "REQUEST ETD 10/15" (5 style NATEXCO), "10/20" và "10/25" (3 style TRUONG PHUC).
- **[R]** MVP chỉ nạp **SL đạt theo ngày**, mỗi (style, màu, món, ngày) lấy một lần. Chỉ nhận style khi khớp nhà máy theo ORDER RECAP, nếu không thì ghi issue `INSPECTION_STYLE_FACTORY_MISMATCH`. Chưa tính tỷ lệ lỗi cho tới khi KLMAS định nghĩa lại (câu hỏi mới Q24). Trích "REQUEST ETD" thành đề xuất đổi ETD đưa vào cùng hàng chờ duyệt với email.

### 2.8 Đa khách hàng là thật, không phải chuyện tương lai

- **[Q]** File DHG: vendor Daehan Global, brand 8 SECONDS, buyer SAMSUNG, nhà máy HAGACO; 8 style, đặt 12.740, ra chuyền 10.230 (15/10). Mã style không theo dạng `CH…`, RDD còn nằm lẫn trong ô mã style ("RDD 1ST: 10/27").
- **[R]** Đưa `client / brand` thành chiều bắt buộc ngay từ DW: lấy từ đường dẫn `PRODUCTION/<KHÁCH>/<BRAND>/<MÙA>/<NHÀ MÁY>/`. Mỗi brand có quy tắc mã style riêng (regex). Chuẩn bị RLS theo brand: buyer CHALLENGER không được thấy dữ liệu 8 SECONDS và ngược lại.

### 2.9 Bằng chứng mới cho câu hỏi Q05 (mã style)

- **[Q]** TBM báo cáo sản xuất dưới mã `CHF4WSK6851`, giống Shipment Status. Chỉ ORDER RECAP dùng `CHF4WHP6851`, nên 2/3 nguồn đang dùng `WSK`.
- **[Q]** Báo cáo ngày của TBM ghi `CHE3WPT6986`, `CHE3WSK6754`, `CHE4MPT6441`, `CHE4WPT6842`. ORDER RECAP 26FW có đúng 4 style `CHF…` cùng số, giao cho TBM, và 4 style này không có báo cáo ngày nào dưới mã `CHF`. **[S]** Gần như chắc chắn là gõ sai chữ mùa (E thay F), không phải reorder. Cần KLMAS xác nhận (Q06).

## 3. Đề xuất bổ sung cho MVP (theo thứ tự ưu tiên)

| # | Việc | Giá trị | Công sức [S] |
|---|---|---|---|
| 1 | **Parser báo cáo sản xuất ngày** (`daily_production`): đọc theo header; ngày theo §2.3; lấy lần xuất hiện cuối của từng style; bỏ bản trùng; lấy client/brand/factory từ đường dẫn | Tiến độ thật theo ngày, ở mức màu × size | 1 ngày |
| 2 | **Dự báo bằng trung bình trượt** (3–5 ngày), thay `daily_output` của Production Status; giữ Production Status để đối soát | Bỏ cảnh báo sai (W33: 49 → khoảng 17 ngày) | 0,5 ngày |
| 3 | **Độ tươi dữ liệu theo nhà máy** + danh sách style không có báo cáo ngày | Biết chỗ nào đang "mù" | 0,5 ngày |
| 4 | **Funnel style**: đặt → cắt → vào chuyền → ra chuyền → kiểm đạt → xuất, ở mức màu × size, thêm vào Style 360 | Yêu cầu #6, #7, #13 | 0,5 ngày |
| 5 | **Parser bảng kiểm** (chỉ SL đạt theo ngày, lọc theo nhà máy, tách món VEST/JACKET) + đếm kiểm viên/ngày | Nền cho dashboard QC và phân công kiểm viên (yêu cầu #12) | 1 ngày |
| 6 | Trích **"REQUEST ETD"** từ Remark thành `change_proposal` | Một hàng chờ duyệt chung cho mọi nguồn | 0,25 ngày |
| 7 | **Chiều client/brand** trong core và dashboard (chọn brand cạnh chọn mùa) | Đa khách hàng, chuẩn bị RLS | 0,5 ngày |
| 8 | Quy ước thư mục nguồn + validator (tên file và thư mục phải khớp nhà máy; cảnh báo file đặt nhầm thư mục) | Giảm lỗi nạp nhầm | 0,25 ngày |

Không nên làm ngay: tỷ lệ lỗi và scorecard chất lượng kiểm viên (định nghĩa lỗi chưa rõ); năng suất theo công nhân (chưa chuẩn hoá theo loại hàng).

## 4. Câu hỏi mới cho KLMAS (bổ sung vào `open_questions.md`)

| # | Ưu tiên | Câu hỏi | Giả định đề xuất |
|---|---|---|---|
| Q02 | P1 | Báo cáo sản xuất ngày có phải nguồn chính thức cho SL cắt / vào chuyền / ra chuyền không? Production Status lấy số từ đâu, cập nhật lúc nào? | Báo cáo ngày là nguồn chính; Production Status dùng để đối soát |
| Q03 | P1 | Vì sao NATEXCO ngừng gửi báo cáo ngày sau 08/09 và HA HIEU chỉ có 2 ngày? Còn file nào chưa gửi không? | Thiếu file, xin bổ sung |
| Q24 | P1 | "DEFECT QTY" trong bảng kiểm là số sản phẩm lỗi hay số điểm lỗi? Tỷ lệ lỗi chính thức tính trên SL kiểm hay SL đạt? | Số điểm lỗi; tỷ lệ = lỗi ÷ SL kiểm |
| Q11 | P2 | Style bộ (VEST + JACKET như CHF4WJK6801): SL đặt 350 là 350 bộ hay 350 mỗi món? Xuất hàng tính theo bộ hay theo món? | 350 bộ = 350 mỗi món |
| Q06 | P1 | 4 mã `CHE…` trong báo cáo ngày TBM có phải gõ sai của `CHF…` cùng số trong ORDER RECAP? | Gõ sai; map sang `CHF…`, đánh dấu chưa xác nhận |
| Q15 | P2 | Dữ liệu DHG / 8 SECONDS có nằm trong phạm vi KOPS giai đoạn 1 không? Buyer DHG có được xem dashboard không? | Có nạp vào DW, ẩn khỏi buyer CHALLENGER |
| Q41 | P3 | Có số SMV (standard minute value) theo style hoặc theo nhóm hàng để chuẩn hoá năng suất không? | Chưa có |
