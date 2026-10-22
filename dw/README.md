# KOPS Data Warehouse — MVP

Kho dữ liệu là **nguồn sự thật duy nhất** của KOPS. Excel (ORDER RECAP, Shipment Status, Production Status), email của buyer và biên bản họp đều được nạp vào cùng một kho. Dashboard và các tính năng sau này (cảnh báo, buyer portal, trợ lý AI) chỉ đọc từ kho này, không đọc trực tiếp file Excel.

```
raw-docs/*.xlsx|xlsb|docx  ┐
raw-docs/inbox/*.eml       ├─► etl + raw ─► stg ─► core ─► mart ─► build/dashboard.html
dw/samples/inbox/*.eml     ┘   (nguyên văn,  (sự kiện   (mô hình  (bảng cho
                                 lineage)     từ ghi chú) chuẩn)    dashboard)
```

## Chạy

Cần Python 3.10+ và LibreOffice. LibreOffice dùng để đọc màu ô (trạng thái style) trong file `.xlsb`; trên macOS cài bằng `brew install --cask libreoffice`. Công cụ tuỳ chọn (thiếu thì được báo, không làm hỏng build): `readpst` cho hộp thư `.pst` (`brew install libpst`), `tesseract` + `poppler` cho OCR (`brew install tesseract tesseract-lang poppler`).

```bash
cd dw
python3 -m venv .venv-mac && .venv-mac/bin/pip install -r requirements.txt   # một lần (trên macOS dùng .venv-mac)
.venv-mac/bin/python -m kops_dw            # build + 33 check + dashboard
.venv-mac/bin/python -m kops_dw test       # chỉ chạy check
open build/dashboard.html
```

Kết quả nằm trong `dw/build/` (đã `.gitignore`):
- `kops.duckdb`: kho dữ liệu. Mở bằng `duckdb build/kops.duckdb` hoặc bất kỳ công cụ BI nào đọc được DuckDB.
- `dashboard.html`: một file HTML chạy offline, dữ liệu nhúng sẵn.
- `lake/`: kết quả parse dạng Parquet + manifest (xem "Nạp tăng dần" bên dưới).
- `quarantine.csv`: file không nạp được và cần người xem (mở được bằng Excel).
- `cache/`: bản `.xlsx` chuyển từ `.xlsb`, text OCR, hộp thư `.pst` đã giải nén; đặt tên theo sha256, tái dùng giữa các lần build.

> `dashboard.html` và `kops.duckdb` chứa dữ liệu kinh doanh của KLMAS. Chỉ chia sẻ trong phạm vi dự án (GUIDELINES §8).

### Thêm dữ liệu

| Muốn thêm | Làm gì |
|---|---|
| Phiên bản mới của một báo cáo | Tải bản mới từ Google Drive của KLMAS, **không đổi tên file**, đặt vào `raw-docs/` theo cây trong `raw-docs/README.md` (vd. `ORDER/CHALLENGER/26FW/`). Quy ước tên của KLMAS: `YYMMDD… <mùa> … <loại báo cáo>`. Bản có ngày báo cáo mới nhất sẽ là bản hiện hành. Pipeline quét đệ quy, bỏ qua thư mục bắt đầu bằng `_` |
| Mùa mới, dữ liệu cũ (lịch sử) | Thả ORDER RECAP vào `ORDER/<KHÁCH>/<MÙA>/`, Shipment / Production Status vào `TRACKING/<BRAND>/<MÙA>/`. Mọi phiên bản đều được giữ; tab "Lịch sử phiên bản" so từng bản với bản trước |
| ORDER RECAP khách khác (DHG, JBEE, KOFA, DKM…) | Như trên. Parser đọc theo tên cột (`order_recap_ext`); mùa lấy từ tiêu đề trong file (ô B1), khách từ tiêu đề/tên file/thư mục (`config.CUSTOMER_KEYS`) |
| Kế hoạch sản xuất | Thả vào `PRODUCTION PLAN/<KHÁCH>/<MÙA>/` (`production_plan`, mỗi sheet một nhà máy) |
| Email: PDF export / in từ Outlook, Gmail, Naver… | Thả file `.pdf` vào `raw-docs/inbox/` (thư mục con tuỳ ý, vd. `inbox/pdf/2026-10/`). Một PDF có thể chứa cả chuỗi thư; nhận header EN/KO/VI và kiểu in của Gmail. PDF scan (không có chữ) được báo `PDF_NO_TEXT` |
| Email: `.eml` / `.msg` | Thả vào `raw-docs/inbox/`. `.msg` cần `pip install extract-msg` |
| Email: cả hộp thư `.mbox` (Google Takeout, Thunderbird) / `.pst` (Outlook) | Thả vào `raw-docs/inbox/`. Đọc từng thư, giữ thư mục/nhãn (`raw.email.folder`), bỏ thư rác/thư tự động (lý do lưu ở `raw.email_filtered`). `.pst` cần `readpst`; thiếu thì file vào cách ly (`MISSING_TOOL`) và được đọc ở lần build đầu tiên sau khi cài |
| Email: PDF scan (không có chữ) | Build đưa trang vào hàng đợi OCR (`etl.ocr_queue`). Chạy `.venv-mac/bin/python -m kops_dw ocr` rồi build lại; thư đọc từ OCR có `text_source='ocr'` và cần đối chiếu với PDF |
| Email: hộp thư (Gmail, Outlook 365, Naver, Hiworks…) | `KOPS_IMAP_PASSWORD=… .venv/bin/python -m kops_dw fetch-imap --host imap.gmail.com --user … --folder KLMAS --since 2026-01-01` (chỉ đọc, không đánh dấu đã đọc). Hoặc agent dùng connector Gmail/Drive lưu `.eml`/PDF vào `raw-docs/inbox/gmail/` |
| File đính kèm của email `.eml` | `.venv/bin/python -m kops_dw attachments` → `raw-docs/EMAIL_ATTACHMENTS/<yyyy-mm>/`, build sau sẽ nạp như file thường (trùng nội dung thì bỏ qua) |
| Biên bản họp | Thả `.docx` vào `raw-docs/MEETINGS/` |
| Báo cáo sản xuất ngày, bảng kiểm, dữ liệu kiểm bên thứ ba | Đã được nhận diện và đăng ký (trạng thái SKIPPED: parser nằm trong kế hoạch Phase 1, `plans/MVP_PHASE1_PLAN.md`) |

Biến môi trường: `KOPS_RAW_DOCS` (thư mục nguồn, có thể ở ổ ngoài hoặc thư mục Google Drive), `KOPS_INBOX` (nhiều thư mục, ngăn bằng `:`), `KOPS_BUILD`, `KOPS_LAKE` (mặc định `build/lake`), `KOPS_SOFFICE` (đường dẫn `soffice` nếu không nằm trong PATH), `KOPS_WORKERS` (số tiến trình parse, mặc định min(8, số CPU); `1` = không song song, dễ debug), `KOPS_PARSE_TIMEOUT` (giây/file, mặc định 600), `KOPS_TEMPLATE_CHECK` (`0` = tắt kiểm tra template), `KOPS_MAIL_SINCE` / `KOPS_MAIL_UNTIL` (YYYY-MM-DD), `KOPS_MAIL_EXCLUDE_FOLDERS`, `KOPS_MAIL_ALLOW` (người gửi/tên miền không bao giờ bị lọc, ngăn bằng dấu phẩy).

## Nạp tăng dần và dữ liệu lịch sử lớn

Theo `plans/HISTORY_SCALE_PLAN.md` (H-01…H-04, H-06, H-08, H-13).

| Bước | Cách làm | Ở đâu |
|---|---|---|
| Manifest | Mỗi file: đường dẫn, kích thước, mtime, sha256. Chỉ tính lại sha256 khi kích thước/mtime đổi | `manifest.py` → `etl.manifest` (NEW / CHANGED / UNCHANGED / REMOVED), `etl.run` (mỗi lần build một dòng: thời gian từng bước, số file parse, RAM) |
| Lake Parquet | Kết quả parse lưu một lần theo khoá = sha256 + phiên bản parser (hash code parser + cấu hình nó đọc) + tên file + đường dẫn trong thư mục nguồn. Build chỉ parse file chưa có khoá; phần còn lại đọc từ Parquet. Kho DuckDB và SQL model vẫn dựng lại mỗi lần (vài giây) | `lake.py`, `parse.py`; `build/lake/<bảng>/<parser>/<batch>.parquet` |
| Song song + cách ly | Parse trong `KOPS_WORKERS` tiến trình; mỗi file có giới hạn thời gian. File lỗi, quá giờ, hoặc làm chết tiến trình (file hỏng, hết RAM) được ghi `FAILED` và cách ly; build vẫn chạy tiếp. Không parse lại file lỗi cho tới khi parser đổi hoặc chạy `build --retry-failed` | `pipeline._parse_all` → `etl.quarantine`, `build/quarantine.csv` |
| Dấu vân tay template | Hash các dòng header của sheet đầu (dòng 1–6). Bố cục chưa có trong `templates/known_templates.json` thì **không nạp**: `UNKNOWN_TEMPLATE`, kèm danh sách nhãn và khác biệt với template gần nhất | `templates.py`; `python -m kops_dw templates` (xem), `templates accept <fp>` (chấp nhận sau khi kiểm tra) |
| Hộp thư | `.mbox` đọc bằng thư viện chuẩn, `.pst` qua `readpst`; đọc theo luồng 2.000 thư/lần; gộp trùng theo `msg_key` trong `core.email` | `ingest/mailbox.py` |
| OCR | Build không chạy OCR; trang scan vào hàng đợi; `python -m kops_dw ocr` chạy tesseract `kor+vie+eng`, cache theo sha256 + trang; build sau chỉ parse lại các PDF đó | `ocr.py` |
| Nghiệm thu, benchmark | Sinh dữ liệu giả lập **ngoài repo** từ file thật, chạy các tình huống của plan | `python -m kops_dw bench accept --out /tmp/kops-bench`; `bench run --out /tmp/kops-bench` (5.000 file / 50.000 thư) |

Lệnh khác: `python -m kops_dw lake-compact` (viết lại lake bỏ các bản parse cũ, khi không có build nào đang chạy).

**Rollback:** lake và cache chỉ là bộ nhớ đệm. Xoá `build/lake` (và/hoặc `build/cache/ocr`, `build/cache/pst`) thì lần build sau parse lại toàn bộ như trước H-02; dữ liệu nguồn không bị đụng tới. Tắt kiểm tra template: `KOPS_TEMPLATE_CHECK=0`. Chạy tuần tự như trước: `KOPS_WORKERS=1`.

## Các lớp dữ liệu

| Schema | Nội dung | Ai ghi |
|---|---|---|
| `etl` | `source_file` (mỗi file: sha256, loại, mùa, ngày báo cáo, bản hiện hành, số dòng, khoá lake, dấu vân tay template), `data_issue` (mọi bất thường, kèm vị trí ô), `manifest`, `run`, `quarantine`, `ocr_queue` | Python |
| `raw` | Dữ liệu gần nguyên văn theo từng template, **mọi phiên bản**: `order_recap_style/color`, `order_line_ext` (khách khác), `production_plan`, `shipment_block/cell`, `production_status(_total)`, `doc_block`, `email` (mỗi thư một dòng, `msg_key` nhận ra cùng một thư ở nhiều file) | Python parser |
| `stg` | Sự kiện trích từ text tự do: `qty_change`, `factory_event`, `email_change`, `requirement`, `action_item`, `decision`; cùng dữ liệu tham chiếu từ `config.py` | Python |
| `core` | Mô hình chuẩn, chỉ lấy bản hiện hành: `style_order`, `order_color`, `shipment_detail`, `production_snapshot`, `meeting`, `requirement`… (`10_core`); `order_portfolio` (mọi khách), `production_plan`, `style_dictionary` (`11_core_customers`); `email` (đã gộp trùng), `email_thread`, `email_mention`, `email_reply`, `change_proposal`, `proposal_file_status` (`12_core_email`) | `sql/1x_*.sql` |
| `mart` | Bảng cho dashboard: `style_360`, `season_kpi`, `factory_kpi`, `supplier_styles`, `shipment_*`, `assortment`, `reconciliation`, `change_log`, `source_lineage` (`20_mart`); `customer_portfolio`, `factory_load_all`, `etd_weekly_all`, `plan_risk`, `file_version`, `version_change`, `email_*` (`25_mart_ext`) | `sql/2x_*.sql` |

Mỗi lần build dựng lại file DuckDB từ đầu (đơn giản, idempotent), nhưng chỉ **parse** file mới hoặc đổi; kết quả parse của các file khác được đọc lại từ lake Parquet (mục "Nạp tăng dần" ở trên).

### Nguồn sự thật cho từng loại dữ liệu

| Dữ liệu | Lấy từ | Ghi chú |
|---|---|---|
| Danh sách style, màu, số lượng đặt, nhà máy, trạng thái | ORDER RECAP | Trạng thái lấy từ màu ô theo legend dòng 1–2. Số lượng ghi dạng text (`170P`) bị loại khỏi tổng, giống hàm SUM của file. Lý do: đó là màu đã huỷ hoặc xoá |
| Assortment màu × size, lô xuất, mẫu đã gửi | Shipment Status | Toàn bộ 104 block có dữ liệu đều khớp tổng của file |
| Đã may, đã kiểm, SL/ngày, kế hoạch cắt/may | Production Status | Không nạp các dòng subtotal (vùng SUM chồng nhau, cho tổng 106.681 thay vì 62.357) |
| Thay đổi số lượng, lịch sử nhà máy | Ghi chú trong ORDER RECAP (`260720 REDUCED 170P➜136P`, `260512 MOVED FACT(HH)`) | |
| Đề xuất thay đổi từ buyer | Email | Chỉ là đề xuất (`PENDING_REVIEW`), không bao giờ tự áp vào dữ liệu. Mã trong email (style, file no, alias) được khớp qua `core.style_dictionary` của mọi khách; đối chiếu với file hiện hành → `IN_FILE` / `NOT_YET` / `PAST_DATE`. Bộ trích xuất LLM (`ingest/email_llm.py`) tắt mặc định, chỉ bật bằng `KOPS_EMAIL_LLM=1` sau khi PO chốt P2 |
| Kế hoạch cắt / may / xuất xưởng, mục tiêu/ngày | PRODUCTION PLAN | BAL tính lại = RDD − (ETA + N); lệch với file thì báo `PLAN_BAL_MISMATCH` |
| Yêu cầu, việc cần làm, nội dung thống nhất | Biên bản họp `.docx` | Nhận diện bảng theo dòng tiêu đề |

## Dashboard

Gồm 8 tab, có chọn mùa, sáng/tối, chạy tốt trên điện thoại. Bấm vào mã style ở bất kỳ đâu để mở **Style 360**: toàn bộ chỉ số, assortment màu × size, từng lô, thay đổi, vấn đề dữ liệu và vị trí dòng gốc.

| Tab | Phục vụ ý tưởng / yêu cầu |
|---|---|
| Tổng quan | Một nguồn sự thật: nguồn đã nạp, chất lượng dữ liệu, mức đáp ứng 14 yêu cầu |
| Control Tower | Ý tưởng 2, 8, 14; yêu cầu #8: tình trạng style, dự kiến xong so với ETD, danh sách cần chú ý |
| Xuất hàng | Ý tưởng 12; yêu cầu #7, #13: lô theo tuần và phương thức, drill-down assortment |
| Nhà máy & NCC | Ý tưởng 4; yêu cầu #4: scorecard nhà máy, gom style theo nhà cung cấp vải |
| Khách hàng & kế hoạch | Mọi khách: SL theo khách, theo tuần ETD, tải nhà máy chung, kế hoạch sản xuất và rủi ro trễ (BAL) |
| Thay đổi | Ý tưởng 11; yêu cầu #2, #5: đề xuất từ email chờ duyệt, lịch sử SL và nhà máy |
| Email | Email theo tuần và loại, luồng trao đổi, thời gian phản hồi, đề xuất đối chiếu với file |
| Lịch sử phiên bản | Mọi phiên bản của từng nguồn; thay đổi giữa các bản, tách thay đổi nghiệp vụ / nghi lỗi nhập / sửa lỗi cũ |
| Đối soát & chất lượng | Ý tưởng 5; yêu cầu #6: lệch giữa các file, danh sách vấn đề kèm vị trí ô |
| Cuộc họp & yêu cầu | Yêu cầu, việc cần làm và nội dung thống nhất lấy từ biên bản |
| Nguồn & lineage | Từng file đã nạp, bản hiện hành, quy tắc nghiệp vụ đang dùng |

## Test

`.venv/bin/python -m kops_dw test` chạy 33 golden number và quy tắc (danh sách trong `kops_dw/checks.py`; các số gốc ở trong `GUIDELINES.md` §7), gồm cả ORDER RECAP khách khác, kế hoạch sản xuất, lịch sử phiên bản và email mẫu. Ví dụ quy tắc: không có thay đổi nào từ email bị tự áp dụng; mọi style đều truy được về file nguồn; email mẫu chứa prompt injection không làm thay đổi dữ liệu. Thiếu file nguồn nào thì bài test tương ứng được SKIP.

## Giới hạn của MVP

- **Email:** dùng bộ trích xuất rule-based (regex cho mã style, %, ETD, màu). 4 email trong `samples/inbox/` là **dữ liệu mẫu** (gắn `X-KOPS-Sample: true`, hiển thị nhãn SAMPLE). Bước tiếp theo là thay bằng LLM, vẫn giữ đúng output contract và bước duyệt (P-05).
- **Chưa nạp:** sheet FAB (vật tư, định mức), báo cáo kiểm, báo cáo sản xuất ngày, minimap. Các tab liên quan ghi rõ "chưa có nguồn".
- **Quy tắc nghiệp vụ** (RDD = ETD + 12, buffer 5 ngày, 45 pcs/ngày mặc định, dung sai 5%) nằm ở `config.py`, chờ KLMAS xác nhận (`analys-docs/open_questions.md`).
- **Alias mã style** cho 3 cặp mã lệch giữa các file (Q05) đang tạm map và đánh dấu `STYLE_ALIAS_UNCONFIRMED`.
- **DuckDB** dùng cho MVP. SQL viết theo lớp `raw → core → mart` nên chuyển sang PostgreSQL + dbt (kiến trúc đã chốt) chủ yếu là việc đổi dialect.

## Cấu trúc thư mục

```
dw/
├── Makefile, requirements.txt
├── kops_dw/
│   ├── config.py          # đường dẫn, quy tắc nghiệp vụ, alias nhà máy/style, mức đáp ứng yêu cầu
│   ├── pipeline.py        # discover → manifest → registry → parse (song song) → nạp lake → chạy SQL
│   ├── manifest.py        # size/mtime/sha256 của từng file (H-01)
│   ├── lake.py            # Parquet lake: ghi/đọc kết quả parse (H-02)
│   ├── parse.py           # parse một file trong worker, khoá cache, phiên bản parser, timeout (H-02/H-03)
│   ├── templates.py       # dấu vân tay header Excel (H-04); ../templates/known_templates.json
│   ├── ocr.py             # hàng đợi OCR tesseract (H-08)
│   ├── bench.py           # dữ liệu giả lập, nghiệm thu, benchmark (H-13)
│   ├── excel.py           # đọc workbook, xlsb → xlsx qua LibreOffice, đọc màu ô
│   ├── ingest/            # một module cho mỗi loại nguồn (mailbox.py: .mbox/.pst, H-06)
│   ├── checks.py          # golden tests
│   └── dashboard.py       # xuất mart → JSON → HTML
├── sql/                   # 00_raw (DDL) · 10_core · 15_issues · 20_mart
├── templates/dashboard.html
└── samples/inbox/         # email mẫu (SAMPLE)
```
