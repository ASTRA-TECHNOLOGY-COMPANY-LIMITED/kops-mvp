# Kế hoạch nạp dữ liệu lịch sử quy mô lớn (mùa 24–25, email cũ, song ngữ Việt–Hàn)

**Bối cảnh:** KLMAS sẽ đưa toàn bộ file và email cũ (mùa 24SS…25FW, có thể cả trước đó) để phân tích lịch sử. Khối lượng dự kiến: hàng nghìn file Excel/PDF, hàng chục nghìn email. Nội dung bằng tiếng Việt, tiếng Hàn (và một phần tiếng Anh).

**Giới hạn của `dw/` hiện tại (22/10/2026):**

| Điểm | Hiện tại | Vấn đề khi lên hàng chục nghìn file |
|---|---|---|
| Build | Full rebuild, đọc lại mọi file mỗi lần (35 file ≈ 22 giây; `.xlsb` qua LibreOffice có cache) | Hàng giờ mỗi lần build; một file lỗi làm chậm cả lượt |
| Lưu trữ | Một file DuckDB, xoá và tạo lại | Không tăng dần được, không giữ kết quả bóc tách đắt (OCR, LLM) |
| Nguồn | Mọi file trong `raw-docs/` của repo | Vài chục GB không nên nằm trong thư mục repo |
| Email lịch sử | PDF từng thư | Xuất PDF từng thư cho chục nghìn thư là không khả thi với KLMAS |
| Dashboard | Một file HTML nhúng toàn bộ dữ liệu (535 KB) | Vài trăm MB, trình duyệt treo |
| Tìm kiếm | Không có | Cần tìm "email nào nói về style X / vấn đề Y" xuyên 2 ngôn ngữ |
| Template cũ | Parser viết theo file mùa 26FW/27SS | Mẫu mùa 24/25 có thể khác cột, khác sheet |

## 1. Kiến trúc đề xuất (vẫn DuckDB + Python, không thêm server)

```
nguồn (chỉ đọc)                    xử lý một lần / file                 kho (tăng dần)                     dùng
──────────────────                 ──────────────────────               ─────────────────────               ──────────────
KOPS_RAW_DOCS (ổ ngoài / Drive)    manifest: path,size,mtime,sha256     lake/  Parquet theo                 DuckDB views
  ORDER/ TRACKING/ PRODUCTION/ ─►  │ chỉ hash file mới/đổi        ─►    parser/customer/season/          ─► core / mart (SQL)
  PRODUCTION PLAN/ INSPECTION/     │ parse song song (N process)        sha256.parquet                   ─► dashboard theo mùa
inbox/ (pst, mbox, eml, pdf)       │ cache theo (sha256, parser_ver)    cache/ ocr, llm theo msg_key      (tải lười, local server)
                                   │ OCR / LLM: hàng đợi riêng          etl.run, etl.source_file          ─► tìm kiếm VI/KO
```

**Nguyên tắc:**
1. **Mỗi file chỉ xử lý một lần.** Kết quả parse lưu thành Parquet, đặt tên theo `sha256`, kèm `parser_version`. Lần build sau chỉ parse file mới, file đổi, hoặc khi parser đổi phiên bản; phần còn lại đọc thẳng từ Parquet.
2. **Bước đắt tách riêng và cache theo khoá ổn định:**
   - `.xlsb` → `.xlsx` (theo `sha256`, đã có);
   - OCR PDF scan (theo `sha256` + trang);
   - LLM (theo `msg_key` + `extractor_version`).
3. **SQL model vẫn full rebuild** nhưng đọc Parquet: chục triệu dòng vẫn chỉ mất vài chục giây trên DuckDB.
4. **Nguồn ở ngoài repo:** `KOPS_RAW_DOCS=/Volumes/KLMAS-archive` (hoặc thư mục Google Drive for desktop). Repo không chứa dữ liệu.
5. **Không gì bị ghi đè:** mọi phiên bản cũ nằm trong lake; "bản hiện hành" chỉ là một cờ tính lại mỗi lần build.

## 2. Email lịch sử: xin đúng định dạng ngay từ đầu

PDF từng thư phù hợp cho vài chục thư mẫu, **không phù hợp cho lịch sử**: mất header gốc, mất file đính kèm, OCR tốn kém, KLMAS phải xuất từng thư. Nên xin theo thứ tự ưu tiên:

| Hệ thống KLMAS dùng | Xin gì | Cách đọc |
|---|---|---|
| Outlook / Microsoft 365 | File `.pst` của hộp thư hoặc thư mục, hoặc quyền IMAP chỉ đọc | `readpst` (gói `libpst`) → `.eml`; hoặc `fetch-imap` |
| Gmail / Google Workspace | Google Takeout → `.mbox`, hoặc label + quyền đọc | Đọc `.mbox` bằng thư viện chuẩn `mailbox`; hoặc connector Gmail / `fetch-imap` |
| Naver Works, Hiworks, Daum | Chức năng sao lưu hộp thư (`.eml` nén zip) hoặc IMAP | `.eml` / `fetch-imap` |
| Không xuất được | PDF in **theo cả luồng** (một PDF cho một chuỗi thư), không phải từng thư | Parser PDF hiện có (đã tách nhiều thư trong một PDF) |
| Kakao / Zalo | File export đoạn chat `.txt`/`.csv` | Parser chat (H-07) |

**Câu hỏi gửi KLMAS** (đưa vào tài liệu câu hỏi, Ưu tiên 2):
- Email đang dùng hệ thống nào?
- Có xuất được cả hộp thư hoặc thư mục theo khách không?
- Khoảng bao nhiêu thư, từ năm nào?
- Có thư mục nào chứa thông tin nhạy cảm (lương, nhân sự) cần loại ra không?

## 3. Song ngữ Việt – Hàn

| Việc | Giải pháp | Ghi chú |
|---|---|---|
| Chuẩn hoá chữ | NFC; tiếng Việt: dấu tổ hợp → dựng sẵn, `Đ/đ`; tiếng Hàn: giữ nguyên âm tiết | Đã có `nfc`, `norm_key` |
| Nhận ngôn ngữ | Đếm ký tự Hangul / dấu tiếng Việt (đã có `lang_of`) | Mỗi thư có thể trộn 2 ngôn ngữ; lưu tỉ lệ thay vì một nhãn |
| Phân loại nhanh, không tốn tiền | Từ khoá VI/KO/EN theo loại (đã có `config.EMAIL_CATEGORIES`); bổ sung từ điển ngành may (원단, 부자재, 선적, 납기, 수량, 샘플; vải, phụ liệu, giao hàng, số lượng, mẫu) | Đủ cho dashboard tổng quan |
| Hiểu nội dung, bóc tách thay đổi | LLM (`email_llm.py`), trả **tóm tắt cả tiếng Việt và tiếng Hàn** + đề xuất có trích dẫn nguyên văn | Chỉ khi PO duyệt P2 |
| Tìm kiếm xuyên ngôn ngữ | (a) Full-text: DuckDB FTS không tách từ tiếng Hàn tốt, nên đánh chỉ mục **n-gram ký tự (bi-gram)** cho cả 2 ngôn ngữ; (b) Ngữ nghĩa: embedding đa ngôn ngữ (vd. `bge-m3` / `multilingual-e5`, chạy local) lưu vào DuckDB `vss` | (a) làm trước, (b) khi cần "tìm theo ý" |
| OCR PDF scan | `tesseract` với gói ngôn ngữ `kor` + `vie` (+`eng`), chỉ chạy cho trang không có text layer, cache theo trang | Chậm: chạy nền theo hàng đợi |
| Hiển thị | Dashboard song ngữ: nhãn tiếng Việt, cột tóm tắt có cả VI và KO | Người Hàn và người Việt cùng đọc được |

## 4. Template file mùa cũ

- **Nhận diện template bằng "dấu vân tay header":** hash các nhãn ở dòng 1–6 sau khi chuẩn hoá. File có dấu vân tay chưa biết → trạng thái `UNKNOWN_TEMPLATE`, vào báo cáo cách ly (không chặn build).
- **Parser đọc theo tên cột:** `order_recap_generic`, `production_plan` đã theo hướng này. CHALLENGER parser cố định cột cũng nên chuyển dần sang tên cột trước khi nạp mùa 24/25.
- **Mỗi mùa cũ có 1–2 golden number** lấy từ ô tổng của file (số style, tổng SL) để biết parser đọc đúng.

## 5. Phân tích lịch sử sẽ có

| Phân tích | Từ nguồn | Dùng để |
|---|---|---|
| So sánh mùa (24SS → 27SS): số style, SL, số khách, số nhà máy | ORDER RECAP mọi bản | Xu hướng kinh doanh |
| Lead time: ngày đặt → ETD → xuất thực tế; tỉ lệ đúng hạn theo nhà máy, khách, loại hàng | ORDER RECAP + Shipment Status + kế hoạch | Scorecard nhà máy nhiều mùa, dự báo tốt hơn |
| Tần suất và loại thay đổi đơn (giảm SL, đổi màu, dời ETD) theo khách, theo giai đoạn trước ETD | Lịch sử phiên bản + email | Biết khách nào hay đổi, đổi lúc nào |
| Chất lượng dữ liệu theo người lập / theo khách (lỗi năm, ô tổng hỏng) | `etl.data_issue` theo phiên bản | Đào tạo, chuẩn hoá mẫu |
| Email: khối lượng, chủ đề, thời gian phản hồi theo khách / theo mùa; chuỗi thư dài nhất | Email | Tìm điểm nghẽn quy trình, ứng viên tự động hoá |
| Tìm lại "lần trước xử lý việc này thế nào" | Email + file, tìm kiếm VI/KO | Kho tri thức (yêu cầu #14) |

## 6. Danh sách task

| ID | Task | Phụ thuộc | Giờ | Nghiệm thu |
|---|---|---|---|---|
| H-01 | **Manifest + build tăng dần:** quét `KOPS_RAW_DOCS` (path, size, mtime; chỉ hash khi đổi), bảng `etl.manifest`, `etl.run` | — | 4 | Lần 2 không đổi file: không parse lại file nào; thêm 1 file: chỉ parse file đó |
| H-02 | **Lake Parquet:** mỗi parser ghi `lake/<table>/parser=…/customer=…/season=…/<sha256>.parquet` + `parser_version`; `00_raw.sql` thành view `read_parquet(...)` | H-01 | 6 | Kết quả 33 check giữ nguyên; build lần 2 < 10 giây trên dữ liệu hiện tại |
| H-03 | **Parse song song + cách ly lỗi:** process pool, timeout từng file, file lỗi vào `etl.quarantine` | H-02 | 3 | 1 file hỏng không làm dừng build; báo cáo liệt kê file cách ly |
| H-04 | **Dấu vân tay template** + báo cáo template chưa biết | H-01 | 3 | File mẫu sửa tên cột → `UNKNOWN_TEMPLATE` kèm danh sách nhãn |
| H-05 | **CHALLENGER ORDER RECAP đọc theo tên cột** (giữ golden 26FW/27SS) | H-04 | 5 | 33 check pass; một file đã đảo vị trí cột vẫn ra đúng số |
| H-06 | **Hộp thư lớn:** đọc `.mbox` (thư viện chuẩn), `.pst` qua `readpst` nếu có; lọc theo ngày/thư mục; bỏ thư rác, thư tự động (newsletter, thông báo hệ thống) bằng quy tắc | — | 5 | Mẫu `.mbox` 1.000 thư nạp < 2 phút; thư trùng gộp đúng |
| H-07 | **Chat export** Kakao / Zalo (`.txt`/`.csv`) → bảng `raw.chat_message` cùng khuôn email | H-06 | 3 | Mẫu chat 2 ngôn ngữ ra đúng người gửi và thời gian |
| H-08 | **OCR hàng đợi:** chỉ trang không có text; `tesseract -l kor+vie+eng`; cache theo trang | H-02 | 3 | PDF scan mẫu ra text; chạy lại không OCR lại |
| H-09 | **LLM theo lô** (khi P2 duyệt): chỉ thư không trùng, không phải trích dẫn; Message Batches API; cache theo `msg_key`; tóm tắt VI + KO; ngưỡng chi phí chạy thử 200 thư trước | H-06 | 5 | Chạy lại không gọi API cho thư đã có; báo cáo chi phí ước tính trước khi chạy toàn bộ |
| H-10 | **Tìm kiếm:** chỉ mục n-gram VI/KO cho email + text file; lệnh `python -m kops_dw search "..."`; (sau) embedding đa ngôn ngữ | H-02 | 4 | Tìm "납기 지연" và "trễ giao hàng" đều ra thư mẫu tương ứng |
| H-11 | **Dashboard theo mùa, tải lười:** `python -m kops_dw serve` (server tĩnh local), dữ liệu chia `build/data/<season>.json` + tổng hợp nhiều mùa; trang chỉ tải mùa đang xem | H-02 | 6 | 10 mùa giả lập: trang mở < 3 giây, mỗi mùa < 5 MB |
| H-12 | **Mart lịch sử nhiều mùa:** so sánh mùa, lead time, đúng hạn theo nhà máy nhiều mùa, tần suất thay đổi | H-02, H-05 | 6 | Tab "Lịch sử" có so sánh mùa; số mùa 26FW khớp số hiện tại |
| H-13 | **Benchmark + giới hạn:** bộ dữ liệu giả lập 5.000 file / 50.000 thư (nhân bản và biến đổi file thật, không commit) | H-01..H-03 | 3 | Báo cáo thời gian lần đầu / lần sau, RAM, dung lượng lake |

Tổng khoảng 56 giờ. Làm trước (không cần chờ dữ liệu): H-01, H-02, H-03, H-04, H-06, H-08, H-13. Chờ dữ liệu thật để hiệu chỉnh: H-05, H-07, H-09, H-10, H-11, H-12.

## 7. Mục tiêu hiệu năng (máy Mac của PO)

| Tình huống | Mục tiêu |
|---|---|
| Lần nạp đầu: 5.000 file + 50.000 thư (không OCR, không LLM) | < 2 giờ, chạy nền, có thể dừng và chạy tiếp |
| Thêm 10 file / 100 thư mới | < 2 phút |
| SQL model + mart | < 1 phút |
| Dashboard một mùa | mở < 3 giây |

## 8. Rủi ro

- **Dung lượng:** PDF và Excel cũ có thể vài chục GB. Để ở ổ ngoài hoặc thư mục Drive; lake Parquet thường chỉ bằng 1–5% dung lượng gốc.
- **Dữ liệu nhạy cảm trong hộp thư** (lương, nhân sự, thông tin cá nhân): lọc theo thư mục/người gửi trước khi nạp; LLM chỉ chạy khi PO duyệt; không publish dashboard.
- **Template quá khác** ở mùa cũ: báo cáo cách ly cho biết cần viết thêm parser nào, thay vì nạp sai.
- **Chi phí LLM:** luôn chạy thử 200 thư và báo ước tính trước khi chạy toàn bộ; dùng batch + cache.

## 9. Trạng thái (22/10/2026, nhánh `feat/dw-history-scale`)

| ID | Trạng thái | Nghiệm thu (lệnh `python -m kops_dw bench accept --out <thư mục ngoài repo>`, 10/10 PASS) |
|---|---|---|
| H-01 | DONE | Lần 2 không đổi: 0 file hash, 0 file parse. Thêm 1 file: chỉ parse file đó |
| H-02 | DONE | Build lần 2 trên dữ liệu hiện tại **0,4–0,7 s** (mục tiêu < 10 s). 33/33 check pass; mọi bảng raw/stg/core/mart giống hệt pipeline cũ |
| H-03 | DONE | File hỏng, file quá giờ, file làm chết worker: build chạy tiếp, file vào `etl.quarantine` + `build/quarantine.csv`. Build lạnh dữ liệu hiện tại 15 s → 4,5 s |
| H-04 | DONE | 11 template đã biết (`dw/templates/known_templates.json`). File đổi tên cột `ORDER Q'TY` → `UNKNOWN_TEMPLATE`, kèm nhãn và "missing [ORDER Q'TY], new [ORDER QUANTITY]" |
| H-06 | DONE | `.mbox` 1.000 thư (870 nghiệp vụ, 50 trùng, 80 tự động): 1,4 s; `core.email` = 870, `raw.email_filtered` = 80. `.pst` qua `readpst`: đã thử nhánh thiếu công cụ và file hỏng; **chưa thử với file .pst thật** (chưa có mẫu) |
| H-08 | DONE | PDF scan KO/VI/EN tự sinh → OCR đúng người gửi, ngày, tiêu đề, nội dung tiếng Hàn và tiếng Việt; chạy lại: OCR 0 trang, build parse 0 file |
| H-13 | DONE | Xem bảng dưới |
| H-05, H-07, H-09…H-12 | Chưa làm | Chờ dữ liệu thật / quyết định của PO |

**Khác với thiết kế ở §1:**
- Lake ghi theo **lô** (`lake/<bảng>/<parser>/<batch>.parquet`, mỗi dòng có `_key`), không phải một Parquet cho mỗi sha256: 50.000 thư thành 100.000 file nhỏ sẽ chậm. Không phân vùng theo customer/season (một lô trộn nhiều mùa); `lake-compact` gom file khi cần.
- Bảng `raw.*` trong DuckDB được **nạp từ Parquet** (INSERT … SELECT read_parquet) thay vì view: giữ đúng kiểu cột và SQL model không phải sửa. Nạp lake chỉ mất ~2 s với 750 nghìn dòng.
- Phiên bản parser tính tự động = hash code parser + giá trị config parser đọc (+ công cụ tuỳ chọn có/không), không cần nhớ tăng số.
- OCR không chạy trong build; build xếp hàng, lệnh `ocr` xử lý (build luôn nhanh).

**Benchmark H-13** (MacBook 8 CPU, 16 GB; 5.000 file Excel nhân bản từ file thật = 22,7 GB, 50.000 thư trong 10 `.mbox` + 1.000 `.eml`; dữ liệu nằm ngoài repo, không commit):

| Lượt build | Thời gian | Parse | SQL | File parse | RAM lớn nhất | Mục tiêu §7 |
|---|---|---|---|---|---|---|
| Lần đầu | 522 s (8,7 phút) | 438 s | 62 s | 4.287 | 1,1 GB | < 2 giờ: đạt |
| Lần sau, không đổi | 79 s | 0 s | 64 s | 0 | 0,9 GB | — |
| Thêm 10 file + 100 thư | 84 s | 3,5 s | 65 s | 8 | 1,0 GB | < 2 phút: đạt |

- Lake Parquet **40 MB** = 0,2% dung lượng nguồn (4.545 file); DuckDB 69 MB; 743 nghìn dòng đơn hàng/ô xuất hàng; 46.172 thư raw → 43.717 sau gộp trùng, 3.928 thư bị lọc.
- **Điểm nghẽn 1 — `12_core_email.sql` 64 s** (mục tiêu SQL < 1 phút: trượt nhẹ): `core.email_mention` so từng thư với 1.193 mã trong từ điển bằng `strpos` (46 nghìn × 1.193 phép tìm chuỗi). Các file SQL khác < 1 s. Hướng xử lý: tách token mã trong thư rồi join bằng `=` (cùng chỉ mục n-gram của H-10); đổi cách khớp nên cần thêm golden check trên email thật trước khi làm.
- **Điểm nghẽn 2 — parse ORDER RECAP CHALLENGER** (~2,3 s/file, 70% thời gian CPU lần đầu): openpyxl đọc cả workbook kèm định dạng ô (cần màu trạng thái). Chấp nhận được vì mỗi file chỉ parse một lần.
- **Điểm nghẽn 3 — dashboard một file**: 160 MB HTML với dữ liệu giả lập → cần H-11 (dashboard theo mùa, tải lười) trước khi nạp dữ liệu lịch sử thật.
