# Rà soát nguồn mới: ORDER RECAP nhiều khách và các phiên bản CHALLENGER (20/10/2026)

Phạm vi: 2 thư mục mới trong `raw-docs/`: `ORDER RECAP` (12 file) và `PRODUCTION PLAN`. Chỉ đọc. Số liệu đếm bằng script trên toàn bộ file. Các phiên bản CHALLENGER được so sánh bằng chính parser của `dw/`.

> Quy ước: **[Q]** quan sát trực tiếp · **[S]** suy luận · **[R]** khuyến nghị cho MVP

## 0. Kết quả quét

| Hạng mục | Kết quả |
|---|---|
| File trùng nội dung (MD5) với file đã có | **Không có.** Các file ORDER RECAP mới là phiên bản khác ngày, không phải bản sao. Không chuyển file nào vào `_DUPLICATES/` |
| `PRODUCTION PLAN/` | **Trống.** Chỉ có cây thư mục: `CHALLENGER/27SS`, `DHG(DAEHAN GROBAL)/27SS`, `DKM(다경물산)/27SS`, `JBEE/27SS`, `KOFA/27SS/NEPA`. Có thể file trên Google Drive chưa được tải về, cần kiểm tra lại |
| Sắp xếp | 12 file chuyển vào `ORDER/<KHÁCH>/<MÙA>/`. Nhật ký và script hoàn tác: `raw-docs/_REORG/2026-10-20_moves.tsv`, `undo_2026-10-20.sh` |
| Kho dữ liệu | Chỉ ORDER RECAP của CHALLENGER đi vào parser hiện tại. ORDER RECAP của khách khác được ghi nhận với trạng thái SKIPPED (`order_recap_other`). Build lại: 19/19 check pass, golden numbers không đổi |

| File | Khách → brand | Mùa | Người lập | Style | Tổng SL |
|---|---|---|---|---|---|
| `261006`, `261020 MJ) 26FW CHALLENGER ORDER RECAP.xlsb` | CHALLENGER | 26FW | MJ | 113 (110 còn hiệu lực) | 62.131 |
| `261005`, `261020 MJ) 27SS CHALLENGER ORDER RECAP.xlsb` | CHALLENGER | 27SS | MJ | 143 (137) | 87.940 |
| `261006. DUNG) DHG 8S 26FW ORDER RECAP.xlsx` | DHG → 8 SECONDS | 26FW | DUNG, HANG | 59 | 119.392 |
| `261020. DHG) 27SS_8SECONDS_ORDER RECAP.xlsx` | DHG → 8 SECONDS | 27SS | LEE | 25 | 36.800 |
| `261003.DUNG) BPK 27SS ORDER RECAP.xlsx` | DHG → BEANPOLE KIDS | 27SS | DUNG | 10 | 9.250 |
| `260619 MJ) 25FW XEXYMIX RE-ORDER RECAP.xlsx` | DHG → XEXYMIX (re-order) | 26FW (tên file ghi 25FW) | MJ | 2 | 4.185 |
| `261006`, `261019 MJ) 27SS JBEE ORDER RECAP.xlsx` | JBEE → NEPA, CROCODILE | 27SS | MJ | 9 | 67.100 |
| `261015 MJ) 27SS KOFA-BLACKYAK ORDER RECAP.xlsx` | KOFA → BLACKYAK, NEPA | 27SS | MJ | 2 (DETAIL) | 4.000 |
| `261019 HANG) 27SS MIZUNO (DKMS) ORDER RECAP.xlsx` | DKM (다경물산) → MIZUNO | 27SS | HANG | 26 | 43.909 |

Số style và tổng SL của khách khác lấy theo ô tổng của chính file (ô F2 hoặc G2, sheet DETAIL); riêng CHALLENGER tính bằng parser của DW.

## 1. KLMAS làm cho nhiều khách hơn ta nghĩ, và CHALLENGER không phải khách lớn nhất

- **[Q]** Có 5 khách đặt hàng: CHALLENGER (đặt trực tiếp), DHG / Daehan Global, JBEE, KOFA, DKM (다경물산, trong file Mizuno ghi `DaKyungMulsan`). Các khách này đặt hàng cho 8 brand.
- **[Q]** Một brand có thể đến qua nhiều khách: NEPA có trong file của JBEE và của KOFA (sheet DETAIL ô P5: `BLACYAK+NEPA - KOFA`).
- **[Q]** 8 SECONDS mùa 26FW có **119.392 sản phẩm / 59 style**, gần gấp đôi CHALLENGER 26FW (62.131 / 110). Buyer cuối của DHG ghi là SAMSUNG (sheet RECAP cột C).
- **[S]** Câu Q14 ("Dữ liệu của Daehan Global / 8 SECONDS có nằm trong giai đoạn 1 không?") quan trọng hơn ta đánh giá. Nếu dashboard chỉ có CHALLENGER thì chỉ phủ khoảng 1/3 sản lượng KLMAS đang theo dõi.
- **[R]** Mô hình dữ liệu cần thêm cấp **khách** (customer, đơn vị đặt hàng với KLMAS) đứng trên **brand**. Hiện `brand` đang làm luôn vai trò khách.

## 2. Cùng một họ template, nhưng vị trí cột khác nhau

- **[Q]** Mọi file đều theo khung ORDER RECAP: dòng 1–2 là chú thích màu và ngày UPDATE, header ở dòng 3–4, mỗi style là một khối nhiều dòng bắt đầu bằng NO ở cột B.
- **[Q]** Vị trí cột thì khác nhau:

  | | SL theo màu | Tổng SL | Ngày ETD | Nhà máy |
  |---|---|---|---|---|
  | CHALLENGER | J | K | L | cột E, dòng cuối khối |
  | DHG | I | K (GROSS TTL) | L | cột E dòng cuối khối, và sheet DETAIL |
  | XEXYMIX | I–M (theo nước KOREA, TAIWAN, INDONESIA, OTHER, JAPAN) | O | P | sheet DETAIL |
  | JBEE, MIZUNO | J | K | L | cột E, header `FACT` |
  | KOFA | J–K (KOREA, GERMANY CHINA) | M | N | cột E |

- **[Q]** Một số file có thêm sheet riêng:
  - **Production status ngay trong file:** DHG 8S 26FW có sheet `PRODUCTION STATUS`; MIZUNO có sheet `27SS PROD&SHIPMENT`. Các khách này không có file Production Status riêng như CHALLENGER.
  - **Bảng mã của Samsung:** 8S 27SS có sheet ẩn `COLOR CODE`, giải nghĩa mã màu và cấu trúc mã hàng (loại hàng, brand nam/nữ, năm, tháng).
  - **Sheet tiếng Hàn:** MIZUNO có 2 sheet theo dõi tiếng Hàn, `27SS 메인 진행 꼬마 (베트남)` và `원부자재 선적 일정 260924` (lịch vận chuyển nguyên phụ liệu).
- **[Q]** Có ô ghi số lượng bằng chữ, ví dụ `1500P`, `100P` (KOFA cột J–K). Có style được ghép nhiều PO, ví dụ `1BYHDMW901M (KOR PO) / 7BYETMW003M (GER PO)`.
- **[Q]** MIZUNO ghi luôn mã tương đương trong ô mã style, ví dụ `32YA7B00 (=32YA7B01) (=32MK7B00)`. Đây là nguồn alias có sẵn trong file.
- **[R]** Không nên viết thêm parser cố định cột cho từng khách. Nên làm **một parser ORDER RECAP đọc theo nhãn header** (giống cách đã đặc tả cho báo cáo sản xuất ngày, spec §3.1). Đề xuất đưa vào backlog D-14.

## 3. Quy tắc ngày giao khác nhau theo khách

| Khách / brand | Nhãn cột ETD trong file | Ghi chú |
|---|---|---|
| CHALLENGER | `RDD (-12DAY)` ở trang đầu, `RDD (-14DAY)` từ trang 4 | Đã hỏi ở Q16 |
| DHG 8 SECONDS | `RDD (-20DAY)`; DETAIL ghi `ETD VN (RDD-20 DAYS)` | |
| DHG BEANPOLE KIDS | `RDD (-14DAY)`, có thêm cột `실제납기` (ngày giao thực tế) | |
| DHG XEXYMIX | `RDD (-10DAY)` | |
| JBEE, KOFA | `RDD-14 DAYS` | |
| MIZUNO | `ETA KOREA (etd +10)` | Tính xuôi từ ETD, không tính ngược từ RDD |

- **[Q]** Mọi file đều có cột `BUYER DEL (RDD-10)`, kể cả CHALLENGER.
- **[S]** Không có một quy tắc RDD chung. Cấu hình `rdd_offset_days = 12` hiện đang dùng chung cho mọi khách là sai khi mở rộng sang khách khác.
- **[R]** Chuyển quy tắc này thành cấu hình theo khách (và brand nếu cần). Bổ sung bằng chứng này vào Q16 khi hoàn thiện bộ câu hỏi.

## 4. Lỗi gõ năm và mùa là lỗi lặp lại, không phải trường hợp lẻ

- **[Q]** CHALLENGER 27SS bản `261005`: **97 style** có ETD và RDD ghi năm 2026. Bản `261015` đã sửa thành 2027.
  - 5 style trong Q36 là phần còn sót lại, đều đã huỷ.
  - **[S]** KLMAS đã tự sửa đúng hướng, nên Q36 gần như đã có câu trả lời là "2027".
- **[Q]** Các file 27SS khác cũng có ETD năm 2026, có thể cùng lỗi:
  - JBEE 27SS: ETD sớm nhất 17/01/2026.
  - KOFA 27SS: ETD 30/01 đến 05/02/2026.
- **[Q]** File XEXYMIX tên ghi `25FW`, nhưng tiêu đề trong file ghi `26FW RE-ORDER RECAP` và các ngày đều thuộc năm 2026. Sheet ẩn DETAIL của file này còn là dữ liệu cũ `24FW 8SECONDS` (template bị copy từ file khác).
- **[R]** Lấy mùa từ **tiêu đề trong file (ô B1)** trước tên file; củng cố nguyên tắc "metadata lấy từ nội dung" của spec §2. Áp kiểm tra `ETD_OUT_OF_SEASON` cho mọi khách.

## 5. Nhà máy dùng chung giữa các khách

| Nhà máy | Khách đang dùng |
|---|---|
| DONG MY | CHALLENGER, MIZUNO (18 style) |
| TRUONG PHUC | CHALLENGER, 8 SECONDS 26FW |
| FG VINA | CHALLENGER, 8 SECONDS 26FW |
| SON HA | CHALLENGER 27SS, BEANPOLE KIDS |
| HAGACO | 8 SECONDS, BEANPOLE KIDS |
| **B85** | 8 SECONDS (34/59 style 26FW, 13 style 27SS), BEANPOLE KIDS, JBEE, XEXYMIX |
| Nhà máy mới chỉ thấy ở đây | WISER MAX, HA THANH (`HA THANH PLAN`) cho JBEE; GIA NGUYEN cho KOFA; TRI DUC, MINH TUAN cho MIZUNO; DANG SON (`ARTWORK FACTORY`, xưởng in) |

- **[S]** `B85` xuất hiện nhiều nhất ở khách DHG nhưng không giống tên nhà máy. Có thể là mã nội bộ của một nhà máy, hoặc mã chuyền hay đội may. Cần KLMAS xác nhận.
- **[S]** Sheet MIZUNO dùng màu ô để đánh dấu nhà máy (ô W1:Y1 là chú thích màu cho DONG MY, MINH TUAN, TRI DUC). Màu ô ở file này mang nghĩa khác với CHALLENGER (ở CHALLENGER màu là trạng thái).
- **[R]** Danh mục nhà máy (Q08) phải chung cho mọi khách. Scorecard nhà máy chỉ có ý nghĩa khi gộp tất cả khách mà nhà máy đó làm.

## 6. Ba phiên bản CHALLENGER: thay đổi giữa các lần cập nhật

So sánh bằng parser của DW, theo các trường: trạng thái màu, nhà máy, ETD, RDD, SL theo màu.

**26FW**
- **`261006 → 261015`:**
  - 9 style chuyển sang `KOREA SHIP OUT`.
  - CHF4MJK6405 đổi nhà máy TRUONG PHUC → TIEN THANH.
  - 2 style tô màu `FF002060` (xanh đậm) không có trong bảng chú thích ở bản `261006`, đến bản `261015` thì thành `KOREA SHIP OUT`.
- **`261015 → 261020`:** không đổi ở các trường trên; chỉ đổi ngày UPDATE (19/10).

**27SS**
- **`261005 → 261015`:**
  - 27 style được gán nhà máy hoặc đổi nhà máy, vd. TAN BINH MINH → JM (3 style), MTT → DONG MY (3 style), TRUONG PHUC PLAN → SON HA.
  - Năm ETD/RDD của 97 style được sửa từ 2026 thành 2027.
  - CHG2WSK6979 được thay bằng **CHF2WSK6979**: chữ mùa đổi từ G sang F trong một file 27SS.
  - Thêm style CHG2WSK7970.
  - CHFG2WIT7957 bị huỷ (600 → 0).
- **`261015 → 261020`:** chỉ CHG1MPT7131 lùi ETD từ 10/01/2027 sang 05/02/2027.

**JBEE `261006 → 261019`:** 8 style được gán nhà máy (WISER MAX 4, HA THANH PLAN 4). Tổng SL không đổi.

- **[S]** Mỗi lần KLMAS gửi bản mới, thứ họ cần biết là "cái gì vừa đổi". Hiện họ phải tự dò bằng mắt trên file Excel vài MB.
- **[R]** Thêm một báo cáo **"Thay đổi so với bản trước"** (style mới, huỷ, đổi nhà máy, đổi ETD, đổi SL, đổi trạng thái), theo khách và mùa. DW đã giữ mọi phiên bản trong lớp raw nên chi phí làm thấp (khoảng 4 giờ). Đây là tính năng dễ cho KLMAS thấy giá trị ngay ở buổi demo. Đề xuất D-15.

## 7. Đề xuất cho MVP

| # | Đề xuất | Ảnh hưởng | Gợi ý |
|---|---|---|---|
| 1 | Thêm cấp **khách** (customer) trên brand: CHALLENGER, DHG, JBEE, KOFA, DKM | Dashboard lọc theo khách; phân quyền theo khách sau này | Phase 1: cột `customer` + bảng ánh xạ trong config |
| 2 | Parser ORDER RECAP đọc theo nhãn header cho mọi khách | Phủ 5 khách thay vì 1 | Backlog D-14; chờ PO quyết phạm vi (Q14) |
| 3 | Quy tắc RDD/ETD theo khách trong config | Dự báo trễ đúng cho từng khách | Làm cùng #2 |
| 4 | Báo cáo "thay đổi so với bản trước" | Giá trị thấy ngay ở buổi demo | Backlog D-15; làm được ngay với CHALLENGER |
| 5 | Mùa lấy từ tiêu đề trong file; kiểm tra năm ETD theo mùa cho mọi khách | Tránh lỗi XEXYMIX (25FW/26FW) và lỗi năm 2026/2027 | Thuộc M1-01 |
| 6 | Danh mục nhà máy chung cho mọi khách | Scorecard nhà máy đúng | Thuộc Q08 |

## 8. Câu hỏi bổ sung (đưa vào bộ câu hỏi khi hoàn thiện)

1. **B85** trong cột nhà máy của các file DHG, JBEE là nhà máy nào? Là mã nội bộ hay tên một xưởng?
2. **Vai trò của DHG, JBEE, KOFA, DKM:** đây là khách đặt hàng với KLMAS (vendor của brand Hàn), còn 8 SECONDS, NEPA, MIZUNO… là brand, đúng không? Vì sao NEPA có ở cả JBEE và KOFA?
3. **RDD theo khách:** khoảng cách ETD → RDD ghi trong file (−20, −14, −10, ETA = ETD + 10) có đúng là quy tắc riêng của từng khách không? Cột `BUYER DEL (RDD-10)` là mốc gì? (Bổ sung vào Q16.)
4. **Năm ETD của JBEE và KOFA 27SS** (01–02/2026): đáng lẽ là 2027, đúng không? (Gộp với Q36.)
5. **CHG2WSK6979 → CHF2WSK6979:** là đổi mã thật hay gõ nhầm?
6. **Thư mục `PRODUCTION PLAN` trên Drive** đã có file kế hoạch sản xuất chưa, hay mới tạo thư mục? (Liên quan yêu cầu D1: kế hoạch sản xuất chưa nhận.)
7. **Phạm vi giai đoạn 1:** ngoài CHALLENGER, KLMAS muốn theo dõi khách nào trước? (Mở rộng Q14 và Q37.)
