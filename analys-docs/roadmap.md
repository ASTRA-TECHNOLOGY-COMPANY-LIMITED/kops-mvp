# KOPS — Ý tưởng, roadmap và ước lượng

Căn cứ: file gốc trong `raw-docs/` (ORDER RECAP 26FW/27SS, Shipment Status, Production Status, hồ sơ năng lực, biên bản họp KOPS 15/10/2026), phân tích trong `analys-docs/`, prototype và kiến trúc trong `prototype/`.
Danh sách task chi tiết (vai trò phụ trách, phụ thuộc, giờ, tiêu chí nghiệm thu): `backlog.csv`.

---

## 1. Ý tưởng

### A. Dữ liệu: một nguồn, nhiều dashboard
1. **Nhập một lần, mọi báo cáo tự cập nhật.** Excel chỉ còn là đầu vào (import) và đầu ra (export đúng mẫu cũ cho buyer).
2. **Season Control Tower**: một màn hình cho cả mùa, gồm số style theo trạng thái, đặt/may/kiểm/xuất theo nhà máy, top 10 style nguy cơ trễ, vật tư chưa về.
3. **Buyer portal**: buyer đăng nhập xem tiến độ, assortment màu × size, lô xuất, báo cáo kiểm. Theo biên bản họp, buyer thích dashboard hơn chatbot.
4. **Bảng chấm điểm đối tác**: nhà máy (đúng hạn, xuất đủ, return %, số lần bị chuyển đơn), nhà cung cấp vải (giao đúng hạn, thiếu yard).
5. **Đối soát tự động**: mỗi lần import đều so "số trong file" với "số tính từ chi tiết" và đưa chênh lệch vào hộp việc của MR.
6. **Kho dữ liệu lịch sử**: lưu các mùa cũ, mẫu mã, lịch sử đổi nhà máy (SCD2), làm nền cho báo giá và chọn nhà máy mùa sau.

### B. Flow sản xuất
7. **AI đọc minimap/order list** (mỗi brand một định dạng, có loại là ảnh) → bản nháp style master → MR duyệt các dòng AI không chắc.
8. **Lịch T&A tính ngược từ RDD**: template mốc theo brand (REF → FPP → INLINE → TOP → SHIPPING, mốc chốt vật tư), cảnh báo khi trễ mốc.
9. **Báo cáo sản xuất ngày**: nhà máy nhập web form, hoặc gửi ảnh/Excel qua Zalo cho AI đọc. Hệ thống tự tính ngày xong dự kiến (SL còn lại ÷ SL ngày, bỏ Chủ nhật, + 5 ngày) và báo khi dưới kế hoạch.
10. **Checklist vật tư và cảnh báo thiếu sớm**: định mức × SL = nhu cầu, so với yard đã về; đặt deadline chốt vật tư trước ngày cắt.
11. **Thay đổi từ buyer có cấu trúc**: AI đọc email/Kakao → đề xuất thay đổi (qty, màu, ETD) → MR duyệt → cập nhật mọi màn hình và ghi lịch sử.
12. **Kế hoạch xuất hàng**: chia tối đa 4 lô, cảnh báo chi phí khi chuyển AIR, nhập packing list, soạn email booking.
13. **Thẻ vật tư 3 bản** (buyer / KLMAS / nhà máy) sinh tự động từ dữ liệu FAB.

### C. Quản lý
14. **Hộp việc hôm nay cho từng MR**: mốc sắp trễ, thay đổi chờ duyệt, câu hỏi buyer chờ trả lời, vật tư thiếu.
15. **Phân quyền và nhật ký**: ai sửa gì, khi nào; buyer chỉ thấy brand của mình.
16. **Báo cáo tuần tự động** cho ban giám đốc KLMAS (PDF/email): tiến độ mùa, rủi ro, hiệu suất nhà máy và kiểm viên.
17. **Trợ lý AI trả lời buyer**: bản nháp dùng dữ liệu thật, MR duyệt rồi gửi; kho Q&A học từ email cũ.

### D. Flow QC
18. **App kiểm hàng trên điện thoại (PWA, chạy offline)**: AQL tự tính, đếm lỗi theo mã, chụp ảnh bắt buộc, PDF theo mẫu từng brand. Tách menu đơn KLMAS và khách kiểm hàng bên thứ ba.
19. **Tiếp nhận yêu cầu kiểm**: đơn KLMAS sinh tự động khi may xong; khoảng 50 khách bên thứ ba gửi qua portal/email.
20. **AI phân công kiểm viên ngày mai**: kiểm viên chuyên trách nhà máy, khu vực, mặt hàng, ghép chuyến.
21. **Vòng phản hồi lỗi**: ảnh lỗi hằng ngày gửi nhà máy, theo dõi CAPA; kiểm inline nối với kiểm cuối.
22. **Trách nhiệm kiểm viên**: kiểm lại mẫu ngẫu nhiên, thống kê lỗi bị sót, đề xuất đào tạo lại.
23. **Dashboard QC**: tỷ lệ đạt, DHU, return % theo nhà máy, brand, kiểm viên.

## 2. Giai đoạn

> **Phase 1 hiện tại = MVP data warehouse** (`dw/`): một kho dữ liệu chung từ Excel, báo cáo sản xuất ngày, bảng kiểm, email và biên bản họp, kèm dashboard. Đặc tả ở `mvp_phase1_spec.md`, kế hoạch ở `plans/MVP_PHASE1_PLAN.md`, câu hỏi cần trả lời ở `open_questions.md` mục 1. Các giai đoạn P0–P5 dưới đây là lộ trình ứng dụng đầy đủ, bắt đầu sau khi KLMAS duyệt MVP.

| Giai đoạn | Mục tiêu | Task | Cổng nghiệm thu |
|---|---|---|---|
| **P0 Nền tảng** | Repo, CI, schema `core`, auth/RBAC, master data, staging | F-01…F-07 | Staging chạy; master data được KLMAS xác nhận |
| **P1 MVP-1: Dữ liệu & dashboard** | Import 4 loại Excel + AI minimap → style master; màn ORDER RECAP; Control Tower; buyer portal; export đúng mẫu cũ; đối soát | D-01…D-12 | Import 26FW thật khớp golden numbers (`GUIDELINES.md` §7); KLMAS duyệt file export so với file gốc |
| **P2 Flow sản xuất** | T&A ngược từ RDD, báo cáo sản xuất ngày, cảnh báo, checklist vật tư, thay đổi từ email, xuất hàng, booking, thẻ vật tư | P-01…P-09 | Chạy 1 tuần với dữ liệu thật; MR xác nhận cảnh báo đúng |
| **P3 Flow QC** | PWA kiểm hàng, PDF theo brand, tiếp nhận yêu cầu, AI phân công, phản hồi lỗi, dashboard QC, portal khách | Q-01…Q-09 | 3 kiểm viên dùng thử 1 tuần; PDF giống mẫu của brand |
| **P4 Kho dữ liệu & AI** | `dw` + dbt, scorecard, nạp mùa cũ, kho tri thức, trợ lý trả lời buyer, báo cáo tuần, landing | A-01…A-07 | Số khớp với 26FW; ban giám đốc KLMAS duyệt báo cáo tuần |
| **P5 Go-live** | Bảo mật, hiệu năng, e2e, chạy song song với Excel, đào tạo, release | H-01…H-06 | 2–4 tuần song song, chênh lệch < 0,5%; KLMAS ký go-live |

P2 và P3 chạy song song sau P1 (QC chỉ cần `core` và auth). P4 bắt đầu khi P1 xong, chạy song song với P2/P3.

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

## 3. Ước lượng

Đơn vị:
- **Giờ build:** thời gian làm việc thực tế cho task (viết code, chạy test, sửa), chưa gồm review. Ước lượng dựa trên mô hình phát triển có AI agent hỗ trợ; đội chỉ gồm người sẽ cần nhiều giờ hơn.
- **Giờ PO:** thời gian PO review, nghiệm thu và trả lời câu hỏi.
- **Giờ KLMAS:** thời gian phía khách hàng cung cấp dữ liệu, trả lời, UAT.

| Giai đoạn | Task | Giờ build | + Review/điều phối 25% | Giờ PO | Giờ KLMAS | Lịch (song song) |
|---|---|---|---|---|---|---|
| P0 Nền tảng | 7 | 56 | 70 | 6 | 2 | 0,5–1 tuần |
| P1 MVP-1 | 12 | 166 | 208 | 18 | 8 | 2–2,5 tuần |
| P2 Sản xuất | 9 | 136 | 170 | 14 | 6 | 2,5–3 tuần |
| P3 QC | 9 | 136 | 170 | 14 | 8 | 2,5–3 tuần (song song P2) |
| P4 DW & AI | 7 | 92 | 115 | 8 | 4 | 2 tuần (song song) |
| P5 Go-live | 6 | 62 | 78 | 16 | 20 | 1 tuần + 2–4 tuần chạy song song |
| **Tổng** | **50** | **648** | **≈ 810** | **≈ 76** | **≈ 48** | **≈ 10–12 tuần đến go-live** |

Giờ PO theo từng task trong `backlog.csv` cộng lại là 69 giờ; bảng trên cộng thêm khoảng 7 giờ điều phối và demo hằng tuần.

Cách tính lịch:
- 3 luồng song song (Data/Backend, Frontend, AI/QC), mỗi luồng khoảng 10 giờ build hữu ích mỗi ngày.
- 810 ÷ 30 ≈ 27 ngày làm việc, tức khoảng 5,5 tuần nếu chỉ tính build. Phần còn lại của 10–12 tuần là chờ dữ liệu và phản hồi từ KLMAS, UAT, và 2–4 tuần chạy song song với Excel.
- **Điểm nghẽn là phản hồi từ KLMAS** (mỗi vòng 2–5 ngày) và thời gian review của PO (khoảng 1–1,5 giờ/ngày), không phải tốc độ build. Muốn nhanh hơn: cho phép tự merge các task rủi ro thấp (UI tĩnh, docs) sau review, và gom câu hỏi gửi KLMAS mỗi tuần một lần.
- Theo biên bản họp, dự án loại này trước đây mất 6 tháng trở lên với đội truyền thống.

**Độ tin cậy:** P0/P1 ±20% (đã có schema, parser prototype, dữ liệu thật). P2/P3 ±35% (chưa có file thật của mẫu báo cáo kiểm và báo cáo sản xuất ngày). Tích hợp Kakao/Gmail phụ thuộc quyền truy cập, có thể bị chặn hoàn toàn.

## 4. Việc chỉ phía khách hàng hoặc PO làm được

- Cung cấp dữ liệu thật: file mùa cũ, mẫu báo cáo kiểm theo brand, minimap của các brand khác, quyền đọc email. Danh sách đầy đủ: `open_questions.md` mục D.
- Tài khoản: AWS, Zalo OA, Kakao Business, Claude API key.
- UAT với MR và kiểm viên của KLMAS; trả lời các câu hỏi trong `open_questions.md`.
- Duyệt release production.

## 5. Rủi ro và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Hiểu sai nghiệp vụ may mặc | BA viết tiêu chí nghiệm thu trước khi code; review đối chiếu `analys-docs`; golden test từ file thật |
| Template Excel thay đổi | Parser kiểm dấu hiệu template, báo `TEMPLATE_CHANGED` thay vì nạp sai (`etl_pipeline.md`) |
| AI trích xuất sai số lượng | Luôn qua bước MR duyệt; eval ≥ 98% trên bộ mẫu trước khi bật |
| Lộ dữ liệu buyer | Security review bắt buộc trên PR chạm auth/dữ liệu; RLS theo brand; không đưa dữ liệu thật vào log của prompt |
| Chờ dữ liệu KLMAS | P1 dùng dữ liệu 26FW/27SS đã có; gửi danh sách xin dữ liệu ngay tuần 1 |
| Câu hỏi nghiệp vụ chưa có câu trả lời | Quy tắc cấu hình được (RDD−12, AQL, định nghĩa return %); không hard-code |
