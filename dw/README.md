# KOPS Data Warehouse — MVP

Kho dữ liệu là **nguồn sự thật duy nhất** của KOPS. Excel (ORDER RECAP, Shipment Status, Production Status), email của buyer và biên bản họp đều được nạp vào cùng một kho. Dashboard và các tính năng sau này (cảnh báo, buyer portal, trợ lý AI) chỉ đọc từ kho này, không đọc trực tiếp file Excel.

```
raw-docs/*.xlsx|xlsb|docx  ┐
raw-docs/inbox/*.eml       ├─► etl + raw ─► stg ─► core ─► mart ─► build/dashboard.html
dw/samples/inbox/*.eml     ┘   (nguyên văn,  (sự kiện   (mô hình  (bảng cho
                                 lineage)     từ ghi chú) chuẩn)    dashboard)
```

## Chạy

Cần Python 3.10+ và LibreOffice. LibreOffice dùng để đọc màu ô (trạng thái style) trong file `.xlsb`; trên macOS cài bằng `brew install --cask libreoffice`.

```bash
cd dw
make            # tạo .venv, build kho, chạy test, sinh dashboard
make open       # mở build/dashboard.html
```

Các lệnh lẻ: `make build`, `make test`, `make dashboard`, `make clean`.

Kết quả nằm trong `dw/build/` (đã `.gitignore`):
- `kops.duckdb`: kho dữ liệu. Mở bằng `duckdb build/kops.duckdb` hoặc bất kỳ công cụ BI nào đọc được DuckDB.
- `dashboard.html`: một file HTML chạy offline, dữ liệu nhúng sẵn.
- `cache/`: bản `.xlsx` chuyển từ `.xlsb`, đặt tên theo sha256, tái dùng giữa các lần build.

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
| Email: hộp thư (Gmail, Outlook 365, Naver, Hiworks…) | `KOPS_IMAP_PASSWORD=… .venv/bin/python -m kops_dw fetch-imap --host imap.gmail.com --user … --folder KLMAS --since 2026-01-01` (chỉ đọc, không đánh dấu đã đọc). Hoặc agent dùng connector Gmail/Drive lưu `.eml`/PDF vào `raw-docs/inbox/gmail/` |
| File đính kèm của email `.eml` | `.venv/bin/python -m kops_dw attachments` → `raw-docs/EMAIL_ATTACHMENTS/<yyyy-mm>/`, build sau sẽ nạp như file thường (trùng nội dung thì bỏ qua) |
| Biên bản họp | Thả `.docx` vào `raw-docs/MEETINGS/` |
| Báo cáo sản xuất ngày, bảng kiểm, dữ liệu kiểm bên thứ ba | Đã được nhận diện và đăng ký (trạng thái SKIPPED: parser nằm trong kế hoạch Phase 1, `plans/MVP_PHASE1_PLAN.md`) |

Biến môi trường: `KOPS_RAW_DOCS` (thư mục nguồn), `KOPS_INBOX`, `KOPS_BUILD`, `KOPS_SOFFICE` (đường dẫn `soffice` nếu không nằm trong PATH).

## Các lớp dữ liệu

| Schema | Nội dung | Ai ghi |
|---|---|---|
| `etl` | `source_file` (mỗi file: sha256, loại, mùa, ngày báo cáo, bản hiện hành, số dòng) và `data_issue` (mọi bất thường, kèm vị trí ô) | Python |
| `raw` | Dữ liệu gần nguyên văn theo từng template, **mọi phiên bản**: `order_recap_style/color`, `order_line_ext` (khách khác), `production_plan`, `shipment_block/cell`, `production_status(_total)`, `doc_block`, `email` (mỗi thư một dòng, `msg_key` nhận ra cùng một thư ở nhiều file) | Python parser |
| `stg` | Sự kiện trích từ text tự do: `qty_change`, `factory_event`, `email_change`, `requirement`, `action_item`, `decision`; cùng dữ liệu tham chiếu từ `config.py` | Python |
| `core` | Mô hình chuẩn, chỉ lấy bản hiện hành: `style_order`, `order_color`, `shipment_detail`, `production_snapshot`, `meeting`, `requirement`… (`10_core`); `order_portfolio` (mọi khách), `production_plan`, `style_dictionary` (`11_core_customers`); `email` (đã gộp trùng), `email_thread`, `email_mention`, `email_reply`, `change_proposal`, `proposal_file_status` (`12_core_email`) | `sql/1x_*.sql` |
| `mart` | Bảng cho dashboard: `style_360`, `season_kpi`, `factory_kpi`, `supplier_styles`, `shipment_*`, `assortment`, `reconciliation`, `change_log`, `source_lineage` (`20_mart`); `customer_portfolio`, `factory_load_all`, `etd_weekly_all`, `plan_risk`, `file_version`, `version_change`, `email_*` (`25_mart_ext`) | `sql/2x_*.sql` |

Mỗi lần build là một lần **full rebuild**: xoá kho cũ và nạp lại toàn bộ file. Cách này đơn giản và idempotent. Khi chuyển sang app ghi trực tiếp, sẽ cần nạp tăng dần và lưu lịch sử (P1–P4).

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
│   ├── pipeline.py        # discover → registry → parse → load → chạy SQL
│   ├── excel.py           # đọc workbook, xlsb → xlsx qua LibreOffice, đọc màu ô
│   ├── ingest/            # một module cho mỗi loại nguồn
│   ├── checks.py          # golden tests
│   └── dashboard.py       # xuất mart → JSON → HTML
├── sql/                   # 00_raw (DDL) · 10_core · 15_issues · 20_mart
├── templates/dashboard.html
└── samples/inbox/         # email mẫu (SAMPLE)
```
