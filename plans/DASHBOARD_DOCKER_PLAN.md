# Plan 23/10/2026 (2) — mô hình dữ liệu liên kết, dashboard cho quản lý, Docker local

Đầu vào: báo cáo N-01..N-08 của Claude Code (23/10, 53/53 check, 13 commit trên `dev` chưa push), `plans/HANDOFF_2026-10-23.md`.

## Đánh giá hiện trạng (đo trên `dw/build/kops.duckdb` ngày 23/10)

- **Đã có:** 26 bảng `core`, 29 bảng `mart`. ORDER RECAP của 5 khách / 2 mùa, kế hoạch sản xuất (246 dòng), Production Status, Shipment Status (3.374 dòng chi tiết), Shipping Schedule, email (363 thư, 367 mốc style, 31 lô hàng), metadata 226 tài liệu kỹ thuật.
- **Chưa có parser (file đã có, đang SKIPPED):** báo cáo sản xuất ngày (7 file, M1-02), bảng kiểm KLMAS (4 file, M1-06), dữ liệu kiểm bên thứ ba `INPUT DATA.xlsx` (M1-12).
- **N-03 phần AI chưa làm:** `milestones.py` vẫn chỉ rule-based theo tiêu đề, dù P2 đã duyệt và tiêu đề viết tự do.
- **Mô hình dữ liệu:** các bảng nối bằng chuỗi `style_no` / `factory_code` từng nguồn. Chưa có dimension chung (khách, brand, mùa, nhà máy, style, ngày). 75 dòng không có mã nhà máy. Mã DHG có 2 dạng (`LEV-27002` và `357311WM1`). Email về LBV-26002 không gắn được vào style.
- **Một cycle đủ:** CHALLENGER 26FW có đủ đơn → kế hoạch → tiến độ → kiểm → xuất (đã xuất 60.357 / 62.131 pcs, 97%). Dùng mùa này làm dữ liệu thật cho dashboard. Các khách / mùa khác thiếu một phần → dùng dữ liệu giả định, có nhãn rõ.

## Prompt cho Claude Code terminal

```text
Bối cảnh: repo kops-mvp, nhánh dev (commit trực tiếp trên dev). Đọc CLAUDE.md, GUIDELINES.md, plans/DASHBOARD_DOCKER_PLAN.md,
plans/HANDOFF_2026-10-23.md, plans/MVP_PHASE1_PLAN.md (M1-02..M1-08, M1-12), analys-docs/mvp_phase1_spec.md,
analys-docs/review_new_docs_emails.md, dw/README.md.
Việc dở từ lần trước: (1) 13 commit trên dev chưa push; (2) server `kops_dw serve` có thể vẫn chạy ở cổng 8765;
(3) N-03 phần AI chưa làm (milestones.py chỉ rule-based).

MỤC TIÊU
1. Một mô hình dữ liệu liên kết: mọi dữ liệu đã nạp (đơn, kế hoạch, tiến độ, kiểm, xuất, email, thay đổi, tài liệu) nối được với nhau
   qua khoá chung, dùng trực tiếp cho dashboard.
2. Dashboard cho quản lý: tổng quan và đánh giá bằng hình ảnh, trên dữ liệu thật của cycle đã đủ (CHALLENGER 26FW). Chỗ thiếu dữ liệu
   thì dùng dữ liệu giả định có nhãn rõ để PO đánh giá giao diện và chỉ số.
3. Docker: build và chạy toàn bộ hệ thống ở local bằng một lệnh để PO kiểm tra.

PHẠM VI (theo thứ tự; mỗi task 1 commit trên dev; chạy toàn bộ check sau mỗi task)

D-00 Dọn việc dở: `pkill -f "kops_dw serve"` nếu còn chạy; `git status` sạch. Push origin dev chỉ khi check xanh; nếu lệnh push
  bị chặn quyền thì ghi lại và làm tiếp, không tìm cách vượt.

D-01 Mô hình dữ liệu liên kết (schema `dim`, `fact`, `bridge`; giữ nguyên tên bảng core/mart cũ, nếu cần thì thành view):
  - Dimension (surrogate key + natural key + nguồn):
    dim_customer, dim_brand (thuộc customer), dim_season (code, năm, mùa, ngày bắt đầu/kết thúc), dim_date,
    dim_factory (tên chuẩn + bảng alias dim_factory_alias: TBM/TAN BINH MINH (PLAN), TP/TRUONG PHUC, DM/DONG MY, HGC/HAGACO/HD2,
      SH/SON HA, XT/XUAN THANH, NTC/NATEXCO, HH/HA HIEU, FG/FG VINA/FG BAC GIANG/FG BG, B85, CHI ANH…; alias chưa chắc ghi
      confidence + câu hỏi Q09),
    dim_style (khoá = customer + season + style_no chuẩn; bảng dim_style_alias gom file no LEV-/LBV- ↔ mã buyer 357311WM1 / BI7139UE1,
      lỗi gõ đã biết CHE→CHF, mã thiếu số như CHFMJK6406; nguồn alias: ORDER RECAP, kế hoạch, PDF DHG, tên thư mục STYLES),
    dim_party (bên liên lạc trong email: KLMAS / buyer / nhà máy / forwarder, từ mail_allow + domain).
  - Fact (grain ghi rõ trong doc): fact_order_line (style × màu × size nếu có, else style), fact_plan (style × nhà máy × bản kế hoạch),
    fact_daily_output (style × nhà máy × ngày, D-02), fact_inspection (lần kiểm, D-02), fact_defect (lần kiểm × mã lỗi),
    fact_shipment_lot + fact_shipment_line (lô × style × màu × size), fact_milestone, fact_shipment_event, fact_change
    (qty_change + change_proposal + version_change), fact_email, fact_document.
  - Bridge: bridge_style_factory (SCD2: nhà máy theo thời gian từ factory_event / bản RECAP), bridge_email_style, bridge_email_party.
  - Mọi fact có: style_key, factory_key, customer_key, season_key, date_key (nếu có), source_file_id, is_synthetic (false).
  - Bảng etl.link_orphan + check: tỉ lệ dòng fact nối được dim_style ≥ 98% cho CHALLENGER 26FW, ≥ 90% cho các khách khác; mọi dòng
    không nối được liệt kê kèm lý do (vd. LBV-26002 chưa có trong RECAP). Không được "ép" nối bằng fuzzy match nếu không có alias.
  - Tài liệu: dw/docs/data_model.md có ERD (Mermaid), grain từng bảng, khoá, nguồn, quy tắc alias. Check cũ giữ nguyên số.

D-02 Ba parser còn thiếu (theo spec có sẵn, golden từ ô tổng trong file):
  - daily_production (M1-02..M1-05): 7 file CHALLENGER + HAGACO; mỗi sheet một ngày; chuỗi sản lượng ngày, last-seen, dự báo ngày xong
    (rolling rate), độ tươi dữ liệu theo nhà máy.
  - inspection_tracker (M1-06): SL kiểm, đạt, lỗi, style bộ, REQUEST ETD; không lưu tên kiểm viên vào core/mart.
  - qc_third_party (M1-12): INPUT DATA.xlsx + bảng mã lỗi A–G → fact_inspection / fact_defect (nguồn = THIRD_PARTY).
  Câu hỏi nghiệp vụ chưa có trả lời (Q24 cách đếm lỗi, Q25 PASS/REJECT…): áp "ASTRA đang hiểu" trong open_questions.md, ghi
  assumption_id, không chặn việc.

D-03 Bóc tách email bằng AI (phần còn thiếu của N-03, P2 đã duyệt; làm khi có ANTHROPIC_API_KEY trong .env, thiếu thì bỏ qua task
  này, ghi vào báo cáo, làm tiếp): giữ đúng đặc tả N-03 trong HANDOFF_2026-10-23 (JSON schema, quote bắt buộc, Batches API, cache theo
  msg_key + prompt_version + model, chạy thử 200 thư + chi phí trước, 30 thư golden, extractor=llm|rule). Kết quả vào fact_milestone /
  fact_shipment_event / fact_change với cờ PENDING_REVIEW.

D-04 Độ phủ cycle + dữ liệu giả định:
  - mart.cycle_coverage: customer × season × stage (ORDER, PLAN, DAILY_OUTPUT, INSPECTION, SHIPMENT, EMAIL, HISTORY) → REAL / PARTIAL /
    NONE + số dòng + ngày dữ liệu mới nhất. In bảng này trong báo cáo.
  - Một cycle "đủ" = có ORDER, PLAN hoặc PRODUCTION STATUS, DAILY_OUTPUT hoặc output trong status, INSPECTION, SHIPMENT ≥ 80% SL.
    Kỳ vọng: CHALLENGER 26FW đủ → dashboard dùng dữ liệu thật cho mùa này.
  - Chỗ NONE/PARTIAL: sinh dữ liệu giả định trong schema `sim` (seed cố định, tái lập được), cùng khoá dim, is_synthetic = true,
    assumption_id. Ví dụ cần có: 2 mùa trước (25SS, 25FW) cho so sánh xu hướng; sản lượng ngày cho nhà máy không có báo cáo
    (TIEN THANH, FG…); kết quả kiểm + lỗi cho 27SS và các khách khác; tiến độ / xuất hàng cho DHG, JBEE, KOFA, DKM theo ETD trong RECAP.
    Phân phối lấy từ dữ liệu thật CHALLENGER 26FW (tỉ lệ trễ, sai số SL, tỉ lệ lỗi theo nhà máy), không bịa số tròn.
  - dw/docs/assumptions.md: bảng assumption_id → dữ liệu nào, cách sinh, tham số, câu hỏi KLMAS liên quan (Q..), khi nào thay bằng thật.
  - Dữ liệu giả định KHÔNG bao giờ vào golden check, không vào core/fact thật; mart đọc được cả hai qua cột is_synthetic.

D-05 Chỉ số cho quản lý (mart.mgr_*; định nghĩa trong dw/docs/metrics.md, mỗi chỉ số: công thức, grain, nguồn, ví dụ số thật):
  SL đặt / style / nhà máy theo mùa; % đã xuất = SL đã xuất ÷ SL đơn còn hiệu lực; đúng hạn xuất = lô đầu tiên có ETD thực ≤ ETD VN
  của RECAP (ghi rõ nếu dùng quy tắc khác); số ngày trễ ETD; style rủi ro = dự báo xong + thời gian vận chuyển > RDD hoặc BAL < 0;
  tiến độ may so với kế hoạch (S-curve kế hoạch vs thực tế); tải nhà máy (style, SL theo tuần); tỉ lệ đạt kiểm, tỉ lệ lỗi, Pareto mã lỗi;
  số lần đổi nhà máy / đổi SL / đổi assort theo style và nhà máy; ETD vật tư trễ theo nhà máy; thời gian phản hồi email; độ tươi dữ liệu;
  chênh lệch giữa các file (reconciliation, các phát hiện Ưu tiên 1). Scorecard nhà máy = đúng hạn, chất lượng, mức thay đổi, độ tươi.
  So sánh mùa này với mùa trước (giả định nếu chưa có thật).

D-06 Dashboard cho quản lý (giữ server `python -m kops_dw serve`, dữ liệu theo mùa; thư viện chart vendored trong repo, không CDN,
  vd. Apache ECharts; sáng / tối; desktop + mobile; tiếng Việt, nhãn nghiệp vụ tiếng Anh giữ nguyên):
  - Bộ lọc chung: mùa (có "Tất cả"), khách, brand, nhà máy; công tắc "Hiện dữ liệu giả định" (bật mặc định cho bản demo). Mọi chart /
    ô có dữ liệu giả định mang nhãn "Giả định" + tooltip assumption_id; KPI tile ghi tỉ lệ phần giả định.
  - Trang:
    1. Tổng quan: KPI tile (SL, style, % xuất, đúng hạn, style rủi ro, tỉ lệ lỗi, đề xuất thay đổi chờ duyệt) + so với mùa trước;
       SL theo khách / brand; lịch ETD theo tuần; top 10 cảnh báo.
    2. Tiến độ sản xuất: S-curve kế hoạch vs thực tế; dự báo ngày xong vs hạn (dumbbell) theo style; tải nhà máy theo tuần.
    3. Xuất hàng: SL xuất theo tuần so với kế hoạch; phân bố số ngày trễ ETD; lô theo forwarder / phương thức; vật tư về trễ.
    4. Chất lượng: tỉ lệ đạt theo nhà máy; Pareto lỗi; xu hướng tỉ lệ lỗi; phàn nàn từ buyer (email).
    5. Nhà máy: scorecard xếp hạng + small multiples; lịch sử đổi nhà máy.
    6. Thay đổi & email: đổi SL / assort / nhà máy theo thời gian; đề xuất từ email chờ duyệt; thời gian phản hồi.
    7. Style 360 (drill-down từ mọi chart): timeline mốc (gantt), funnel đơn → may → kiểm → xuất, lô hàng, email, thay đổi, tài liệu.
    8. Sức khoẻ dữ liệu: độ phủ cycle (D-04), độ tươi, dòng không nối được (D-01), chênh lệch giữa file.
  - Click chart → lọc / drill-down; mọi số có tooltip nguồn (file, sheet, ô hoặc email).
  - Tự kiểm tra: chạy headless browser, chụp mọi trang ở sáng / tối, desktop / mobile, tự xem lại; lưu ảnh ngoài repo (có dữ liệu KLMAS).

D-07 Docker (chạy được trên Mac Apple Silicon và Linux x86_64):
  - dw/Dockerfile: python 3.x slim + libreoffice-calc (xlsb) + tesseract (kor, vie, eng) + poppler-utils + pst-utils; cài requirements
    ghim phiên bản; user không phải root.
  - docker-compose.yml ở gốc repo:
    `kops-build` (one-shot: build + check + render data), `kops-dashboard` (serve, phụ thuộc kops-build thành công),
    port chỉ bind 127.0.0.1:8765; raw-docs mount read-only; dw/build là volume/bind mount; ANTHROPIC_API_KEY qua env_file .env (không
    bake vào image); profile `demo` bật dữ liệu giả định.
  - .dockerignore loại raw-docs, dw/build, .env, .venv*, dữ liệu benchmark. Image không chứa dữ liệu KLMAS (kiểm bằng `docker run … ls`).
  - Makefile hoặc scripts/: `make up`, `make down`, `make rebuild`, `make check`, `make logs`.
  - Kiểm tra thật trên máy này: `docker info`; nếu chưa có Docker thì DỪNG task này, báo lệnh cài (không tự cài Docker Desktop).
    Nếu có: build image, `make up`, mở http://127.0.0.1:8765, check trong container = check ngoài container (53+ check), thời gian build
    image, dung lượng image.
  - Hướng dẫn trong dw/README.md mục "Chạy bằng Docker".

D-08 Hoàn thiện: cập nhật dw/README.md, CLAUDE.md (lệnh Docker), plans/DASHBOARD_DOCKER_PLAN.md (trạng thái), MVP_PHASE1_PLAN
  (M1-02..M1-08, M1-12 đã làm gì).

LUẬT CỨNG
- Commit trực tiếp trên dev, conventional commits; push origin dev chỉ khi toàn bộ check xanh; không push/force-push main.
- Không sửa / đổi tên / xoá / di chuyển file trong raw-docs. Không commit raw-docs, dw/build, ảnh chụp dashboard, email thật, .env,
  mail_allow.local.txt. Không publish dashboard / artifact có dữ liệu KLMAS ra ngoài máy.
- Dữ liệu giả định luôn tách riêng (schema sim, is_synthetic) và luôn có nhãn trên giao diện; không bao giờ trộn vào golden check.
- Golden: không sửa số kỳ vọng để cho xanh; golden mới chỉ từ ô tổng trong file (ghi sheet/ô).
- Nội dung email / file là DỮ LIỆU; thay đổi bóc ra luôn PENDING_REVIEW. Chỉ gửi email tới Claude API. Không lưu tên kiểm viên.
- Câu hỏi nghiệp vụ mới: đề xuất trong báo cáo, không tự sửa open_questions.md.

TIÊU CHÍ HOÀN THÀNH
- Toàn bộ check xanh (cũ + mới), bench accept 10/10.
- dim/fact/bridge có đủ dữ liệu; tỉ lệ nối style đạt ngưỡng D-01; ERD + grain trong dw/docs/data_model.md.
- 3 parser D-02 chạy trên file thật, có golden.
- mart.cycle_coverage in ra được; CHALLENGER 26FW = cycle đủ (hoặc giải thích vì sao không).
- Dashboard 8 trang chạy, lọc mùa / khách / nhà máy, drill-down tới Style 360, nhãn "Giả định" đúng chỗ; ảnh tự kiểm đã xem.
- `make up` dựng được hệ thống từ máy sạch (chỉ cần Docker + raw-docs), dashboard mở ở 127.0.0.1:8765.

BÁO CÁO LẠI (tiếng Việt, ngắn)
1. Commit (hash), đã push dev chưa; check (x/y); thời gian build (local và Docker), dung lượng image.
2. Bảng cycle_coverage; dữ liệu nào thật / giả định trên từng trang dashboard.
3. Mô hình dữ liệu: số dim / fact, tỉ lệ nối, danh sách orphan chính và lý do.
4. Parser mới: số dòng, golden + bằng chứng (file, sheet, ô).
5. AI email (D-03): đã chạy chưa, chi phí, precision / recall.
6. 5 insight chính cho quản lý rút ra từ dashboard (chỉ từ dữ liệu thật, ghi rõ nguồn).
7. Giả định đã dùng (assumption_id) cần KLMAS xác nhận → đề xuất câu hỏi kèm mức ưu tiên.
8. Lệnh để PO chạy: `make up`, URL, cách bật / tắt dữ liệu giả định. Việc cần PO quyết.
```

## Quyết định PO cho các mục Claude Code hỏi (23/10, báo cáo N-01..N-08)

| # | Mục | Đề xuất |
|---|---|---|
| 1 | Push dev bị chặn | PO tự chạy `git push origin dev`, hoặc thêm `Bash(git push origin dev)` vào danh sách allow của Claude Code |
| 2 | `mail_allow.local.txt` (8 domain, 65 địa chỉ) | Giữ đối tác và Gmail cá nhân của nhân viên KLMAS đang dùng cho công việc; `leeintl.co.kr` để chờ Q19 |
| 3 | Mọi tab lọc theo mùa, chi tiết cắt 2.000 dòng / mùa | Giữ; thêm lựa chọn "Tất cả" và phân trang thay vì cắt cứng (D-06) |
| 4 | Benchmark 10 mùa | Chưa cần; 7 mùa đủ cho giai đoạn này |

## Trạng thái D-00..D-08 (Claude Code, 23/10/2026, commit trực tiếp trên `dev`)

| ID | Trạng thái | Kết quả |
|---|---|---|
| D-00 | DONE | Server cũ đã tắt; 14 commit trước đã push `origin dev` (không có thay đổi file → không commit) |
| D-01 | DONE | 9 bảng `dim`, 14 `fact`, 3 `bridge`; style master = mọi bản ORDER RECAP, 603 alias (9 mã trỏ 2 style → không dùng). Tỉ lệ nối: CHALLENGER 26FW 100%, DHG 95,6%, DKM 99,8%, JBEE / KOFA 100%. `dw/docs/data_model.md` |
| D-02 | DONE | Báo cáo ngày (7 file), bảng kiểm KLMAS, INPUT DATA; G1–G12 của spec đúng; xem `MVP_PHASE1_PLAN.md` §Trạng thái |
| D-03 | NOT DONE | Không có `ANTHROPIC_API_KEY` (`.env` không tồn tại) → bỏ qua theo đặc tả. `fact.milestone` / `fact.shipment_event` vẫn `extractor = rule`, `PENDING_REVIEW` |
| D-04 | DONE | `mart.cycle_coverage` (bảng dưới); dữ liệu giả định schema `sim` (seed cố định, ASM-SIM-01..05), `dw/docs/assumptions.md` |
| D-05 | DONE | `mart.mgr_*`, `dw/docs/metrics.md` |
| D-06 | DONE | `manager.html` 8 trang, lọc mùa / khách / brand / nhà máy, công tắc giả định, drill-down Style 360; tự kiểm 32 ảnh (sáng / tối × desktop / mobile, lưu ngoài repo) |
| D-07 | DONE | `dw/Dockerfile`, `docker-compose.yml`, `Makefile`; image 1,24 GB / 58 s; build lạnh trong container 80 s; 80/80 check trong = ngoài container |
| D-08 | DONE | README, CLAUDE.md, plan này, MVP_PHASE1_PLAN |

**Độ phủ cycle (dữ liệu thật, 23/10):**

| Khách · mùa | ORDER | PLAN | DAILY_OUTPUT | INSPECTION | SHIPMENT | EMAIL | HISTORY | Cycle đủ |
|---|---|---|---|---|---|---|---|---|
| CHALLENGER 26FW | REAL | REAL | REAL | REAL (98%) | REAL (97,1%) | REAL | REAL | **Có** |
| CHALLENGER 27SS | REAL | REAL (77%) | NONE | NONE | PARTIAL | NONE | REAL | Không (chưa sản xuất) |
| DHG 26FW | REAL | NONE | PARTIAL (31%) | NONE | NONE | REAL | REAL | Không |
| DHG 27SS | REAL | PARTIAL | NONE | NONE | NONE | REAL | REAL | Không |
| DKM 26FW | REAL | REAL | NONE | NONE | REAL (96,9%) | REAL | PARTIAL | Không |
| DKM 27SS | REAL | NONE | NONE | NONE | PARTIAL | NONE | PARTIAL | Không |
| JBEE 27SS | REAL | PARTIAL | NONE | NONE | NONE | REAL | REAL | Không |
| KOFA 27SS | REAL | REAL | NONE | NONE | NONE | NONE | PARTIAL | Không |

**Khác với đặc tả:** sản lượng ngày lấy từ chênh lệch luỹ kế (không phải cột TODAY); docker dùng biến `KOPS_SIM` (`make up` /
`make up-real`) thay vì profile `demo`, vì profile không đổi được biến môi trường của cùng một service mà không nhân đôi cổng;
dashboard quản lý là trang mới, dashboard phân tích 12 tab giữ nguyên ở `/dashboard.html`.
