# Rà soát `raw-docs/new-docs` (tài liệu mới + email export) — 23/10/2026

Nguồn: thư mục `new-docs` KLMAS chia sẻ ngày 22–23/10 (cây thư mục theo khách → style → từng email, giống cây Drive). Manifest đầy đủ từng file (loại, khách, style, ngày, md5, trùng): `raw-docs/_REORG/2026-10-23_new_docs_manifest.tsv` (local, không commit).
Ký hiệu: **[Q]** quan sát, **[S]** suy luận, **[R]** đề xuất. Mã câu hỏi theo `open_questions.md` bản 23/10.

## 1. Tổng quan

435 file, 1,88 GB, 5 khách (CHALLENGER, DHG, JBEE, KOFA, MIZUNO).

| Nhóm | Số file | Dung lượng | Xử lý trong DW |
|---|---:|---:|---|
| Email Gmail lưu dạng `.mhtml` (mỗi file một luồng) | 184 | 183 MB | **Parser mới** (chưa đọc được: DW chỉ nhận `.eml/.pdf/.msg/.mbox/.pst`) |
| File rập CAD (`.dxf .PDS .sty .rul .mdl .pax`) | 99 | 57 MB | Chỉ metadata |
| Tài liệu kỹ thuật Excel/PDF (W.S, CMT, FPP/INLINE comment, mini marker) | 91 | **1.365 MB** (10 file > 20 MB, lớn nhất 217 MB) | Chỉ metadata (tên, ngày, style, nhà máy, giai đoạn) |
| Định mức / cân đối vật tư (`FACTORY CONSUMPTION & BALANCE`, `최종요척`) | 15 | 12 MB | Metadata; đọc số sau |
| Assort, xác nhận số lượng / vật liệu (NEPA `수량확정`, `소재확정`), thiếu hàng, hàng B, huỷ bán thành phẩm, packing | 12 | 174 MB | Metadata; Q44 |
| ORDER RECAP | 9 (3 trùng) | 44 MB | Parser có sẵn (bản mới của family cũ) |
| Kế hoạch sản xuất | 6 | 21 MB | Parser `production_plan` có sẵn (kiểm lại mẫu cột) |
| Shipment Status, Production & Shipping Status, **Shipping Schedule** | 6 | 5 MB | Có sẵn, trừ SHIPPING SCHEDULE (**mới**) |
| "DHG 생산계획표 · 오더 현황표" (PDF do Daehan Global in) | 2 | 1 MB | **Mới**, dùng đối chiếu |
| Khác (zip, ảnh, `noname`, `.url`, `.DS_Store`) | 10 | 21 MB | Bỏ qua |

**Trùng lặp**
- 3 file trùng byte với file đã có (ORDER RECAP BPK 261021, KOFA 261015, MIZUNO 27SS 261019) → đã chuyển vào `_DUPLICATES/new-docs/…`; nhật ký `_REORG/2026-10-23_moves.tsv`, hoàn tác `_REORG/undo_2026-10-23.sh`.
- 44 nhóm trùng **bên trong** `new-docs` (48 MB): cùng một file đính kèm nằm ở 2 thư mục email (vd. rập `BI7138U01-110-140(26-10-20).dxf` ở cả "FPP CFMD" và "FPP SAMPLE COMMENT"). **Giữ nguyên** vì mỗi thư mục là một gói email; DW đã gộp theo sha256.

## 2. Email (184 luồng, 453 thư)

- [Q] Lưu từ Gmail của KLMAS (Google Workspace, giao diện tiếng Hàn), một hộp thư (tài khoản hiển thị ở đầu file). Mỗi file: header Gmail in (người gửi `Tên <địa chỉ>`, ngày `2026년 7월 20일 오전 7:27`, `받는사람:`, `참조:`), nội dung, **chỉ tên** file đính kèm. Phần HTML không khai báo charset trong MIME header → phải đọc theo `<meta charset>`; tên file trên macOS là NFD → chuẩn hoá NFC.
- [Q] Thời gian 01/09/2025 → 22/10/2026; nhiều nhất 06/2026 (90 thư) và 10/2026 (94). Theo khách: DHG 91 luồng, CHALLENGER 64, MIZUNO 25, JBEE 4, **KOFA 0**.
- [Q] Người gửi theo tên miền: `klmasvn.com` 188 thư, `daehan.co.kr` 161, `hafashion.com.vn` (HAGACO) 51, `daum.net` (CHALLENGER) 25, `naver.com` 12, `abklogx.com` (forwarder ABK) 9, `jbeesc.com` 3. Trong To/CC còn có `jaketnd.com` (forwarder JAKE), `dongmygarment.com.vn`, nhiều Gmail cá nhân của nhà máy (TRUONG PHUC, B85, Thành Vân…).
- [Q] Phân loại theo tiêu đề (ước tính bằng từ khoá, cần KLMAS xác nhận ở Q17):

  | Giai đoạn | Luồng | Ví dụ tiêu đề |
  |---|---:|---|
  | Mẫu (FPP request / CMT / comment) | 56 | `0430) CHF3MJK6301 QC CMT+패턴 파일` |
  | Xuất hàng + vật tư về nhà máy | 43 | `260811ETD SEA SHIPMENT MTT TO CHALLENGER #LCL ABKHPH2608037`; `9/27->9/29ETD (delay) FROM ICH TO B85 SHIPMENT - JAKEHPH2609051` |
  | Kiểm hàng, inline | 21 | `[KLMAS] CHALLENGER INSPECTION REPORT 260907` |
  | Gói sản xuất đại trà (FPP CFMD MAIN W.S + grading + mini marker) | 14 | `260629 (CHALLENGER- TRUONG PHUC) CHF3WJK6701- FPP CFMD MAIN W.S…` |
  | Báo cáo sản xuất ngày | 14 | `261021 - (CHALLENGER// TIEN THANH) - 26FW - DAILY PRODUCTION REPORT`; `TIẾN ĐỘ SẢN XUẤT HD2 - THÁNG 10/2026` |
  | Định mức / cân đối, duyệt DM | 14 | `260810 (CHALLENGER- TP) … FACTORY'S CONSUMPTION & BALANCE SHEET`; `Re: DUYỆT DM ma hang LBV-26002` |
  | Kỹ thuật / rập | 9 | `0729) NATEXCO_ CHF4MJK6406 작업 지시서 +패턴 파일` |
  | Đơn / sketch / assort / đổi số lượng | 6 | `LEV-26111 - SIZE ASSORT`; `260720 … THAY ĐỔI SỐ LƯỢNG ĐƠN HÀNG {1ST CHANGE ASSORT Q'TY}` |
  | Vật tư: kiểm vải, test vải | 4 | `BIÊN BẢN KIỂM VẢI MÃ HÀNG LBV-26002 (KH KLMAS)`; `260707 … 검단 리포트` |
  | Chất lượng (buyer phàn nàn) | 2 | `8SECONDS - QUALITY ATTENTION` |
  | Khác | 1 | — |

### Insight chính
1. **[Q] Vòng đời style hiện rõ qua email** (CHF3WJK6701): tài liệu + rập (14/05) → FPP CMT (24/06) → FPP CFMD = gói đại trà (29/06) → kiểm vải `검단 리포트` (07/07) → đổi assort do vải lỗi (20/07) → định mức (10/08) → INLINE CMT (12/08) → xuất `260819ETD … #LCL ABKHPH2608058`. **[R]** Dùng làm khung T&A: mỗi mốc = (style, loại mốc, ngày, người gửi, nguồn email). Q17.
2. **[Q] Tiêu đề email theo quy ước khá chặt**: `<YYMMDD>ETD SEA|AIR SHIPMENT <nhà máy> TO <khách> #LCL|FCL <booking>`; vật tư vào: `<M/D>-><M/D>ETD (delay) FROM ICH|SH TO <nhà máy> SHIPMENT - <booking>`. **[S]** Trích được ETD, ETD đổi/trễ, phương thức, nhà máy, booking bằng regex, không cần AI. Q43.
3. **[Q] Một nhà máy = một booking LCL** cho CHALLENGER (ABKHPH2608037 MTT, ABKHPH2608058 TP, ABKHPH2609012 DONG MY); đầu mùa dùng forwarder khác (`SMKCHAP…`). Trả lời gần như hết Q22 (lô xuất). Booking là khoá nối email ↔ Shipment Status ↔ chứng từ.
4. **[Q] Đổi số lượng xảy ra qua email trước khi vào ORDER RECAP**: CHALLENGER báo đổi assort do vải lỗi (20/07 07:27, tiếng Hàn), KLMAS chuyển cho nhà máy 2 giờ sau (tiếng Việt, kèm hướng dẫn giữ 2 cây vải lỗi, cắt giảm đều các cỡ). **[R]** Đây đúng là use-case `change_proposal` (PENDING_REVIEW) — đối chiếu với ORDER RECAP bản sau ngày 20/07.
5. **[Q] Báo cáo ngày đi 2 chiều**: nhà máy → KLMAS (HAGACO gửi `HD2- DAILY PRODUCTION T10 -26.xlsx` gần như mỗi ngày, luồng 19 thư) và KLMAS → buyer (Elena, văn phòng HN). Có email báo cáo của **NATEXCO 14/10, TIEN THANH 21/10** mà ASTRA chưa có file → D2 là "KLMAS chưa chuyển", không phải "không có". Q03.
6. **[Q] Factory master mới**: B85 là nhà máy may (cho DHG và NEPA); HAGACO = May Hải Dương 2 (HD2, xưởng Nam Sách); CHF3MJK6301 đi qua NATEXCO → HA HIEU → MTT; Thành Vân xuất hiện cạnh TRUONG PHUC. PRODUCTION STATUS 21/10 có 8 nhà máy CHALLENGER. Q08.
7. **[Q] Daehan Global có bảng riêng** "생산계획표 · 오더 현황표" (in 21/10, người lập phía DHG) với `납기 여유` = RDD − ETA Incheon và trạng thái → **[S]** buyer đã có công cụ tương tự dashboard; cần biết nguồn số để tránh nhập 2 lần. Q15.5.
8. **[Q] Chất lượng**: Daehan Global phàn nàn lỗi phát hiện ở kho 8 SECONDS (LEV-26005, LEV-25128/25116) và yêu cầu "strengthen the KLMAS Inspection" → **[R]** dashboard chất lượng nên nối được lỗi phía buyer với lần kiểm của KLMAS (phase 2).
9. **[Q] File đính kèm lớn là link tải 30 ngày** (`대용량파일 … 30일 보관`) → không lấy lại được từ email cũ; nguồn file phải là Drive. Q19, D9.

## 3. Excel / PDF mới

| File | Quan sát | Hành động |
|---|---|---|
| `261015) 26FW CHALLENGER SHIPPING SCHEDULE.xlsx` | 2 sheet `SHIPPING SCHEDULE` (26 dòng, đang xuất) và `SHIPPED STYLES` (138 dòng). Cột: STYLE NO, INPUT/SEWING FINISH PLAN, ORDER Q'TY, ETD VN, RDD, SHIPPED Q'TY, SHIP(PLAN) Q'TY, BAL, pcs/box, box q'ty, FACTORY, **FIXED EX-FACT / FIXED ETD / FIXED ETA**, SHIP MODE, RMKS (`DOWN ISSUE`, `SHADING…`) | Parser mới; ETD VN − RDD = 12 ngày (bằng chứng Q21) |
| `261021 HUONG) 26FW CLGR PRODUCTION AND SHIPPING STATUS(~10.20).xlsx` | Bản mới của [PRODUCTION STATUS]: 110 style, **62.357** pcs (RECAP 15/10: 62.131), 8 nhà máy | Parser có sẵn; golden theo bản cụ thể |
| `261022 MJ) 26FW/27SS CHALLENGER ORDER RECAP.xlsb` | Bản mới nhất của 2 family → sẽ thành bản hiện hành | Golden hiện tại (62.131 / 87.940) đang theo bản 15/10 → phải ghim check theo file, thêm golden bản 22/10 |
| `261022 MJ) (CLGR - ALL) 26FW PRODUCTION PLAN.xlsx`, `261022 MJ) CHALLENGER 27SS PRODUCTION PLAN.xlsx` | Kế hoạch CHALLENGER lần đầu có (trước đây Q15 hỏi) | Kiểm `production_plan` đọc được |
| `261022R 27SS NEPA PRODUCTION PLAN.xlsx` (WISER MAX), `261020_NEPA - GIA NGUYEN…` | Cùng mẫu cột: A) ex-fact, B) ETD Hải Phòng, C) ETA Incheon, D) `DUE ETD / RDD-14`, E) `ETA / RDD-2` (WISER MAX) vs `RDD-3` (GIA NGUYEN), F) buyer delivery. GIA NGUYEN: due ETD 08/02/**2026** trước ngày cắt 12/2026 | Q15.4, Q41 (lỗi năm) |
| `260620 HUONG - DONGMY + HAGACO - 26FW - MIZUNO PRODUCTION PLAN (RE_CHECK).xlsx` | 2 sheet theo nhà máy, có ghi chú `재확인요청`, `6/16 요청` | production_plan |
| MIZUNO `260804/260824 … 26FW ALL STYLES SHIPMENT STATUS`, `261013) 27SS …`, `260821 HANG) 26FW MIZUNO (DKMS) ORDER RECAP` | Mùa 26FW MIZUNO lần đầu có | Parser shipment chung; history |
| `8 SECONDS_오더현황_2026-10-21.pdf`, `오더리캡 현황 · DHG 빈폴키즈.pdf` | PDF có text: FILE NO · STYLE, nhà máy (B85/HGC/SH/XT), SL, CUT/INPUT/FINISH, ETD, ETA, RDD, 납기 여유, 상태 | Parser PDF đơn giản để đối chiếu với RECAP/plan |
| `261019 27SS NEPA PANTS ASSORT.xlsx` | Ma trận màu × size cho 7ND1709 (10.000 pcs) | Đọc sau (assort) |
| NEPA `… 08.19 수량확정.pdf`, `… 소재확정.원단발주.pdf` | Xác nhận số lượng / vật liệu + đặt vải của buyer | Mốc T&A |

## 4. Đề xuất cho DW (đưa vào prompt Claude Code 23/10)
1. Parser `.mhtml` (Gmail print) dùng lại `email_pdf.split_messages`; charset từ meta; NFC; lấy tên file đính kèm + kích thước + link-hết-hạn.
2. Phân loại file kỹ thuật / CAD **chỉ metadata** trước khi mở Excel (theo đuôi file, từ khoá tên, và giới hạn kích thước) — tránh mở file 217 MB.
3. `core.style_milestone` từ tiêu đề email + tên file/thư mục: FPP_REQUEST, FPP_CMT, FPP_CFMD, DM_APPROVAL, FABRIC_INSPECTION, INLINE_CMT, FINAL_INSPECTION, DAILY_REPORT, EX_FACTORY, ETD, ETA, ASSORT_CHANGE.
4. `core.shipment_event` từ tiêu đề: hướng (outbound / inbound material), ETD cũ → mới (delay), ETA, mode, nhà máy, khách, booking, forwarder.
5. Parser SHIPPING SCHEDULE + PDF "오더 현황표"; đối chiếu ETD/RDD với RECAP và plan.
6. `KOPS_MAIL_ALLOW` = tên miền KLMAS, buyer, nhà máy, forwarder quan sát được (mục 2) + danh sách địa chỉ Gmail/naver cụ thể (không mở cả `gmail.com`).
7. Golden ghim theo file/bản (không theo "bản hiện hành") để thêm bản mới không làm đỏ check cũ; thêm golden cho bản 22/10 từ ô tổng trong file.
