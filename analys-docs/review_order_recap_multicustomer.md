# Rà soát nguồn mới: ORDER RECAP nhiều khách, kế hoạch sản xuất và các phiên bản (20–21/10/2026)

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
| CHALLENGER | `RDD (-12DAY)` ở trang đầu, `RDD (-14DAY)` từ trang 4 | Đã hỏi ở Q21 |
| DHG 8 SECONDS | `RDD (-20DAY)`; DETAIL ghi `ETD VN (RDD-20 DAYS)` | |
| DHG BEANPOLE KIDS | `RDD (-14DAY)`, có thêm cột `실제납기` (ngày giao thực tế) | Sheet DETAIL lại ghi `ETD VN (RDD-20 DAYS)`: mâu thuẫn ngay trong một file |
| DHG XEXYMIX | `RDD (-10DAY)` | |
| JBEE, KOFA | `RDD-14 DAYS` | |
| MIZUNO | `ETA KOREA (etd +10)` | Tính xuôi từ ETD, không tính ngược từ RDD |

- **[Q]** Mọi file đều có cột `BUYER DEL (RDD-10)`, kể cả CHALLENGER.
- **[S]** Không có một quy tắc RDD chung. Cấu hình `rdd_offset_days = 12` hiện đang dùng chung cho mọi khách là sai khi mở rộng sang khách khác.
- **[R]** Chuyển quy tắc này thành cấu hình theo khách (và brand nếu cần). Bổ sung bằng chứng này vào Q21 khi hoàn thiện bộ câu hỏi.

## 4. Lỗi gõ năm và mùa là lỗi lặp lại, không phải trường hợp lẻ

- **[Q]** CHALLENGER 27SS bản `261005`: **97 style** có ETD và RDD ghi năm 2026. Bản `261015` đã sửa thành 2027.
  - 5 style trong Q41 là phần còn sót lại, đều đã huỷ.
  - **[S]** KLMAS đã tự sửa đúng hướng, nên Q41 gần như đã có câu trả lời là "2027".
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
  - Dòng 638 (mã O25): CHG2WSK6979 đổi thành **CHG2WSK7970** (nhà máy TAN BINH MINH). Đồng thời có thêm dòng 685 (mã O35) **CHF2WSK6979**, chữ mùa là F trong một file 27SS. *(Sửa 21/10: bản 20/10 của tài liệu này ghi nhầm là CHG2WSK6979 đổi thành CHF2WSK6979.)*
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

## 8. Câu hỏi bổ sung

*Ngày 21/10 đã đưa vào `open_questions.md`: ý 1 → Q08; ý 2 và 7 → Q14; ý 3 → Q21; ý 4 → Q41; ý 5 → Q05; ý 6 → Q15.*


1. **B85** trong cột nhà máy của các file DHG, JBEE là nhà máy nào? Là mã nội bộ hay tên một xưởng?
2. **Vai trò của DHG, JBEE, KOFA, DKM:** đây là khách đặt hàng với KLMAS (vendor của brand Hàn), còn 8 SECONDS, NEPA, MIZUNO… là brand, đúng không? Vì sao NEPA có ở cả JBEE và KOFA?
3. **RDD theo khách:** khoảng cách ETD → RDD ghi trong file (−20, −14, −10, ETA = ETD + 10) có đúng là quy tắc riêng của từng khách không? Cột `BUYER DEL (RDD-10)` là mốc gì? (Bổ sung vào Q21.)
4. **Năm ETD của JBEE và KOFA 27SS** (01–02/2026): đáng lẽ là 2027, đúng không? (Gộp với Q41.)
5. **CHG2WSK6979 → CHG2WSK7970, và CHF2WSK6979 mới:** là gõ nhầm hay đổi mã thật?
6. **Thư mục `PRODUCTION PLAN` trên Drive** đã có file kế hoạch sản xuất chưa, hay mới tạo thư mục? (Liên quan yêu cầu D1: kế hoạch sản xuất chưa nhận.)
7. **Phạm vi giai đoạn 1:** ngoài CHALLENGER, KLMAS muốn theo dõi khách nào trước? (Mở rộng Q14 và Q46.)

---

# Cập nhật 21/10/2026: lần quét thứ hai

## 9. Kết quả quét

| Hạng mục | Kết quả |
|---|---|
| `ORDER RECAP/` | Có lại 13 file. **12 file trùng byte (MD5)** với file đã xếp vào `ORDER/` hôm 20/10, nên được chuyển vào `_DUPLICATES/ORDER RECAP/…`. **1 file mới:** `261021 DHG) BPK 27SS ORDER RECAP.xlsx`, chuyển vào `ORDER/DHG(DAEHAN GROBAL)/27SS/` |
| `PRODUCTION PLAN/` | **2 file mới** (lần đầu nhận kế hoạch sản xuất): `261016 MJ_DHG BPK -ALL 27SS PRODUCTION PLAN.xlsx` và `261020_NEPA - GIA NGUYEN _27SS_PRODUCTION_PLAN.xlsx`. Mỗi file có một bản trùng nằm trong `PRODUCTION/<KHÁCH>/<BRAND>/27SS/`; bản đó chuyển vào `_DUPLICATES/`. Bản chính đặt ở `PRODUCTION PLAN/<KHÁCH>/<MÙA>/` |
| `PRODUCTION/` | Có thêm thư mục rỗng theo cấu trúc Drive của KLMAS (vd. `FG`, `TIEN THANH`, `DKM (다경물산)/27SS/DONG MY`, `JBEE/NEPA/27SS/B85`). Giữ nguyên |
| Nhật ký | 17 lần chuyển: `raw-docs/_REORG/2026-10-21_moves.tsv`, hoàn tác bằng `undo_2026-10-21.sh` |
| Kho dữ liệu | Thêm loại nguồn `production_plan` (trạng thái SKIPPED, chờ parser). Tên file có `_` (vd. `_27SS_PRODUCTION_PLAN`) giờ được nhận đúng mùa và loại. Build lại: 19/19 check pass |

**[S] Vì sao file trùng quay lại:** thư mục `raw-docs/` không phải thư mục đồng bộ (không phải symlink, không có dấu vết Drive). Có vẻ mỗi lần tải lại, cả thư mục `ORDER RECAP` từ Drive được copy vào. Cây thư mục của ta khác cây Drive, nên mỗi lần copy lại sinh ra bản trùng.

**[R]** Chọn một trong hai cách:
1. Chỉ copy file mới (so tên file và ngày ở đầu tên) vào cây hiện tại.
2. **(Khuyến nghị)** Đổi `raw-docs/` thành bản sao y nguyên cây Drive của KLMAS (`ORDER RECAP/`, `PRODUCTION PLAN/`, `PRODUCTION/` đúng như trên Drive) và không sắp xếp lại nữa. Copy lại sẽ chỉ ghi đè đúng file cũ, không sinh bản trùng. Pipeline đã lấy metadata từ nội dung và tên file nên không phụ thuộc thư mục. Đây cũng là cấu trúc mà việc đồng bộ tự động sau này (backlog D-13) sẽ dùng.

## 10. Kế hoạch sản xuất (PRODUCTION PLAN): nguồn mới, giá trị cao cho dự báo

**Bố cục [Q]:**
- Mỗi sheet là kế hoạch của một nhà máy. File BPK có 4 sheet: `HGC` = HAGACO, `SH` = SON HA, `XT` = XUAN THANH, `B85`. File NEPA có 1 sheet `PLAN`.
- Header ở dòng 4–6, song ngữ Anh/Hàn/Việt. Từ dòng 7 mỗi dòng là một style.
- Template giống nhau giữa 2 file, dù do 2 người lập ở 2 khách khác nhau.

| Nhóm cột | Cột | Ý nghĩa |
|---|---|---|
| Nhận diện | C, D, E, G | FILE NO, STYLE, ITEM, Q'TY |
| Năng lực | B `LINE / WORKER`, K `DAILY & TARGET`, L `Number of working day` | vd. `4 / 13`, 45 cái/ngày, 27,4 ngày (= SL ÷ mục tiêu/ngày) |
| Nguyên phụ liệu | H, I, J | ngày xuất vải, ngày xuất phụ liệu, ngày phụ liệu về nhà máy |
| Kế hoạch may | M, N, O | ngày cắt, vào chuyền, may xong |
| Kế hoạch xuất | P, Q, R | ngày xuất xưởng, ETD Hải Phòng, ETA Incheon |
| Hạn của buyer | S, T, U | `DUE ETD / RDD-14 DAYS`, ETA, RDD |
| Dư địa | V `BAL` | **[Q]** = RDD − (ETA Incheon + 2). Kiểm tra: LBV-27002: 01/12 − (04/12 + 2) = −5; LBV-27001: 01/12 − (28/11 + 2) = +1 |
| Thực tế | W, X, Y | EXF, ETD, ETA thực tế: hiện còn trống |
| Mẫu | Z–AD | FPP, TOP (theo dõi duyệt mẫu) |

**Insight:**
- **[Q]** Kế hoạch BPK (16/10) đã thấy rủi ro: **LBV-27002 (HAGACO, 1.100 cái)** may xong 23/11 và xuất xưởng 26/11, trễ 9 ngày so với hạn xuất 17/11; BAL = −5. Ba style khác có BAL 1–2 ngày (LBV-27001, LBV-27005, LBV-27006), gần như không còn dư địa.
- **[Q]** Mục tiêu/ngày theo style dao động **30–147 cái**. Kho dữ liệu đang dùng mặc định **45 cái/ngày** cho style chưa có báo cáo ngày.
  - **[R]** Khi có kế hoạch, dùng cột K thay cho số mặc định.
  - **[R]** So kế hoạch (cột M–O) với thực tế (báo cáo ngày) để ra cảnh báo "chậm so với kế hoạch". Đây là tính năng đã có trong backlog (P-03) nhưng trước đây chưa có nguồn.
- **[Q]** Tiêu đề cột T khác nhau ngay trong một file: sheet `HGC` ghi `ETA / ETD +7DAYS`, các sheet khác ghi `ETA / RDD-3 DAYS`. Cột V ghi `ETA+2` ở BPK nhưng `ETA+1` ở NEPA.
- **[Q]** File NEPA lặp lại lỗi năm: dòng 8 có ngày cắt 05/01/2026 trong khi dòng 7 là 21/12/2026; các ngày xuất (cột P–U) ghi tháng 02/**2026**, đáng lẽ là 2027.
- **[Q]** Tổng SL kế hoạch BPK = 9.270, khác cả bản ORDER RECAP 03/10 (9.250) lẫn bản 21/10 (10.380). Kế hoạch có LBV-27016 = 1.020 (khớp bản 21/10) nhưng LBV-27014 = 900 (khớp bản 03/10), và chưa có 2 style mới. Các file được cập nhật lệch nhịp với nhau.
- **[Q]** B85 có sheet kế hoạch riêng (`27SS [DHG BPK-B85] PRODUCTION PLAN`), tức KLMAS coi B85 là một nhà máy. Vẫn cần tên chính thức (Q08).

## 11. Beanpole Kids: bản 03/10 → bản 21/10

| Loại | Chi tiết |
|---|---|
| Thay đổi có vẻ là thật | LBV-27005 và LBV-27006 chuyển SON HA → **XUAN THANH**. LBV-27006 và LBV-27015 ghi `CANCLE` (sheet DETAIL). Thêm **LBV-27016-1** (600) và **LBV-26017-1** (500, mã mùa 26). LBV-27014 900 → 910; LBV-27016 1.000 → 1.020. Tổng (ô F2) 9.250 → 10.380 |
| Đổi quy tắc ngày | Tiêu đề cột ETD (ô M4) từ `RDD (-14DAY)` sang `RDD (-8DAY)`; ETD các style dời theo (vd. LBV-27001 từ 10/11 sang 23/11) |
| Lỗi nhập | ETD LBV-27010 và LBV-27011 = 11/01/**2026**; LBV-27014 = 28/12/**2025**; LBV-27017 = 08/02/**2026**; RDD LBV-27015 là chữ `12//1`; ngày UP DATE (ô D2) lùi về 07/09/2026 |
| Sheet DETAIL hỏng | Ngày hiện năm 1900–1904, dòng `#N/A`, tổng `G.TTL` = `#N/A` (công thức tham chiếu lệch sau khi chèn dòng) |

- **[S]** Bản mới nhất chưa chắc là bản đúng nhất. Nếu kho dữ liệu chỉ lấy "bản mới nhất" mà không kiểm tra, dashboard sẽ hiện ETD năm 2025 cho đơn 27SS.
- **[R]**
  - Parser của khách khác (D-14) đọc sheet RECAP, không đọc DETAIL.
  - Khi bản mới có lỗi nghiêm trọng (ngày ngoài mùa, ô tổng `#N/A`), giữ giá trị của bản trước cho ô đó và ghi issue, thay vì ghi đè bằng lỗi.
  - Báo cáo "thay đổi so với bản trước" (D-15) cần tách 2 loại: thay đổi nghiệp vụ và lỗi nhập.

## 12. Đề xuất bổ sung cho MVP

| # | Đề xuất | Gợi ý |
|---|---|---|
| 7 | Parser kế hoạch sản xuất (đọc theo nhãn header; mỗi sheet một nhà máy) → `core.production_plan` (ngày cắt/vào chuyền/may xong, mục tiêu/ngày, BAL) | Backlog D-16, khoảng 6 giờ. Chờ Q15 |
| 8 | Dự báo: style chưa có báo cáo ngày dùng mục tiêu/ngày của kế hoạch thay cho 45 cái/ngày; có báo cáo ngày thì so với kế hoạch | Làm sau D-16 |
| 9 | Kiểm tra bản mới trước khi thay bản cũ: ngày ngoài mùa, ô tổng lỗi, ngày UP DATE lùi | Gộp vào D-14 và D-15 |
| 10 | Thống nhất cách đưa file từ Drive về (mục 9) | PO quyết |

Câu hỏi mới đã thêm vào `open_questions.md`: **Q15** (kế hoạch sản xuất, ưu tiên 2) và **Q42** (Beanpole Kids bản 21/10, ưu tiên 3). Bằng chứng mới cũng được bổ sung vào Q05, Q08, Q14, Q21 và Q41.
