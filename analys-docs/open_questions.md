# Open Questions, Assumptions & Decisions

Mức ưu tiên: **P1** = chặn thiết kế/nạp dữ liệu đúng · **P2** = ảnh hưởng chất lượng báo cáo · **P3** = có thể quyết sau

## A. Quyết định cần nghiệp vụ trả lời

| # | Ưu tiên | Câu hỏi | Vì sao quan trọng | Giả định đang dùng |
|---|---|---|---|---|
| Q1 | P1 | File nào là **nguồn chính thức** cho order qty, shipped qty, nhà máy hiện tại? | 3 file cho 3 con số khác nhau (business_analysis §5.3–5.4) | ORDER RECAP = style/màu/qty/factory; SHIPMENT STATUS = size & lô xuất; PRODUCTION STATUS = output/inspection |
| Q2 | P1 | "SHIPPED Q'TY" có bao gồm mẫu (shipping/photo sample) không? Ở từng file? | Quyết định công thức balance & báo cáo xuất thiếu/dư | DB lưu tách hàng và mẫu; mart hiển thị cả 2 cách |
| Q3 | P1 | CHF4WHP6851 ↔ CHF4WSK6851, CHF4WHP6852 ↔ CHF4WSK6852: mã nào đúng? Có phải đổi mã không? | Khoá chính sản phẩm | Ghi vào `style_alias` với `confirmed=false` |
| Q4 | P1 | 3 style CHF3MPT6334/CHF3WPT6745/CHF3WSK6751 giảm 20% ở ORDER RECAP (288/320/296) nhưng production & shipment vẫn 360/400/370 — số nào là đơn hiện hành? | Qty sai → balance sai | Theo ORDER RECAP (mới nhất), log XSRC_MISMATCH |
| Q5 | P1 | Một **lô xuất** (vd. `8/12ETD-8/18ETA SEA`) là một booking/container chung cho mọi nhà máy hay riêng từng nhà máy? Có số invoice/BL không? | Khoá của bảng shipment | Chung theo (ETD, ETA, mode); factory ở dòng shipment_line |
| Q6 | P1 | Bảng màu trạng thái (fill colour) có còn là cách chính thức để ghi trạng thái? Khi màu ô B và D khác nhau thì ưu tiên ô nào? | Trạng thái style | Ưu tiên ô D (mã style) |
| Q7 | P2 | Quy tắc RDD: ETD + 12 (công thức) hay RDD − 14 (header DETAIL) hay RDD − 10 (BUYER DEL)? | Kiểm tra ngày | ETD + 12 |
| Q8 | P2 | Đơn vị tiền tệ của 원단단가 (đơn giá vải) và CMPH? KR ~2,400 (KRW?), CN ~4.19 & VN ~0.85 (USD?) | Không thể tổng hợp chi phí | Để NULL + issue cho tới khi có quy tắc |
| Q9 | P2 | Ý nghĩa ký hiệu trong ghi chú vật tư: `G`, `C`, `C1`, `L`, `P`, `OK`, `SNAP`, `SBM`, `L+P+W` | Parse milestone vật tư | Lưu nguyên văn ở `detail` |
| Q10 | P2 | Ý nghĩa `RE` trong `7/16 SENT - 7/20 RE` (returned? rejected?), `CMMT` (comment?), `HC` (hand carry?) | Kiểu sự kiện | RE=RETURN, CMMT=comment received, HC=hand carry |
| Q11 | P2 | Bảng mã nhóm hàng: ST, IT, MK, HC, GW, CP, WI, OP, HP nghĩa là gì? | item_type master | Suy theo mô tả (business_analysis §4) |
| Q12 | P2 | Mã năm/mùa trong style (`F3`, `G2`, `E4`) có đúng E=2025, F=2026, G=2027 và 1–4 = Spring/Summer/Fall/Winter? Chữ số 5 (`CHF5UGW6070`)? | Tách mã | Giả thuyết như trên, không dùng làm khoá |
| Q13 | P2 | Danh sách nhà máy chính thức + mã viết tắt; quan hệ FG VINA / FG BAC GIANG / TBM; TIEN THANH; TRUONG PHUC TV | Master factory & alias | Theo bảng alias đề xuất |
| Q14 | P2 | Tiêu chuẩn chấp nhận xuất dư/thiếu (tolerance %) | Quy tắc QTY_RANGE | ±5% |
| Q15 | P2 | XXL và 2XL có tương đương? | Master size | Có |
| Q16 | P2 | 5 style 27SS có ETD đầu năm 2026 (CHG1WJK7504 2026-01-17, CHG2WJK7604, CHG2MST7238, CHG2WST7651, CHFG2WIT7957): sai năm (2027)? | Lịch sản xuất | Đánh dấu ETD_OUT_OF_SEASON, không tự sửa |
| Q17 | P2 | 7 style trong FAB nhưng không có trong ORDER RECAP (CHF3MPT6332, CHF3UCP6382, CHF3WPT6743, CHF4MCP6482, CHF4UCP6484, CHF4WCP6876, CHF4WSK6851) — đã huỷ hay đổi mã? | Vải đã đặt cho style không còn đơn | INFO issue |
| Q18 | P2 | Các style mùa trước `CHE4…` trong sheet TP/NATEXCO (block rỗng) có cần theo dõi không? | Phạm vi dữ liệu | Bỏ qua block rỗng |
| Q19 | P3 | Cột pricing/payment/PO/CO trong ORDER RECAP đang trống — dữ liệu này nằm ở hệ thống/file khác? Có đưa vào DB không? | Phạm vi Option B giai đoạn 1 | Tạo bảng (P), chưa nạp |
| Q20 | P3 | `(BE: SAND)` trong ô màu nghĩa là "before: SAND" (màu cũ)? | Lịch sử đổi màu | Có |
| Q21 | P3 | 해리감 (PART) là gì? | part_code | Lưu raw |
| Q22 | P3 | Ảnh thiết kế nhúng trong ORDER RECAP có cần lưu (object storage) không? | Dung lượng | Không ở giai đoạn 1 |

## B. Câu hỏi kỹ thuật / triển khai

| # | Ưu tiên | Câu hỏi | Giả định |
|---|---|---|---|
| T1 | P1 | DB dùng cho **vận hành** (app nhập liệu) hay chỉ **báo cáo** từ Excel? | Giai đoạn 1: báo cáo + đối soát từ Excel; giai đoạn 2: app |
| T2 | P1 | Hạ tầng: on-prem, cloud (AWS/GCP/Azure/Supabase), hay chuẩn Microsoft (SQL Server)? | PostgreSQL managed |
| T3 | P2 | Công cụ BI: Power BI, Metabase, Looker Studio? | Bất kỳ (mart views) |
| T4 | P2 | Tần suất cập nhật mong muốn (hằng ngày? theo giờ?) và nơi đặt file (Google Drive, SharePoint, thư mục mạng)? | Hằng ngày, thư mục drop |
| T5 | P2 | Số người dùng & phân quyền (MR, QC, quản lý, buyer?) | < 30 người, quyền theo vai trò |
| T6 | P3 | Có mở rộng sang brand khác (PDF liệt kê ~30 brand) & dữ liệu QC/inspection (báo cáo lỗi, kiểm hàng) không? Nếu có, cần mẫu file | Thiết kế đã có brand_id; QC chưa mô hình hoá |
| T7 | P3 | Thời gian lưu trữ raw (retention) | 2 năm |

## C. Giả định kỹ thuật đã áp dụng trong phân tích
- Giá trị số/ngày lấy từ cache của Excel (không tính lại công thức); nếu file chưa được recalculation trước khi lưu, giá trị có thể cũ.
- `.xlsb` được đọc bằng `pyxlsb` và bằng bản sao chuyển đổi qua LibreOffice để đọc màu/merge; không giả định chuyển đổi giữ đủ mọi tính năng (ảnh, định dạng có điều kiện chưa được đối chiếu đầy đủ).
- PDF: chỉ dùng text layer + xem ảnh trang ở độ phân giải thấp; chưa OCR toàn bộ (biểu đồ sản lượng, trang thông tin công ty).
- Phân tích màu trạng thái: chỉ đọc được màu RGB; các ô dùng theme colour (ON PRODUCTION, nhiều màu nhà máy) chưa giải mã.
- Tất cả thống kê về số dòng/số style là đếm đầy đủ (không lấy mẫu), riêng việc phân loại text milestone mới kiểm trên mẫu.
