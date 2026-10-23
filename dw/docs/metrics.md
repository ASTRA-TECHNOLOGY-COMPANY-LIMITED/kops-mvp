# Chỉ số cho quản lý (D-05)

Bảng `mart.mgr_*` trong `sql/40_mgr.sql`. Mọi bảng tách phần thật và phần giả định (`is_synthetic`, hoặc cặp cột
`*_real` / `*_syn`) và chỉ chứa số cộng được (tổng, đếm); dashboard tự tính tỉ lệ với hoặc không có phần giả định.
Ví dụ là số **thật** của CHALLENGER 26FW, đo ngày 23/10/2026 (`KOPS_TODAY` mặc định = ngày build).

| Chỉ số | Công thức | Grain / bảng | Nguồn | Ví dụ thật |
|---|---|---|---|---|
| SL đặt, số style, số nhà máy | Σ `order_qty` style còn hiệu lực (`is_active`) | style → `mgr_style`, `mgr_season` | ORDER RECAP bản hiện hành | 62.131 pcs, 110 style, 8 nhà máy |
| % đã xuất | SL xuất (lô SHIPMENT, không gồm mẫu) ÷ SL đặt còn hiệu lực | `mgr_season.shipped_real / order_qty` | Shipment Status | 60.357 / 62.131 = **97,1%** |
| Đúng hạn xuất | Lô đầu tiên có ETD ≤ ETD VN của RECAP (quy tắc chặt). Kèm quy tắc cũ của Control Tower: ≤ ETD VN + 7 ngày (`ontime_tolerance_days`) | `mgr_season.on_time_real / judged_real`, `on_time_tol_real` | Shipment Status + RECAP | chặt: 21 / 104 = **20,2%**; +7 ngày: 81 / 104 = **77,9%** (= `mart.season_kpi`) |
| Số ngày trễ ETD | ETD lô đầu − ETD VN (âm = sớm) | style; `delay_days_real / judged_real` | như trên | trung bình **4,5 ngày** |
| Style rủi ro | Còn hiệu lực, chưa xuất đủ (dung sai 5%) và: ngày sẵn sàng dự báo + 12 ngày vận chuyển > RDD (`FORECAST_AFTER_RDD`), hoặc BAL kế hoạch < 0 (`PLAN_BAL_NEGATIVE`), hoặc đã qua ETD mà chưa xuất (`ETD_PASSED_NOT_SHIPPED`) | `mgr_style.risk_reason` | dự báo từ báo cáo ngày (`mart.style_forecast`), nếu không có thì Production Status; kế hoạch | **6** style (CHF4WJK6804, CHF4MJK6405, CHF4WJK6805 dự báo sau RDD; CHF4MJK6403, CHF4WJK6802, CHF4WJK6806 qua ETD) |
| Ngày sẵn sàng dự báo | Ngày báo cáo cuối + ⌈SL còn lại ÷ tốc độ⌉ ngày làm việc (T2–T7) + 5 ngày; tốc độ = TB 3 ngày có sản lượng gần nhất trong 10 ngày | style → `mart.style_forecast` | báo cáo sản xuất ngày | CHF4MPT6444: 190 / 350 pcs, 50 pcs/ngày → sẵn sàng 25/10, trễ 18 ngày |
| Tiến độ may (S-curve) | Kế hoạch: SL mỗi style chia đều cho ngày làm việc từ ngày vào chuyền tới ngày xong theo kế hoạch; thực tế: Σ sản lượng ngày | khách × mùa × nhà máy × ngày → `mgr_scurve` | PRODUCTION PLAN, báo cáo ngày | lũy kế theo ngày |
| Tải nhà máy | Σ SL đặt theo tuần ETD; Σ sản lượng ngày theo tuần | `mgr_weekly` (measure ETD_PLAN / SHIPPED / OUTPUT) | RECAP, Shipment Status, báo cáo ngày | TBM 37 style / 19.770 pcs (Production Status) |
| Tỉ lệ đạt kiểm, tỉ lệ lỗi | Lỗi ÷ SL đã kiểm (ASM-QC-01, Q26); REJECT ÷ số lần kiểm (ASM-QC-02, Q31) | nhà máy × tháng × nguồn → `mgr_quality` | bảng kiểm KLMAS (dòng C, D), INPUT DATA | NATEXCO 946 / 1.407 = **67,2%** điểm lỗi / SL kiểm; MTT 21,1% |
| Pareto mã lỗi | Σ điểm lỗi (minor + major) theo mã, sắp giảm dần | mã × nguồn → `mgr_defect_pareto` | INPUT DATA (bên thứ ba) | A08 bẩn 15.282, A37 thừa chỉ 14.187 (= 42,9% tổng) |
| Phàn nàn chất lượng từ buyer | Thư loại QUALITY hoặc tiêu đề có QUALITY / 품질 / 불량 | thư → `mgr_buyer_complaint` | email | 26 thư (vd. "8SECONDS - QUALITY ATTENTION") |
| Số lần đổi nhà máy / SL / assort / ETD | Đếm `fact.change` (ghi chú RECAP, khác biệt giữa các bản RECAP, đề xuất email) + mốc ASSORT_CHANGE | khách × mùa × nhà máy × tháng → `mgr_changes`; style → `mgr_style` | RECAP, email | 18 đổi nhà máy (14 / 110 style), 30 đổi SL, 2 đổi assort; ghi chú `FIXED FACT` (chốt nhà máy lần đầu) không tính là thay đổi |
| ETD vật tư trễ | Lô vật tư có ETD cũ → ETD mới | nhà máy → `mart.material_delay` | tiêu đề email | 7 / 15 lô bị dời |
| Thời gian phản hồi email | Trung vị số giờ giữa 2 thư liên tiếp của 2 người khác nhau trong một luồng | tháng × loại người gửi → `mgr_email_response` | email | KLMAS trả lời trung vị 12,3 giờ |
| Độ tươi dữ liệu | Ngày T2–T6 giữa báo cáo ngày cuối và hôm nay: ≤ 2 FRESH, 3–5 STALE, > 5 DARK (ASM-FRESH-01) | nhà máy → `mart.factory_freshness` | báo cáo ngày | ngày 19/10: TBM, TRUONG PHUC FRESH; NATEXCO DARK |
| Chênh lệch giữa các file | Recap vs Shipment / Production, SHIPPING SCHEDULE vs RECAP, PDF buyer vs kế hoạch, ô tổng sai | `mgr_recon` | các file | 22 + 11 + 18 + 49 dòng |
| Scorecard nhà máy | Đúng hạn (lô đầu), tỉ lệ lỗi, số thay đổi, độ tươi, số style rủi ro; điểm = trung bình 4 thành phần (trọng số bằng nhau, chờ PO chốt), xếp hạng trên trang | nhà máy × khách × mùa → `mgr_factory` | các dòng trên | DONG MY đúng hạn 28,6%, NATEXCO lỗi 67,2% |
| So với mùa trước | Cùng chỉ số, mùa cùng nửa năm trước (26FW ↔ 25FW). 25SS / 25FW chưa có dữ liệu thật → giả định ASM-SIM-01 | `mgr_season` | — | 25FW (giả định) đúng hạn chặt 14 / 96 |
