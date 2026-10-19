# KOPS × Buzz — Ý tưởng, kế hoạch thực thi và ước lượng

Đầu vào: `raw-docs/` (ORDER RECAP 26FW/27SS, Shipment Status, Production Status, hồ sơ năng lực, biên bản họp KOPS 15/10), `analys-docs/` (phân tích, schema `core`, ETL), `prototype/` (KOPS_prototype.html, `dw_schema.sql`).
File đi kèm: `backlog.csv` (50 task, có agent phụ trách, phụ thuộc, giờ, tiêu chí nghiệm thu), `agents/` (4 agent mới), `kickoff_prompt.md` (lệnh giao cho Planner).

---

## 1. Vấn đề cần giải (từ tài liệu)

| Hiện trạng | Bằng chứng |
|---|---|
| ~300 style/mùa nhập lặp lại vào 4–5 file Excel | Biên bản họp mục 2; ORDER RECAP, Shipment Status, Production Status, FAB, checklist vật tư |
| Tổng số sai, ba file ba con số | Production Status báo 106.681 pcs, thực tế 62.357; chỉ 21/100 style khớp số đã xuất giữa các file |
| Trạng thái nằm trong màu ô, lịch sử nằm trong ghi chú tự do | "260512 MOVED FACT", "260720 REDUCED 170P➜136P" |
| Thiếu vật tư phát hiện sát ngày sản xuất | Biên bản họp mục 2-3 (đặt lại mất thêm 1 tuần tàu) |
| Báo cáo kiểm viết giấy → nhập Excel → chèn ảnh → PDF, 70–100 báo cáo/ngày | Biên bản họp mục 2-2 |
| Buyer hỏi qua Kakao/email, MR tra tay | Biên bản họp mục 2-3 |

## 2. Ý tưởng

### A. Dữ liệu: một nguồn, nhiều dashboard
1. **Nhập một lần, mọi báo cáo tự cập nhật.** Excel chỉ còn là đầu vào (import) và đầu ra (export đúng mẫu cũ cho buyer).
2. **Season Control Tower**: một màn hình cho cả mùa, gồm số style theo trạng thái, đặt/may/kiểm/xuất theo nhà máy, top 10 style nguy cơ trễ, vật tư chưa về.
3. **Buyer portal**: buyer đăng nhập xem tiến độ, assortment màu × size, lô xuất, báo cáo kiểm. Biên bản ghi buyer thích dashboard hơn chatbot.
4. **Bảng chấm điểm đối tác**: nhà máy (đúng hạn, xuất đủ, return %, số lần bị chuyển đơn), nhà cung cấp vải (giao đúng hạn, thiếu yard).
5. **Đối soát tự động**: mỗi lần import đều so "số trong file" với "số tính từ chi tiết" và đưa chênh lệch vào hộp việc của MR.
6. **Kho dữ liệu lịch sử**: lưu các mùa cũ, mẫu mã, lịch sử đổi nhà máy (SCD2), làm nền cho báo giá và chọn nhà máy mùa sau.

### B. Flow sản xuất
7. **AI đọc minimap/order list** (mỗi brand một định dạng, có loại ảnh) → bản nháp style master → MR duyệt các dòng AI không chắc.
8. **Lịch T&A tính ngược từ RDD**: template mốc theo brand (REF → FPP → INLINE → TOP → SHIPPING, mốc chốt vật tư), cảnh báo khi trễ mốc.
9. **Báo cáo sản xuất ngày**: nhà máy nhập web form, hoặc gửi ảnh/Excel qua Zalo cho AI đọc. Hệ thống tự tính ngày xong dự kiến (SL còn lại ÷ SL ngày + Chủ nhật + 5 ngày) và báo khi dưới kế hoạch.
10. **Checklist vật tư và cảnh báo thiếu sớm**: định mức × SL = nhu cầu, so với yard đã về; đặt deadline chốt vật tư trước ngày cắt.
11. **Thay đổi từ buyer có cấu trúc**: AI đọc email/Kakao → đề xuất thay đổi (qty, màu, ETD) → MR duyệt → cập nhật mọi màn hình và ghi lịch sử.
12. **Kế hoạch xuất hàng**: chia tối đa 4 lô, cảnh báo chi phí khi chuyển AIR, nhập packing list, soạn email booking.
13. **Thẻ vật tư 3 bản** (buyer / KLMAS / nhà máy) sinh tự động từ dữ liệu FAB.

### C. Quản lý
14. **Hộp việc hôm nay cho từng MR**: mốc sắp trễ, thay đổi chờ duyệt, câu hỏi buyer chờ trả lời, vật tư thiếu.
15. **Phân quyền và nhật ký**: ai sửa gì, khi nào; buyer chỉ thấy brand của mình.
16. **Báo cáo tuần tự động** cho TGĐ (PDF/email): tiến độ mùa, rủi ro, hiệu suất nhà máy và kiểm viên.
17. **Trợ lý AI trả lời buyer**: bản nháp dùng dữ liệu thật, MR duyệt rồi gửi; kho Q&A học từ email cũ.

### D. Flow QC
18. **App kiểm hàng trên điện thoại (PWA, chạy offline)**: AQL tự tính, đếm lỗi theo mã, chụp ảnh bắt buộc, PDF theo mẫu từng brand. Tách menu đơn KLMAS và khách kiểm hàng bên thứ ba.
19. **Tiếp nhận yêu cầu kiểm**: đơn KLMAS sinh tự động khi may xong; khoảng 50 khách bên thứ ba gửi qua portal/email.
20. **AI phân công kiểm viên ngày mai**: kiểm viên chuyên trách nhà máy, khu vực, mặt hàng, ghép chuyến.
21. **Vòng phản hồi lỗi**: ảnh lỗi hằng ngày gửi nhà máy, theo dõi CAPA; kiểm inline nối với kiểm cuối.
22. **Trách nhiệm kiểm viên**: kiểm lại mẫu ngẫu nhiên, thống kê lỗi bị sót, đề xuất đào tạo lại.
23. **Dashboard QC**: tỷ lệ đạt, DHU, return % theo nhà máy, brand, kiểm viên.

## 3. Kiến trúc (đã chốt ở prototype)
Next.js + PWA · FastAPI (Python) · PostgreSQL 16 với các schema `raw`/`core`/`dw` · dbt · Claude API (Sonnet cho soạn thảo và trích xuất, Haiku cho phân loại) + pgvector · S3 · AWS Singapore. Chi tiết: `prototype/KOPS_prototype_architecture.md`.

## 4. Đội agent

### Agent hiện có và vai trò trong dự án

| Agent (model) | Vai trò trong KOPS |
|---|---|
| Planner (Opus) | Chia task theo `backlog.csv`, giữ thứ tự phụ thuộc, mở các luồng song song |
| Reviewer (Opus) | Review mọi PR; đối chiếu tiêu chí nghiệm thu và `analys-docs` |
| Researcher (Sonnet) | Tra cứu kỹ thuật: OR-Tools, PWA offline, Kakao/Zalo API, AQL ISO 2859-1 |
| Developer (Sonnet) | Backend FastAPI, nghiệp vụ, tích hợp (email, Zalo, PDF) |
| QA (Sonnet) | Test đơn vị/tích hợp, Playwright e2e, bộ test "golden" từ file Excel thật |
| DevOps (Sonnet) | Repo, CI/CD, Docker, AWS, backup |
| Database Engineer (Sonnet) | Migration schema `core`, index, RLS, hiệu năng |
| Security Gate (Sonnet) | Chặn merge nếu lỗi bảo mật; RBAC, dữ liệu buyer, secrets |
| Release Manager (Sonnet) | Phiên bản, changelog, release notes song ngữ, rollback |

### Đề xuất thêm 4 agent (định nghĩa trong `agents/`)

| Agent mới | Model | Lý do |
|---|---|---|
| **Domain Analyst (BA may mặc, VI/KO)** | Opus | Biến biên bản họp và Excel thành user story và tiêu chí nghiệm thu; hiểu FPP, assortment, định mức, AQL; viết và dịch tiếng Hàn. Thiếu agent này, Developer sẽ đoán nghiệp vụ |
| **Data Engineer** | Sonnet | Parser Excel/xlsb (block 4 dòng, lưới block, màu ô), pipeline `raw → core`, dbt cho `dw`, đối soát |
| **Frontend Engineer** | Sonnet | Next.js, dashboard, PWA offline/camera, i18n VI/KO/EN. Tách khỏi Developer để chạy song song |
| **AI Engineer** | Sonnet | Prompt + tool use cho minimap, email, trả lời buyer; bộ eval có số đo; bộ tối ưu phân công kiểm viên |

Tổng cộng 13 agent. Developer và Frontend có thể mở 2 thread song song khi Planner cho phép.

### Việc agent không làm được, cần người
- Lấy dữ liệu thật từ KLMAS: file mùa cũ, mẫu báo cáo kiểm theo brand, minimap của 2 brand khác, quyền đọc Gmail.
- Tài khoản AWS, Zalo OA, Kakao Business, Claude API key.
- UAT với chị Lee Min Ji và kiểm viên; quyết định nghiệp vụ trong `analys-docs/open_questions.md`.
- Duyệt release production.

## 5. Kế hoạch theo giai đoạn

| Giai đoạn | Mục tiêu | Task | Cổng nghiệm thu (người duyệt) |
|---|---|---|---|
| **P0 Nền tảng** | Repo, CI, schema `core`, auth/RBAC, master data, staging | F-01…F-07 | Staging chạy; seed master data được KLMAS xác nhận |
| **P1 MVP-1: Dữ liệu & dashboard** | Import 4 loại Excel + AI minimap → style master; màn ORDER RECAP; Control Tower; buyer portal; export đúng mẫu cũ; đối soát | D-01…D-12 | Import 26FW thật cho kết quả 110 style / 62.357 pcs; KLMAS duyệt export so với file gốc |
| **P2 Flow sản xuất** | T&A ngược từ RDD, báo cáo sản xuất ngày, cảnh báo, checklist vật tư, thay đổi từ email, xuất hàng, booking, thẻ vật tư | P-01…P-09 | Chạy 1 tuần dữ liệu thật; MR xác nhận cảnh báo đúng |
| **P3 Flow QC** | PWA kiểm hàng, PDF theo brand, tiếp nhận yêu cầu, AI phân công, phản hồi lỗi, dashboard QC, portal khách | Q-01…Q-09 | 3 kiểm viên dùng thử 1 tuần; PDF giống mẫu brand |
| **P4 Kho dữ liệu & AI** | `dw` + dbt, scorecard, nạp mùa cũ, kho tri thức, trợ lý trả lời buyer, báo cáo tuần, landing | A-01…A-07 | Đúng số với 26FW; TGĐ duyệt báo cáo tuần |
| **P5 Go-live** | Bảo mật, hiệu năng, e2e, chạy song song với Excel, đào tạo, release | H-01…H-06 | 2–4 tuần song song, chênh lệch < 0,5%; TGĐ ký go-live |

P2 và P3 chạy song song sau P1 (QC chỉ cần `core` + auth). P4 bắt đầu khi P1 xong, chạy song song với P2/P3.

```
Tuần:       1    2    3    4    5    6    7    8    9   10   11   12
P0          ███
P1               ██████████
P2                         ███████████
P3                         ███████████
P4                              ███████████
P5                                        ██████  ████████████ (chạy song song Excel)
Demo KLMAS:         ▲MVP-1         ▲SX          ▲QC          ▲Go-live
```

## 6. Ước lượng (giả sử không giới hạn token)

Đơn vị **agent-giờ** là thời gian một thread agent làm việc thật (viết code, chạy test, sửa) cho task đó; chưa gồm review. Chi tiết từng task nằm trong `backlog.csv`.

| Giai đoạn | Task | Agent-giờ (build) | + Review/Plan 25% | Giờ người (bạn) | Giờ KLMAS | Lịch (song song) |
|---|---|---|---|---|---|---|
| P0 Nền tảng | 7 | 56 | 70 | 6 | 2 | 0,5–1 tuần |
| P1 MVP-1 | 12 | 166 | 208 | 18 | 8 | 2–2,5 tuần |
| P2 Sản xuất | 9 | 136 | 170 | 14 | 6 | 2,5–3 tuần |
| P3 QC | 9 | 136 | 170 | 14 | 8 | 2,5–3 tuần (song song P2) |
| P4 DW & AI | 7 | 92 | 115 | 8 | 4 | 2 tuần (song song) |
| P5 Go-live | 6 | 62 | 78 | 16 | 20 | 1 tuần + 2–4 tuần chạy song song |
| **Tổng** | **50** | **648** | **≈ 810** | **≈ 76** | **≈ 48** | **≈ 10–12 tuần đến go-live** |

Giờ người theo task trong `backlog.csv` là 69 giờ; bảng trên cộng thêm khoảng 7 giờ cho điều phối và gửi demo hằng tuần.

Cách tính lịch:
- 3 luồng song song (Data/Backend, Frontend, AI/QC), mỗi luồng ~10 agent-giờ hữu ích mỗi ngày. Agent không cần nghỉ, nhưng mỗi ngày bị chặn ở các cổng review và các câu hỏi chờ người trả lời.
- 810 ÷ 30 ≈ 27 ngày làm việc, tức khoảng 5,5 tuần nếu chỉ tính build. Phần còn lại của 10–12 tuần là chờ dữ liệu và phản hồi từ KLMAS, UAT, và 2–4 tuần chạy song song với Excel.
- **Không giới hạn token không làm lịch ngắn lại tuyến tính.** Điểm nghẽn là phản hồi từ KLMAS (mỗi vòng 2–5 ngày) và thời gian review của bạn (~1–1,5 giờ/ngày). Muốn nhanh hơn thì có hai cách: giao Reviewer (Opus) tự merge các task rủi ro thấp, và gom câu hỏi gửi KLMAS mỗi tuần một lần qua nhóm Zalo.
- So sánh: biên bản họp ghi dự án loại này trước đây mất 6 tháng trở lên với đội người. Phương án agent rút còn khoảng 3 tháng, với khoảng 76 giờ công của bạn.

Độ tin cậy: P0/P1 ±20% (đã có schema, parser prototype, dữ liệu thật). P2/P3 ±35% (mẫu báo cáo kiểm và báo cáo sản xuất ngày chưa có file thật). Phần tích hợp Kakao/Gmail phụ thuộc quyền truy cập, có thể bị chặn hoàn toàn.

## 7. Rủi ro và cách giảm

| Rủi ro | Giảm |
|---|---|
| Agent hiểu sai nghiệp vụ may mặc | Domain Analyst viết tiêu chí nghiệm thu trước khi code; Reviewer đối chiếu `analys-docs`; bộ golden test từ 6 file thật |
| Template Excel thay đổi | Parser kiểm dấu hiệu template, báo `TEMPLATE_CHANGED` thay vì nạp sai (theo `etl_pipeline.md`) |
| AI trích xuất sai số lượng | Luôn qua bước MR duyệt; eval ≥ 98% trên bộ mẫu trước khi bật |
| Lộ dữ liệu buyer | Security Gate bắt buộc trên mọi PR có auth/data; RLS theo brand; không đưa dữ liệu thật vào prompt log |
| Chờ dữ liệu KLMAS | P1 dùng 26FW/27SS đã có; danh sách xin dữ liệu gửi ngay tuần 1 (xem `kickoff_prompt.md`) |
| Câu hỏi nghiệp vụ chưa trả lời (`open_questions.md`) | Giữ cấu hình được (ví dụ RDD−12, AQL, định nghĩa return %); không hard-code |

## 8. Cách chạy với Buzz
1. Thêm 4 agent trong `agents/` vào Buzz. File viết dạng prompt vai trò; chỉnh lại theo định dạng config Buzz của bạn.
2. Tạo project Buzz `kops` (repo mới, ví dụ `~/.buzz/REPOS/kops`) và mount `klmas-docs` làm tài liệu chỉ đọc.
3. Giao `kickoff_prompt.md` cho Planner. Planner nạp `backlog.csv` và bắt đầu P0. Nếu task KOPS đến từ relay Astra, chạy qua agent bridge sang relay local.
4. Mỗi ngày bạn duyệt các PR ở cổng nghiệm thu và trả lời câu hỏi agent; mỗi tuần gửi KLMAS một gói câu hỏi kèm bản demo.
