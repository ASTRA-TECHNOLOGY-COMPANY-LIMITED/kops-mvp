# KOPS Data Warehouse — MVP

Kho dữ liệu là **nguồn sự thật duy nhất** của KOPS. Excel (ORDER RECAP, Shipment Status, Production Status), email của buyer và biên bản họp đều được nạp vào cùng một kho. Dashboard và các tính năng sau này (cảnh báo, buyer portal, trợ lý AI) chỉ đọc từ kho này, không đọc trực tiếp file Excel.

```
raw-docs/*.xlsx|xlsb|docx|pdf ┐
raw-docs/**/*.mhtml            ├─► etl + raw ─► stg ─► core ─► mart ─► build/data/<mùa>.json + dashboard.html
raw-docs/inbox/*.eml|pdf|mbox  │   (nguyên văn,  (sự kiện   (mô hình  (bảng cho
dw/samples/inbox/*             ┘    lineage)     từ ghi chú) chuẩn)    dashboard)
```

## Chạy

Cần Python 3.10+ và LibreOffice. LibreOffice dùng để đọc màu ô (trạng thái style) trong file `.xlsb`; trên macOS cài bằng `brew install --cask libreoffice`. Công cụ tuỳ chọn (thiếu thì được báo, không làm hỏng build): `readpst` cho hộp thư `.pst` (`brew install libpst`), `tesseract` + `poppler` cho OCR (`brew install tesseract tesseract-lang poppler`).

```bash
cd dw
python3 -m venv .venv-mac && .venv-mac/bin/pip install -r requirements.txt   # một lần (trên macOS dùng .venv-mac)
.venv-mac/bin/python -m kops_dw            # build + check + dashboard
.venv-mac/bin/python -m kops_dw test       # chỉ chạy check (golden cũ chạy trên snapshot ghim file, xem "Test")
.venv-mac/bin/python -m kops_dw serve --open   # http://127.0.0.1:8765/ : dashboard quản lý; /dashboard.html: dashboard phân tích
```

Kết quả nằm trong `dw/build/` (đã `.gitignore`):
- `kops.duckdb`: kho dữ liệu. Mở bằng `duckdb build/kops.duckdb` hoặc bất kỳ công cụ BI nào đọc được DuckDB.
- `dashboard.html` + `data/`: trang dashboard và dữ liệu chia theo mùa (`data/<mùa>.json`, `data/_common.json`, `data/index.json`); mở qua `serve`. `dashboard --single` ghi lại bản một file nhúng mọi mùa (mở trực tiếp được, chỉ hợp với dữ liệu nhỏ).
- `snapshot_*.duckdb`: kho dựng lại từ lake với các file golden được ghim (do `test` tạo, xem "Test").
- `lake/`: kết quả parse dạng Parquet + manifest (xem "Nạp tăng dần" bên dưới).
- `quarantine.csv`: file không nạp được và cần người xem (mở được bằng Excel).
- `cache/`: bản `.xlsx` chuyển từ `.xlsb`, text OCR, hộp thư `.pst` đã giải nén; đặt tên theo sha256, tái dùng giữa các lần build.

> `dashboard.html` và `kops.duckdb` chứa dữ liệu kinh doanh của KLMAS. Chỉ chia sẻ trong phạm vi dự án (GUIDELINES §8).

### Chạy bằng Docker

Cần Docker (Docker Desktop trên Mac Apple Silicon, hoặc Docker Engine trên Linux x86_64) và thư mục `raw-docs/` cạnh
`docker-compose.yml`. Không cần Python, LibreOffice hay tesseract trên máy: image có đủ.

```bash
make up          # dựng image, build kho + chạy mọi check + dựng dashboard, rồi mở http://127.0.0.1:8765
make up-real     # như trên nhưng không có dữ liệu giả định (KOPS_SIM=0)
make refresh     # có file KLMAS mới: build tăng dần + check + dựng lại dashboard; trang đang mở tự nạp (không cần restart)
make check       # chạy toàn bộ check trong container
make check-ui    # kiểm thử giao diện (Playwright + Chromium), ảnh chụp vào UI_OUT (mặc định /tmp/kops-ui, ngoài repo)
make report SEASON=27SS REPORT_LANG=ko   # PDF "Việc cần xử lý" + "Tổng quan" vào ./reports (git-ignored, có dữ liệu KLMAS)
make logs        # xem log; make down: dừng; make rebuild: dựng lại image; make clean: xoá volume build
```

- `kops-build` chạy một lần: build → check → dashboard; check đỏ thì dừng và `kops-dashboard` không chạy.
- `raw-docs` mount **chỉ đọc**; kết quả build nằm trong volume `kops_build` (không lẫn với `dw/build` của máy). Image chỉ có
  code và email mẫu tổng hợp, không có file KLMAS (kiểm: `docker run --rm --entrypoint ls kops-dw:local -R /app`).
- Cổng chỉ mở trên `127.0.0.1:8765` (máy này). Server chỉ phục vụ `manager.html`, `dashboard.html`, `data/**.json`,
  `vendor/*.js`; file DuckDB, lake không truy cập được qua HTTP.
- `ANTHROPIC_API_KEY` (khi bật bóc tách email bằng AI) đặt trong `.env` ở gốc repo (không commit), compose đọc lúc chạy, không
  đưa vào image. Múi giờ container: Asia/Ho_Chi_Minh; `KOPS_TODAY=YYYY-MM-DD make up` để cố định "hôm nay".
- Bật / tắt dữ liệu giả định: `make up` (bật, có nhãn "Giả định" trên trang) / `make up-real`; trên trang còn công tắc
  "Hiện dữ liệu giả định".
- Đo ngày 23/10/2026 (MacBook Apple Silicon 8 CPU, sau E-07): image 2,32 GB (có Chromium cho PDF và kiểm thử giao diện; trước
  là 1,24 GB); `make up` với volume trống 2 phút 18 giây (build kho lạnh 106 s); `make refresh` 43 s; `make check-ui` 92 s
  (153 lượt mở trang, 891 kiểm tra); 92/92 check trong container = ngoài container.

### Chatbot hỏi đáp dữ liệu (F-04)

- **Chế độ cơ bản** (mặc định, không cần API key, không gửi gì ra ngoài): nhận diện ý định + mã style / mùa / khách / nhà máy, chạy
  truy vấn cố định trên mart, trả lời ngắn kèm bảng, nguồn, ngày dữ liệu. Câu không hiểu thì nói rõ và gợi ý câu mẫu, không đoán.
  Golden: `dw/eval/chat_cases.json` (43 câu VI / KO), chạy `python -m kops_dw chat-eval`.
- **Chế độ AI** (tắt mặc định): `KOPS_CHAT_LLM=1` + `ANTHROPIC_API_KEY` trong `.env`, `pip install anthropic`. Claude dùng các truy
  vấn của chế độ cơ bản và một tool `query_mart` chỉ chạy SELECT trên schema `mart` / `dim` (kết nối chỉ đọc, chặn hàm đọc file,
  500 dòng, 5 giây). **Bật chế độ này nghĩa là câu hỏi và số liệu kho dữ liệu (mã style, số lượng, tiêu đề email…) được gửi tới
  Claude API. PO phải xác nhận phạm vi đồng ý của KLMAS trước khi bật: đồng ý P2 (23/10) mới nói về nội dung email.**

### Thêm file KLMAS mới (hằng ngày)

1. **Tải file** từ Google Drive của KLMAS, **giữ nguyên tên file** (không đổi tên, không ghi đè bản cũ: bản mới có ngày mới ở
   đầu tên, kho tự lấy bản mới nhất).
2. **Đặt vào `raw-docs/`** theo bảng "Quy ước khi thêm file" trong `raw-docs/README.md`. Hay gặp nhất:
   - báo cáo sản xuất ngày → `PRODUCTION/<BRAND>/<MÙA>/<NHÀ MÁY>/` (vd. `PRODUCTION/CHALLENGER/27SS/NATEXCO/`);
   - ORDER RECAP → `ORDER/<KHÁCH>/<MÙA>/`; kế hoạch sản xuất → `PRODUCTION PLAN/<KHÁCH>/<MÙA>/`;
   - Shipment / Production Status → `TRACKING/<BRAND>/<MÙA>/`; bảng kiểm KLMAS → `INSPECTION/ORDER_TRACKING/<BRAND>/<MÙA>/`;
   - email (`.mhtml`, `.eml`, PDF) không thuộc style nào → `inbox/`.
   Chỉ copy file chưa có (so tên file); copy lại cả thư mục Drive sẽ sinh bản trùng.
3. **Chạy** ở gốc repo: `make refresh` (Docker; build tăng dần chỉ đọc file mới / đổi, chạy toàn bộ check, dựng lại dashboard).
   Không dùng Docker: `cd dw && .venv-mac/bin/python -m kops_dw`.
4. **Xem kết quả**:
   - trang đang mở ở http://127.0.0.1:8765/ tự nạp dữ liệu mới trong vòng 1 phút, không cần tải lại; dòng đầu trang ghi
     "dữ liệu tới … · file mới nhất … · build …" (chữ chuyển xanh khi vừa nạp);
   - check phải `ALL PASS`. Check đỏ thì dashboard **giữ bản cũ** (`make logs` xem check nào đỏ);
   - file không đọc được nằm trong `dw/build/quarantine.csv` (Docker: volume build), file mẫu Excel lạ: `python -m kops_dw templates`;
   - trang "Sức khoẻ dữ liệu": độ phủ cycle, độ tươi báo cáo ngày, dòng không nối được với style.

### Thêm dữ liệu (chi tiết theo loại)

| Muốn thêm | Làm gì |
|---|---|
| Phiên bản mới của một báo cáo | Tải bản mới từ Google Drive của KLMAS, **không đổi tên file**, đặt vào `raw-docs/` theo cây trong `raw-docs/README.md` (vd. `ORDER/CHALLENGER/26FW/`). Quy ước tên của KLMAS: `YYMMDD… <mùa> … <loại báo cáo>`. Bản có ngày báo cáo mới nhất sẽ là bản hiện hành. Pipeline quét đệ quy, bỏ qua thư mục bắt đầu bằng `_` |
| Mùa mới, dữ liệu cũ (lịch sử) | Thả ORDER RECAP vào `ORDER/<KHÁCH>/<MÙA>/`, Shipment / Production Status vào `TRACKING/<BRAND>/<MÙA>/`. Mọi phiên bản đều được giữ; tab "Lịch sử phiên bản" so từng bản với bản trước |
| ORDER RECAP khách khác (DHG, JBEE, KOFA, DKM…) | Như trên. Parser đọc theo tên cột (`order_recap_ext`); mùa lấy từ tiêu đề trong file (ô B1), khách từ tiêu đề/tên file/thư mục (`config.CUSTOMER_KEYS`) |
| Kế hoạch sản xuất | Thả vào `PRODUCTION PLAN/<KHÁCH>/<MÙA>/` (`production_plan`, mỗi sheet một nhà máy) |
| Email: PDF export / in từ Outlook, Gmail, Naver… | Thả file `.pdf` vào `raw-docs/inbox/` (thư mục con tuỳ ý, vd. `inbox/pdf/2026-10/`). Một PDF có thể chứa cả chuỗi thư; nhận header EN/KO/VI và kiểu in của Gmail. PDF scan (không có chữ) được báo `PDF_NO_TEXT` |
| Email: `.eml` / `.msg` | Thả vào `raw-docs/inbox/`. `.msg` cần `pip install extract-msg` |
| Email: luồng Gmail lưu từ trình duyệt (`.mhtml`) | Ở bất kỳ đâu trong `raw-docs/` (gói theo style `STYLES/…`, `inbox/mhtml/…`). Mỗi file một luồng; tách từng thư (header `Tên <địa chỉ>` + ngày `2026년 7월 20일 오전 7:27`, `받는사람:`, `참조:`), thư trích dẫn Outlook giữ là `is_quoted`, danh sách đính kèm (tên, kích thước, link tải hết hạn) vào `raw.email_attachment` |
| SHIPPING SCHEDULE, bảng "생산계획표 · 오더 현황표" (PDF buyer in) | `TRACKING/<BRAND>/<MÙA>/`. SHIPPING SCHEDULE → `core.shipping_schedule`, đối chiếu ORDER RECAP (`mart.schedule_vs_recap`); PDF của buyer (cần `pdftotext`, gói poppler) → `mart.plan_vs_buyer_view`, chỉ để đối chiếu |
| Tài liệu kỹ thuật, rập CAD, ảnh, zip | Không mở file: W.S, CMT, comment, mini marker, định mức, CAD (`.dxf .pds .sty .rul .mdl .pax`)… chỉ đọc tên file + tên thư mục email của KLMAS → `core.document` (khách, style, nhà máy, mùa, giai đoạn, ngày). File báo cáo lớn hơn `KOPS_MAX_PARSE_MB` (30) cũng không mở, vào cách ly `TOO_LARGE` |
| Email: cả hộp thư `.mbox` (Google Takeout, Thunderbird) / `.pst` (Outlook) | Thả vào `raw-docs/inbox/`. Đọc từng thư, giữ thư mục/nhãn (`raw.email.folder`), bỏ thư rác/thư tự động (lý do lưu ở `raw.email_filtered`). `.pst` cần `readpst`; thiếu thì file vào cách ly (`MISSING_TOOL`) và được đọc ở lần build đầu tiên sau khi cài |
| Email: PDF scan (không có chữ) | Build đưa trang vào hàng đợi OCR (`etl.ocr_queue`). Chạy `.venv-mac/bin/python -m kops_dw ocr` rồi build lại; thư đọc từ OCR có `text_source='ocr'` và cần đối chiếu với PDF |
| Email: hộp thư (Gmail, Outlook 365, Naver, Hiworks…) | `KOPS_IMAP_PASSWORD=… .venv/bin/python -m kops_dw fetch-imap --host imap.gmail.com --user … --folder KLMAS --since 2026-01-01` (chỉ đọc, không đánh dấu đã đọc). Hoặc agent dùng connector Gmail/Drive lưu `.eml`/PDF vào `raw-docs/inbox/gmail/` |
| File đính kèm của email `.eml` | `.venv/bin/python -m kops_dw attachments` → `raw-docs/EMAIL_ATTACHMENTS/<yyyy-mm>/`, build sau sẽ nạp như file thường (trùng nội dung thì bỏ qua) |
| Biên bản họp | Thả `.docx` vào `raw-docs/MEETINGS/` |
| Báo cáo sản xuất ngày | `PRODUCTION/…/<NHÀ MÁY>/`, tên có `DAILY PRODUCTION REPORT` (`daily_production`, D-02): mỗi sheet một ngày, ngày lấy từ tên sheet; sản lượng ngày = chênh lệch luỹ kế (TODAY nhà máy hay để nguyên sau khi may xong) |
| Bảng kiểm KLMAS | Tên có `KLMAS INSPECTION REPORT` (`inspection_tracker`): SL đạt theo style × món × màu × ngày, tổng ngày A/C/D/F; **không đọc tên kiểm viên**; `REQUEST ETD` → đề xuất chờ duyệt |
| Dữ liệu kiểm bên thứ ba | `INSPECTION/THIRD_PARTY/INPUT DATA.xlsx` (`qc_third_party`): mỗi lần kiểm + mã lỗi; không đọc cột QC NAME |

Biến môi trường: `KOPS_RAW_DOCS` (thư mục nguồn, có thể ở ổ ngoài hoặc thư mục Google Drive), `KOPS_INBOX` (nhiều thư mục, ngăn bằng `:`), `KOPS_BUILD`, `KOPS_LAKE` (mặc định `build/lake`), `KOPS_SOFFICE` (đường dẫn `soffice` nếu không nằm trong PATH), `KOPS_WORKERS` (số tiến trình parse, mặc định min(8, số CPU); `1` = không song song, dễ debug), `KOPS_PARSE_TIMEOUT` (giây/file, mặc định 600), `KOPS_TEMPLATE_CHECK` (`0` = tắt kiểm tra template), `KOPS_MAIL_SINCE` / `KOPS_MAIL_UNTIL` (YYYY-MM-DD), `KOPS_MAIL_EXCLUDE_FOLDERS`, `KOPS_MAIL_ALLOW` (người gửi/tên miền không bao giờ bị lọc, ngăn bằng dấu phẩy; cộng với danh sách trong `dw/mail_allow.local.txt`, file local không commit, mẫu ở `mail_allow.example.txt`; tạo từ email đã nạp: `mail-allow suggest --write`, xem số thư bị lọc trước/sau: `mail-allow report`; không nhận cả tên miền Gmail/Naver/Daum), `KOPS_MAX_PARSE_MB` (mặc định 30), `KOPS_KLMAS_DOMAINS` (mặc định `klmasvn.com`, để biết thư do KLMAS gửi).

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
| Nghiệm thu, benchmark | Sinh dữ liệu giả lập **ngoài repo** từ file thật, chạy các tình huống của plan | `python -m kops_dw bench accept --out /tmp/kops-bench`; `bench run --out /tmp/kops-bench` (5.000 file / 50.000 thư; 23/10: build ấm 19 s, SQL 1,9 s); `bench dash` (kích thước file mùa, thời gian mở trang) |

Lệnh khác: `python -m kops_dw lake-compact` (viết lại lake bỏ các bản parse cũ, khi không có build nào đang chạy).

**Rollback:** lake và cache chỉ là bộ nhớ đệm. Xoá `build/lake` (và/hoặc `build/cache/ocr`, `build/cache/pst`) thì lần build sau parse lại toàn bộ như trước H-02; dữ liệu nguồn không bị đụng tới. Tắt kiểm tra template: `KOPS_TEMPLATE_CHECK=0`. Chạy tuần tự như trước: `KOPS_WORKERS=1`.

## Các lớp dữ liệu

| Schema | Nội dung | Ai ghi |
|---|---|---|
| `etl` | `source_file` (mỗi file: sha256, loại, mùa, ngày báo cáo, bản hiện hành, số dòng, khoá lake, dấu vân tay template), `data_issue` (mọi bất thường, kèm vị trí ô), `manifest`, `run`, `quarantine`, `ocr_queue` | Python |
| `raw` | Dữ liệu gần nguyên văn theo từng template, **mọi phiên bản**: `order_recap_style/color`, `order_line_ext` (khách khác), `production_plan`, `shipment_block/cell`, `production_status(_total)`, `doc_block`, `email` (mỗi thư một dòng, `msg_key` nhận ra cùng một thư ở nhiều file) | Python parser |
| `stg` | Sự kiện trích từ text tự do: `qty_change`, `factory_event`, `email_change`, `email_event` (mốc / lô hàng đọc từ tiêu đề thư), `document` (metadata tài liệu kỹ thuật), `requirement`, `action_item`, `decision`; cùng dữ liệu tham chiếu từ `config.py` | Python |
| `core` | Mô hình chuẩn, chỉ lấy bản hiện hành: `style_order`, `order_color`, `shipment_detail`, `production_snapshot`, `meeting`, `requirement`… (`10_core`); `order_portfolio` (mọi khách), `production_plan`, `style_dictionary` (`11_core_customers`); `email` (đã gộp trùng), `email_thread`, `email_mention` (khớp mã bằng token, N-07), `email_reply`, `change_proposal`, `proposal_file_status` (`12_core_email`); `document` (`13`); `shipment_event`, `style_milestone` (`14`); `shipping_schedule`, `buyer_order_status` (`16`) | `sql/1x_*.sql` |
| `dim`, `fact`, `bridge` | Mô hình liên kết (D-01): khách, brand, mùa, ngày, nhà máy (+ alias), style (+ alias), bên liên lạc; fact đơn, kế hoạch, sản lượng ngày, kiểm, lỗi, lô xuất, mốc, thay đổi, email, tài liệu; bridge nhà máy theo thời gian, email ↔ style / người. Chi tiết: `docs/data_model.md` | `sql/30_model.sql` |
| `sim` | Dữ liệu **giả định** cho bản demo (D-04): mùa 25SS / 25FW, sản lượng / kiểm / lô xuất cho chỗ thiếu; seed cố định, `assumption_id` (`docs/assumptions.md`); không vào core / fact / check golden; `KOPS_SIM=0` để tắt | `kops_dw/sim.py` |
| `mart` | Bảng cho dashboard: `style_funnel` màu × size + cờ (`34_funnel`); `mgr_action` việc cần xử lý (`42_actions`); `style_360`, `season_kpi`, `factory_kpi`, `supplier_styles`, `shipment_*`, `assortment`, `reconciliation`, `change_log`, `source_lineage` (`20_mart`); `customer_portfolio`, `factory_load_all`, `etd_weekly_all`, `plan_risk`, `file_version`, `version_change`, `email_*` (`25_mart_ext`); `style_timeline`, `style_event`, `material_delay`, `schedule_vs_recap`, `plan_vs_buyer_view` (`26_mart_milestone`); `cycle_coverage` (`32`); `mgr_*` chỉ số quản lý, tách phần thật / giả định (`40_mgr`, định nghĩa `docs/metrics.md`) | `sql/2x–4x_*.sql` |

Mỗi lần build dựng lại file DuckDB từ đầu (đơn giản, idempotent), nhưng chỉ **parse** file mới hoặc đổi; kết quả parse của các file khác được đọc lại từ lake Parquet (mục "Nạp tăng dần" ở trên).

### Nguồn sự thật cho từng loại dữ liệu

| Dữ liệu | Lấy từ | Ghi chú |
|---|---|---|
| Danh sách style, màu, số lượng đặt, nhà máy, trạng thái | ORDER RECAP | Trạng thái lấy từ màu ô theo legend dòng 1–2. Số lượng ghi dạng text (`170P`) bị loại khỏi tổng, giống hàm SUM của file. Lý do: đó là màu đã huỷ hoặc xoá |
| Assortment màu × size, lô xuất, mẫu đã gửi | Shipment Status | Toàn bộ 104 block có dữ liệu đều khớp tổng của file |
| Đã may, đã kiểm, SL/ngày, kế hoạch cắt/may | Production Status | Không nạp các dòng subtotal (vùng SUM chồng nhau, cho tổng 106.681 thay vì 62.357) |
| Thay đổi số lượng, lịch sử nhà máy | Ghi chú trong ORDER RECAP (`260720 REDUCED 170P➜136P`, `260512 MOVED FACT(HH)`) | |
| Đề xuất thay đổi từ buyer | Email | Chỉ là đề xuất (`PENDING_REVIEW`), không bao giờ tự áp vào dữ liệu. Mã trong email (style, file no, alias) được khớp qua `core.style_dictionary` của mọi khách; đối chiếu với file hiện hành → `IN_FILE` / `NOT_YET` / `PAST_DATE`. Bộ trích xuất LLM (`ingest/email_llm.py`) tắt mặc định; bật bằng `KOPS_EMAIL_LLM=1` (KLMAS đồng ý ngày 23/10, chỉ Claude API) |
| Mốc tiến độ style, lô hàng (thành phẩm đi / vật tư về) | Tiêu đề email + tên tài liệu kỹ thuật | Luật trên tiêu đề (`milestones.py`), không phải dữ liệu đã duyệt; mỗi mốc ghi thư/file nguồn. Thư xuất hàng nối với style qua lô cùng nhà máy trong Shipment Status (ETD ±3 ngày). Tiêu đề viết tự do: thư không đọc được chỉ là không có mốc |
| Kế hoạch cắt / may / xuất xưởng, mục tiêu/ngày | PRODUCTION PLAN | Quy tắc hạn của từng file được lưu theo dòng (`due_etd_rule` RDD-14/-12, `due_eta_rule` RDD-3/-2/ETD+7, `bal_rule` ETA+2/+1, ETD VN-ETD, ETA VN-ETA); BAL tính lại theo đúng quy tắc đó, lệch thì `PLAN_BAL_MISMATCH`; ngày chạy ngược hàng tháng (gõ sai năm) → `YEAR_SUSPECT`, không tự sửa |
| Kế hoạch xuất chính thức (FIXED EX-FACT / ETD / ETA) | SHIPPING SCHEDULE (CHALLENGER) | Dòng tổng của từng khối được tính lại, lệch thì `TOTAL_MISMATCH` |
| Yêu cầu, việc cần làm, nội dung thống nhất | Biên bản họp `.docx` | Nhận diện bảng theo dòng tiêu đề |

## Dashboard

**Dashboard quản lý** (trang đầu của `serve`, `templates/manager.html`, D-06, E-04..E-08): 9 trang — **Việc cần xử lý** (trang
đầu, E-04: kế hoạch / dự báo trễ, vật tư về trễ, thiếu duyệt mẫu trước ngày cắt, nhà máy không gửi báo cáo ngày, đề xuất email
chờ duyệt, lệch số giữa file; mỗi dòng có lý do, nguồn, hạn và mở Style 360; `mart.mgr_action`), Tổng quan, Tiến độ sản xuất (S-curve
kế hoạch / thực tế, dự báo xong so với ETD, tải nhà máy), Xuất hàng, Chất lượng (tỉ lệ lỗi, Pareto, phàn nàn buyer), Nhà máy
(scorecard), Thay đổi & email, Style 360 (mốc, funnel, sản lượng ngày, lô, email, thay đổi, tài liệu), Sức khoẻ dữ liệu (độ phủ
cycle, độ tươi, dòng không nối được, chênh lệch file). Lọc mùa (có "Tất cả"), khách, brand, nhà máy; công tắc "Hiện dữ liệu giả
định" — phần giả định luôn có nhãn **Giả định** và mã giả định khi rê chuột. Biểu đồ: ECharts 5.5.1 lưu trong
`templates/vendor/` (không CDN). Dữ liệu `build/data/mgr/<mùa>.json`.
- Mùa mặc định = mùa đang chạy (mùa có ETD gần nhất phía trước, hiện là 27SS); lựa chọn mùa, ngôn ngữ, tab được nhớ theo người xem
  (localStorage). 27SS chưa có sản lượng ngày / kiểm: biểu đồ ghi "Chưa có dữ liệu", không sinh giả định.
- **Song ngữ VI / KO** (E-05): nút ngôn ngữ ở đầu trang. Chuỗi giao diện viết bằng tiếng Việt trong `L('…')`, bản dịch ở
  `templates/i18n/{vi,ko}.json` (thuật ngữ nghiệp vụ giữ tiếng Anh). Thêm chuỗi mới: viết `L('…')`, chạy
  `python -m kops_dw i18n` (cập nhật `vi.json`, liệt kê khoá thiếu tiếng Hàn), thêm bản dịch vào `ko.json`; check đỏ khi còn
  chuỗi thiếu bản dịch hoặc chữ tiếng Việt nằm ngoài `L()`.
- **Xuất** (E-06): nút "In / PDF" trên Việc cần xử lý và Tổng quan (A4 ngang, có ngày dữ liệu, bộ lọc, nhãn giả định); nút CSV dưới
  mọi bảng (mọi dòng theo bộ lọc, tạo ngay trong trình duyệt); `python -m kops_dw report --season 27SS --lang ko --out <thư mục>`
  in PDF bằng Chromium headless (Docker: `make report`). PDF / CSV có dữ liệu KLMAS: chỉ lưu trên máy.
- Mã câu hỏi KLMAS trên chip lấy tiêu đề từ `analys-docs/open_questions.md` lúc dựng (`kops_dw/questions.py`).

**Dashboard phân tích** (`/dashboard.html`, 12 tab) như dưới đây.

Gồm 12 tab, sáng/tối, chạy tốt trên điện thoại. **Bộ lọc mùa áp cho mọi tab** (H-11): trang chỉ tải dữ liệu của mùa đang xem (`data/<mùa>.json`) cùng phần chung; đổi mùa thì tải thêm mùa đó. Mở bằng `python -m kops_dw serve` (máy chủ tĩnh chỉ nghe 127.0.0.1, chỉ phục vụ `dashboard.html` và `data/*.json`); `?season=27SS` mở thẳng một mùa. Email được xếp vào mùa của style mà thư nhắc tới; thư không nhắc style nào hiện ở mọi mùa. Bấm vào mã style ở bất kỳ đâu để mở **Style 360**: toàn bộ chỉ số, assortment màu × size, từng lô, thay đổi, vấn đề dữ liệu và vị trí dòng gốc.

| Tab | Phục vụ ý tưởng / yêu cầu |
|---|---|
| Tổng quan | Một nguồn sự thật: nguồn đã nạp, chất lượng dữ liệu, mức đáp ứng 14 yêu cầu |
| Control Tower | Ý tưởng 2, 8, 14; yêu cầu #8: tình trạng style, dự kiến xong so với ETD, danh sách cần chú ý |
| Xuất hàng | Ý tưởng 12; yêu cầu #7, #13: lô theo tuần và phương thức, drill-down assortment |
| Nhà máy & NCC | Ý tưởng 4; yêu cầu #4: scorecard nhà máy, gom style theo nhà cung cấp vải |
| Khách hàng & kế hoạch | Mọi khách của mùa đang chọn: SL theo khách, theo tuần ETD, tải nhà máy chung, kế hoạch sản xuất và rủi ro trễ (BAL) |
| Tiến độ style | Timeline mốc theo style (FPP request → CMT → CFMD → kiểm vải → định mức → inline → kiểm hàng → xuất), lô hàng từ email, vật tư về nhà máy dời ETD theo nhà máy |
| Thay đổi | Ý tưởng 11; yêu cầu #2, #5: đề xuất từ email chờ duyệt, lịch sử SL và nhà máy |
| Email | Email theo tuần và loại, luồng trao đổi, thời gian phản hồi, đề xuất đối chiếu với file |
| Lịch sử phiên bản | Mọi phiên bản của từng nguồn; thay đổi giữa các bản, tách thay đổi nghiệp vụ / nghi lỗi nhập / sửa lỗi cũ |
| Đối soát & chất lượng | Ý tưởng 5; yêu cầu #6: lệch giữa các file, SHIPPING SCHEDULE so với ORDER RECAP, bảng hiện trạng đơn của buyer so với kế hoạch KLMAS, danh sách vấn đề kèm vị trí ô |
| Cuộc họp & yêu cầu | Yêu cầu, việc cần làm và nội dung thống nhất lấy từ biên bản |
| Nguồn & lineage | Từng file đã nạp, bản hiện hành, quy tắc nghiệp vụ đang dùng |

## Test

`.venv-mac/bin/python -m kops_dw test` chạy 92 golden number và quy tắc (danh sách trong `kops_dw/checks.py`; các số gốc ở trong `GUIDELINES.md` §7), gồm cả ORDER RECAP khách khác, kế hoạch sản xuất, lịch sử phiên bản, email thật (.mhtml: mốc CHF3WJK6701, lô ABKHPH2608058 / JAKEHPH2609051) và email mẫu.

**Golden theo bản file (N-05):** mỗi số golden thuộc về một phiên bản file. Check golden ghi rõ các file nó được đo (`GOLDEN_2210`: bản hiện hành ngày 22/10; `GOLDEN_2310`: ORDER RECAP 261022, PRODUCTION STATUS 261021) và chạy trên một kho snapshot dựng lại từ lake (không parse lại, ~1 s) trong đó các file ghim là bản hiện hành của family của chúng. Bản mới tới sau không làm đỏ golden cũ; bản mới có golden riêng lấy từ ô tổng của chính file đó (tên check ghi sheet/ô). Ví dụ quy tắc: không có thay đổi nào từ email bị tự áp dụng; mọi style đều truy được về file nguồn; email mẫu chứa prompt injection không làm thay đổi dữ liệu. Thiếu file nguồn nào thì bài test tương ứng được SKIP.

**Mã câu hỏi (E-01):** mọi mã `Qnn` trong code / doc / template phải có trong `kops_dw/questions.py` kèm từ khoá của tiêu đề trong
`open_questions.md`; khi KLMAS đổi mã câu hỏi, check đỏ cho tới khi cập nhật bảng này.

**Kiểm thử giao diện (E-07):** `python -m kops_dw check-ui --out <thư mục ngoài repo>` (Docker: `make check-ui`): mọi trang ×
sáng/tối × desktop/mobile × VI/KO × giả định tắt/bật (mùa 26FW) + các trang 27SS: không lỗi console, mọi biểu đồ có dữ liệu hoặc
"Chưa có dữ liệu", chip giả định chỉ có khi bật, không cuộn ngang trên mobile, KPI chính = mart (đọc DuckDB), trang đang mở nhận
bản build mới mà không tải lại. Dùng Chromium của hệ thống (macOS: Google Chrome; `KOPS_CHROME` để chỉ đường dẫn).

## Giới hạn của MVP

- **Email:** dùng bộ trích xuất rule-based (regex cho mã style, %, ETD, màu; mốc / lô hàng từ tiêu đề). Email trong `samples/inbox/` (gồm một luồng `.mhtml` tổng hợp) là **dữ liệu mẫu** (gắn `X-KOPS-Sample: true`, hiển thị nhãn SAMPLE). Bước tiếp theo là thay bằng LLM, vẫn giữ đúng output contract và bước duyệt (P-05).
- **Chưa nạp:** sheet FAB (vật tư, định mức), minimap. Bóc tách email bằng AI (D-03) chưa chạy: cần `ANTHROPIC_API_KEY`.
- **Dữ liệu giả định** chỉ để PO đánh giá giao diện và chỉ số; luôn có nhãn; thay bằng file thật khi KLMAS gửi (`docs/assumptions.md`).
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
│   ├── ingest/            # một module cho mỗi loại nguồn (mailbox.py: .mbox/.pst, H-06; email_mhtml.py: Gmail .mhtml;
│   │                      #   shipping_schedule.py; buyer_order_status.py: PDF 오더 현황표)
│   ├── docmeta.py         # tài liệu kỹ thuật chỉ đọc tên (N-02)
│   ├── milestones.py      # mốc style + lô hàng từ tiêu đề email (N-03)
│   ├── mailallow.py       # danh sách người gửi không lọc (N-06)
│   ├── sim.py             # dữ liệu giả định schema sim (D-04)
│   ├── mgr_dashboard.py   # dữ liệu + trang dashboard quản lý (D-06)
│   ├── checks.py          # golden tests (ghim theo bản file)
│   └── dashboard.py       # xuất mart → data/<mùa>.json + HTML; serve
├── sql/                   # 00_raw (DDL) · 10–17 core · 20–26 mart · 30 model · 32 coverage · 40 mgr
├── docs/                  # data_model.md, assumptions.md, metrics.md
├── Dockerfile             # + docker-compose.yml, Makefile ở gốc repo (D-07)
├── templates/dashboard.html
└── samples/inbox/         # email mẫu (SAMPLE)
```
