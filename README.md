# KOPS — KLMAS Order & Production System

KOPS thay bộ file Excel rời mà KLMAS đang dùng để quản lý sản xuất và kiểm hàng may mặc cho các thương hiệu Hàn Quốc (bắt đầu với **CHALLENGER**). Nguyên tắc cốt lõi: **dữ liệu nhập một lần, mọi màn hình và báo cáo tự cập nhật, mọi con số dò ngược được về nguồn.**

- **Khách hàng:** KLMAS, công ty FDI tại Việt Nam (Hà Nội, TP.HCM). Không có nhà máy riêng, làm việc với khoảng 10 nhà máy gia công; ngoài ra kiểm hàng bên thứ ba cho khoảng 50 khách.
- **Bên phát triển:** ASTRA TECHNOLOGY.
- **Người dùng:** MR (merchandiser), QA nhà máy, kiểm viên, buyer, ban giám đốc KLMAS.
- **Trạng thái repo:** đã có phân tích, prototype UI và **MVP data warehouse** (`dw/`). Chưa có ứng dụng production.

Mọi người tham gia dự án, dù là người hay AI agent, đọc [`GUIDELINES.md`](GUIDELINES.md) trước khi bắt đầu việc.

---

## 1. Bài toán

| Hiện trạng ở KLMAS | Bằng chứng |
|---|---|
| ~300 style/mùa được nhập lặp lại vào 4–5 file Excel | Biên bản họp KOPS 15/10/2026 mục 2; ORDER RECAP, Shipment Status, Production Status, FAB, checklist vật tư |
| Tổng số sai, ba file cho ba con số | Production Status hiển thị 106.681 pcs, tính lại từ chi tiết là 62.357; chỉ 21/100 style khớp số đã xuất giữa các file |
| Trạng thái nằm trong màu ô, lịch sử nằm trong ghi chú tự do | `260512 MOVED FACT`, `260720 REDUCED 170P➜136P` |
| Thiếu vật tư phát hiện sát ngày sản xuất | Biên bản họp mục 2-3 (đặt lại mất thêm 1 tuần tàu) |
| Báo cáo kiểm viết giấy → nhập Excel → chèn ảnh → PDF, 70–100 báo cáo/ngày | Biên bản họp mục 2-2 |
| Buyer hỏi qua Kakao/email, MR tra cứu thủ công | Biên bản họp mục 2-3 |

Chi tiết: [`analys-docs/business_analysis.md`](analys-docs/business_analysis.md), [`analys-docs/data_quality_report.md`](analys-docs/data_quality_report.md).

## 2. Giải pháp tóm tắt

Hệ thống có bốn khối:

1. **Dữ liệu và dashboard:** import Excel/minimap thành style master; màn hình ORDER RECAP; Season Control Tower; buyer portal; export đúng mẫu Excel cũ; đối soát tự động.
2. **Flow sản xuất:** lịch T&A tính ngược từ RDD, báo cáo sản xuất ngày, cảnh báo trễ và thiếu vật tư, thay đổi từ buyer có cấu trúc và có duyệt, kế hoạch xuất hàng.
3. **Flow QC:** app kiểm hàng PWA chạy offline, AQL tự tính, PDF theo mẫu từng brand, AI phân công kiểm viên, vòng phản hồi lỗi cho nhà máy.
4. **Kho dữ liệu và AI:** lịch sử nhiều mùa, scorecard nhà máy và nhà cung cấp, kho tri thức, trợ lý soạn trả lời buyer (luôn có người duyệt).

Danh sách 23 ý tưởng, roadmap, ước lượng và rủi ro: [`analys-docs/roadmap.md`](analys-docs/roadmap.md).

## 3. Kiến trúc (đã chốt ở bước prototype)

| Lớp | Lựa chọn |
|---|---|
| Frontend | Next.js 15 (TypeScript), một app gồm landing (SSR, i18n vi/ko/en), app nội bộ và PWA kiểm hàng |
| Backend | FastAPI (Python 3.12): API, ingest Excel/minimap, sinh PDF, dịch vụ AI |
| Dữ liệu | PostgreSQL 16, một cụm, nhiều schema: `etl` → `raw` → `core` (vận hành) → `dw` (star schema, dbt chạy mỗi giờ) + view `mart`; pgvector cho kho tri thức |
| AI | Claude API: Sonnet cho trích xuất và soạn thảo, Haiku cho phân loại; model ID đặt trong config |
| Hạ tầng | Docker, AWS ap-southeast-1 (RDS, S3), Playwright cho PDF và e2e |

Lý do từng lựa chọn, sơ đồ thành phần và quy tắc nghiệp vụ đã cài: [`prototype/KOPS_prototype_architecture.md`](prototype/KOPS_prototype_architecture.md).

## 4. Cấu trúc repo

```
kops-mvp/
├── README.md              # tài liệu này
├── GUIDELINES.md          # quy tắc làm việc chung: vai trò, quy trình, quy tắc dữ liệu, định nghĩa xong
├── analys-docs/           # phân tích nghiệp vụ, dữ liệu, thiết kế DB/ETL, roadmap, backlog
├── prototype/             # prototype HTML (chuẩn UI và luồng màn hình), kiến trúc, dw_schema.sql
├── dw/                    # MVP data warehouse: nạp Excel + email + biên bản họp → DuckDB → dashboard
└── raw-docs/              # file gốc của KLMAS — KHÔNG commit (đã .gitignore), xin PO để lấy
```

### Tài liệu trong `analys-docs/`

| File | Nội dung | Dùng khi |
|---|---|---|
| `executive_summary.md` | Tóm tắt phát hiện và đề xuất CSDL | Cần bức tranh chung trong 5 phút |
| `business_analysis.md` | Vòng đời style, thực thể, quy trình, mâu thuẫn giữa các file | Viết spec, hiểu nghiệp vụ |
| `document_inventory.md` | Danh mục và cấu trúc từng file nguồn | Viết parser |
| `data_quality_report.md` | 26 lỗi dữ liệu, mã DQ-01…DQ-30 (một số mã bỏ trống) | Viết validation, đối soát |
| `database_design.md`, `er_diagram.md`, `schema.sql` | Thiết kế schema `core` | Migration, API |
| `source_to_target_mapping.csv` | 98 dòng mapping ô Excel → cột DB | Viết parser |
| `etl_pipeline.md` | Pipeline `raw → core`, kiểm template, xử lý lỗi | Viết ingest |
| `open_questions.md` | Câu hỏi nghiệp vụ còn mở, giả định đang dùng, dữ liệu cần xin KLMAS | Trước khi tự quyết một quy tắc |
| `review_inspection_production.md` | Rà soát báo cáo sản xuất ngày và bảng kiểm hàng: chất lượng dữ liệu, insight, đề xuất cho MVP | Mở rộng DW sang tiến độ may và QC |
| `roadmap.md` | Ý tưởng, giai đoạn P0–P5, ước lượng, rủi ro | Lập kế hoạch |
| `backlog.csv` | 50 task: vai trò phụ trách, phụ thuộc, giờ ước lượng, tiêu chí nghiệm thu | Nhận và giao việc |

### MVP data warehouse

`dw/` gom mọi nguồn (Excel, email, biên bản họp) về một kho duy nhất, rồi sinh dashboard offline gồm Control Tower, xuất hàng, nhà máy & NCC, thay đổi, đối soát và lineage. Cách chạy, các lớp dữ liệu và giới hạn hiện tại: [`dw/README.md`](dw/README.md).

```bash
cd dw && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m kops_dw && open build/dashboard.html
```

### Prototype

Mở `prototype/KOPS_prototype.html` trực tiếp bằng trình duyệt, không cần server. Muốn sửa thì sửa trong `prototype/src/` rồi build lại file HTML bằng `cd prototype && python3 build.py` (script dùng đường dẫn tương đối nên phải chạy trong thư mục `prototype/`).

## 5. Đọc gì trước

| Vai trò | Thứ tự đọc |
|---|---|
| Mọi người | README → `GUIDELINES.md` → `executive_summary.md` → mở prototype |
| BA / Product | `business_analysis.md` → `open_questions.md` → biên bản họp trong `raw-docs/` |
| Data / Database | `document_inventory.md` → `data_quality_report.md` → `database_design.md` → `schema.sql` → `etl_pipeline.md` → `source_to_target_mapping.csv` |
| Backend / Frontend | Kiến trúc trong `prototype/` → prototype HTML → `database_design.md` → task trong `backlog.csv` |
| AI | Kiến trúc (mục AI) → `GUIDELINES.md` §8 → `roadmap.md` (ý tưởng 7, 11, 17, 20) |
| QA | `GUIDELINES.md` §7 (golden numbers) → `data_quality_report.md` → tiêu chí nghiệm thu trong `backlog.csv` |

## 6. Bảo mật tài liệu

`raw-docs/`, dữ liệu trong `prototype/proto_data.json` và mọi số liệu trích từ đó là dữ liệu kinh doanh của KLMAS và buyer. Không đưa ra ngoài phạm vi dự án, không dán vào dịch vụ bên ngoài hay issue công khai. Xem `GUIDELINES.md` §8.
