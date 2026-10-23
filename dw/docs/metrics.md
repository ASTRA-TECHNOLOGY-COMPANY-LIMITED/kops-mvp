# Chỉ số cho quản lý (D-05)

Bảng `mart.mgr_*` trong `sql/40_mgr.sql`. Mọi bảng tách phần thật và phần giả định (`is_synthetic`, hoặc cặp cột
`*_real` / `*_syn`) và chỉ chứa số cộng được (tổng, đếm); dashboard tự tính tỉ lệ với hoặc không có phần giả định.
Ví dụ là số **thật** của CHALLENGER 26FW, đo ngày 23/10/2026 (`KOPS_TODAY` mặc định = ngày build).

| Chỉ số | Công thức | Grain / bảng | Nguồn | Ví dụ thật |
|---|---|---|---|---|
| SL đặt, số style, số nhà máy | Σ `order_qty` style còn hiệu lực (`is_active`) | style → `mgr_style`, `mgr_season` | ORDER RECAP bản hiện hành | 62.131 pcs, 110 style, 8 nhà máy |
| % đã xuất | SL xuất (lô SHIPMENT, không gồm mẫu) ÷ SL đặt còn hiệu lực | `mgr_season.shipped_real / order_qty` | Shipment Status | 60.357 / 62.131 = **97,1%** |
| Đúng hạn xuất | **Số chính** (PO chốt 23/10): lô đầu tiên có ETD ≤ ETD VN của RECAP (quy tắc chặt). **Số phụ**, nhãn "≤ ETD + 7 ngày": cho trễ `ontime_tolerance_days` = 7 ngày (quy tắc cũ của Control Tower). Chờ KLMAS xác nhận Q21 (ASM-ONTIME-01) | `mgr_season.on_time_real / judged_real`, `on_time_tol_real` | Shipment Status + RECAP | chặt: 21 / 104 = **20,2%**; +7 ngày: 81 / 104 = **77,9%** (= `mart.season_kpi`) |
| Số ngày trễ ETD | ETD lô đầu − ETD VN (âm = sớm) | style; `delay_days_real / judged_real` | như trên | trung bình **4,5 ngày** |
| Style rủi ro | Còn hiệu lực, chưa xuất đủ (dung sai 5%) và: ngày sẵn sàng dự báo + 12 ngày vận chuyển > RDD (`FORECAST_AFTER_RDD`), hoặc BAL kế hoạch < 0 (`PLAN_BAL_NEGATIVE`), hoặc đã qua ETD mà chưa xuất (`ETD_PASSED_NOT_SHIPPED`) | `mgr_style.risk_reason` | dự báo từ báo cáo ngày (`mart.style_forecast`), nếu không có thì Production Status; kế hoạch | **6** style (CHF4WJK6804, CHF4MJK6405, CHF4WJK6805 dự báo sau RDD; CHF4MJK6403, CHF4WJK6802, CHF4WJK6806 qua ETD) |
| Ngày sẵn sàng dự báo | Ngày báo cáo cuối + ⌈SL còn lại ÷ tốc độ⌉ ngày làm việc (T2–T7) + 5 ngày; tốc độ = TB 3 ngày có sản lượng gần nhất trong 10 ngày | style → `mart.style_forecast` | báo cáo sản xuất ngày | CHF4MPT6444: 190 / 350 pcs, 50 pcs/ngày → sẵn sàng 25/10, trễ 18 ngày |
| Tiến độ may (S-curve) | Kế hoạch: SL mỗi style chia đều cho ngày làm việc từ ngày vào chuyền tới ngày xong theo kế hoạch; thực tế: Σ sản lượng ngày | khách × mùa × nhà máy × ngày → `mgr_scurve` | PRODUCTION PLAN, báo cáo ngày | lũy kế theo ngày |
| Funnel màu × size, cờ | Đặt (RECAP theo màu; báo cáo ngày theo size) → cắt, may (báo cáo ngày, last-seen) → đạt kiểm (bảng kiểm KLMAS, theo màu; bộ 2 món tính theo món ít hơn, Q11) → xuất (Shipment Status, lô SHIPMENT). Cờ, dung sai `qty_tolerance_pct` = 5% (Q13): `CUT_SHORT` cắt < đặt × 95% khi đã xuất hoặc đã qua ETD (theo size); `OUTPUT_GT_CUT` may > cắt (theo size); `SHIP_GT_ORDER` xuất > đặt RECAP × 105% (theo màu; theo size nhà máy hay xuất dư vài cái nên không gắn cờ) | `mart.style_funnel` (level SIZE / COLOR) | báo cáo ngày, RECAP, bảng kiểm, Shipment Status | HA HIEU = ô tổng sheet `9.28` J31 / N31 / Z31 = 740 / 740 / 90; `SHIP_GT_ORDER` 3 style giảm 20% ở RECAP (Q04); `OUTPUT_GT_CUT` CHF4MJK6404 BEIGE S 64 / 32 (TRUONG PHUC sheet `10.14` dòng 173); `CUT_SHORT` CHF4WHP6850 (4 size), DHG 456Y3ZMCA (2 size) |
| Việc cần xử lý | Một dòng = một việc, chỉ dữ liệu thật: `PLAN_LATE` (BAL kế hoạch < 0, hoặc ngày xong + 5 ngày hoàn thiện + 12 ngày vận chuyển > RDD), `FORECAST_LATE` (dự báo sau RDD, hoặc qua ETD chưa xuất đủ), `MATERIAL_LATE` (vật tư về sau ngày cắt kế hoạch; ngày về = ETA, không có thì ETD + 7 ngày, ASM-MAT-01), `APPROVAL_MISSING` (ngày cắt kế hoạch từ 7 ngày trước tới 21 ngày tới, chưa xuất, chưa có mốc FPP CFMD / DM duyệt trước ngày cắt), `DAILY_STALE` (nhà máy có style đang may, > 1 ngày làm việc không gửi báo cáo ngày, Q32), `PROPOSAL_PENDING` (thay đổi đọc từ email chờ duyệt), `FILE_MISMATCH` (lệch số giữa file / ô tổng sai, hoặc ETD / ngày cắt trước đầu mùa > 240 ngày (`year_suspect_days`) — nghi gõ sai năm, Q46; style như vậy không sinh việc khác). Mức 1 nghiêm trọng (sắp tới hạn: ≤ 7–14 ngày), 2 cao, 3 trung bình; hạn = ngày cắt / ETD / hôm nay; người phụ trách để trống (Q50) | `mart.mgr_action` | kế hoạch, báo cáo ngày, email, RECAP, Shipment Status | 27SS ngày 23/10: 10 kế hoạch trễ (5 BAL âm ở NATEXCO / SON HA), 3 thiếu duyệt mẫu (DHG), 2 nhà máy thiếu báo cáo ngày |
| Tải nhà máy | Σ SL đặt theo tuần ETD; Σ sản lượng ngày theo tuần | `mgr_weekly` (measure ETD_PLAN / SHIPPED / OUTPUT) | RECAP, Shipment Status, báo cáo ngày | TBM 37 style / 19.770 pcs (Production Status) |
| Tỉ lệ đạt kiểm, tỉ lệ lỗi | Lỗi ÷ SL đã kiểm (ASM-QC-01, Q24); REJECT ÷ số lần kiểm (ASM-QC-02, Q25) | nhà máy × tháng × nguồn → `mgr_quality` | bảng kiểm KLMAS (dòng C, D), INPUT DATA | NATEXCO 946 / 1.407 = **67,2%** điểm lỗi / SL kiểm; MTT 21,1% |
| Pareto mã lỗi | Σ điểm lỗi (minor + major) theo mã, sắp giảm dần | mã × nguồn → `mgr_defect_pareto` | INPUT DATA (bên thứ ba) | A08 bẩn 15.282, A37 thừa chỉ 14.187 (= 42,9% tổng) |
| Phàn nàn chất lượng từ buyer | Thư loại QUALITY hoặc tiêu đề có QUALITY / 품질 / 불량 | thư → `mgr_buyer_complaint` | email | 26 thư (vd. "8SECONDS - QUALITY ATTENTION") |
| Số lần đổi nhà máy / SL / assort / ETD | Đếm `fact.change` (ghi chú RECAP, khác biệt giữa các bản RECAP, đề xuất email) + mốc ASSORT_CHANGE | khách × mùa × nhà máy × tháng → `mgr_changes`; style → `mgr_style` | RECAP, email | 18 đổi nhà máy (14 / 110 style), 30 đổi SL, 2 đổi assort; ghi chú `FIXED FACT` (chốt nhà máy lần đầu) không tính là thay đổi |
| ETD vật tư trễ | Lô vật tư có ETD cũ → ETD mới | nhà máy → `mart.material_delay` | tiêu đề email | 7 / 15 lô bị dời |
| Thời gian phản hồi email | Trung vị số giờ giữa 2 thư liên tiếp của 2 người khác nhau trong một luồng | tháng × loại người gửi → `mgr_email_response` | email | KLMAS trả lời trung vị 12,3 giờ |
| Độ tươi dữ liệu | Ngày T2–T6 giữa báo cáo ngày cuối và hôm nay: ≤ 2 FRESH, 3–5 STALE, > 5 DARK (ASM-FRESH-01) | nhà máy → `mart.factory_freshness` | báo cáo ngày | ngày 19/10: TBM, TRUONG PHUC FRESH; NATEXCO DARK |
| Chênh lệch giữa các file | Recap vs Shipment / Production, SHIPPING SCHEDULE vs RECAP, PDF buyer vs kế hoạch, ô tổng sai | `mgr_recon` | các file | 22 + 11 + 18 + 49 dòng |
| Scorecard nhà máy | Đúng hạn (lô đầu ≤ ETD VN), 100 − % lỗi, 100 − 10 × thay đổi / 1.000 pcs, độ tươi (FRESH 100 / STALE 50 / DARK 0); điểm = trung bình có trọng số `config.SCORECARD_WEIGHTS` (mặc định bằng nhau, PO giữ tới khi KLMAS trả lời Q21; ASM-SCORE-01); thành phần chưa có dữ liệu thì bỏ và chia lại trọng số; công thức hiện trên trang Nhà máy | nhà máy × khách × mùa → `mgr_factory` | các dòng trên | DONG MY đúng hạn 28,6%, NATEXCO lỗi 67,2% |
| So với mùa trước | Cùng chỉ số, mùa cùng nửa năm trước (26FW ↔ 25FW). 25SS / 25FW chưa có dữ liệu thật → giả định ASM-SIM-01 | `mgr_season` | — | 25FW (giả định) đúng hạn chặt 14 / 96 |

## Chart quản lý bổ sung (F-05)

Màu: 8 ô phân loại đã kiểm định (bảng tham chiếu dataviz, đạt kiểm tra mù màu ở cả nền sáng `#ffffff` và tối `#191d22`);
độ lớn dùng một thang xanh (sáng → đậm); màu trạng thái (đỏ / vàng / xanh lá) chỉ dùng cho trạng thái, luôn kèm nhãn.
Mỗi chart có tooltip ghi nguồn; nhãn "Giả định" khi có phần dữ liệu `sim`. Không chart nào dùng hai trục Y.

| Chart | Trang | Định nghĩa | Bảng / nguồn |
|---|---|---|---|
| Ma trận rủi ro | Tổng quan | Style còn hiệu lực, chưa xuất đủ (dung sai 5%): trục ngang = RDD − hôm nay (ngày), trục dọc = max(đã may, đã xuất) ÷ SL đặt, bong bóng = SL đặt; đỏ = có `risk_reason`, vàng = còn < 30 ngày mà < 50%, xanh = bình thường. Bấm → Style 360 | `mart.mgr_style` |
| Phễu mốc | Tiến độ | Số style đã qua: FPP REQUEST, FPP CFMD, DM duyệt (mốc email / tài liệu), đã cắt (ngày cắt kế hoạch đã tới hoặc có sản lượng), đã may, đã kiểm, đã xuất; mốc sau kéo theo mốc trước (style đã xuất thì đã cắt, may, kiểm) | `mart.mgr_style_stage` |
| Lead time từng chặng | Tiến độ | Box plot theo nhà máy (≥ 2 style): FPP REQUEST → FPP CFMD, FPP CFMD → ngày cắt kế hoạch, ngày cắt → ETD lô xuất đầu (ngày) | `mart.mgr_style_stage` |
| Lịch ETD tuần × nhà máy | Xuất hàng | Heatmap SL đặt theo tuần ETD VN và nhà máy; bấm → lọc nhà máy | `mart.mgr_weekly` (ETD_PLAN) |
| Tải so với công suất | Nhà máy | SL kế hoạch may mỗi tuần (PRODUCTION PLAN chia đều ngày làm việc) so với SL đã may; "công suất" = tuần may nhiều nhất đã đạt — KLMAS chưa có số chuyền × target | `mart.mgr_scurve`, `mart.mgr_weekly` |
| Biểu đồ kiểm soát | Chất lượng | p-chart tỉ lệ lỗi kiểm bên thứ ba theo tháng: p = điểm lỗi ÷ SL kiểm, đường giữa p̄, giới hạn p̄ ± 3·√(p̄(1−p̄)/n) (ASM-QC-01, Q24); điểm ngoài giới hạn tô đỏ | `mart.mgr_quality` (INPUT DATA) |
| Tỉ lệ đạt nhà máy × tháng | Chất lượng | KLMAS: SL đạt ÷ SL kiểm; bên thứ ba: (lần kiểm − REJECT) ÷ lần kiểm (ASM-QC-02, Q25); 15 nhà máy kiểm nhiều nhất | `mart.mgr_quality` |
| Cầu số lượng (waterfall) | Thay đổi & email | Đặt ban đầu = đặt hiện tại − Σ thay đổi SL (ghi chú RECAP `QTY_NOTE` + khác biệt giữa các bản `VERSION_QTY`); giảm, tăng; cắt (báo cáo ngày; style không có báo cáo lấy SL may); may; xuất — chỉ dữ liệu thật | `mart.mgr_qty_bridge` |
| Tuổi đề xuất chờ duyệt | Thay đổi & email | Số đề xuất `PENDING_REVIEW` theo số ngày từ email tới hôm nay | `fact.change` |
| Tỉ trọng size theo mùa | Xu hướng | % SL đặt theo size (cột 100%), theo mùa × khách | `mart.trend_size` (Shipment Status) |
| Top màu theo mùa | Xu hướng | 8 màu có SL đặt lớn nhất (màu còn hiệu lực) | `mart.trend_color` (ORDER RECAP) |
| Item × size | Xu hướng | % SL của mỗi item (giới tính + loại hàng trong mã style) theo size, mỗi hàng 100% | `mart.trend_size` |
| Vải chính theo mùa | Xu hướng | Số style theo nhà cung cấp vải chính (phần trước dấu `)` trong cột MAIN FABRIC) | `mart.trend_fabric` |
| So sánh brand | Xu hướng | SL đặt theo brand × mùa (style còn hiệu lực, dữ liệu thật) | `mart.mgr_style` |
