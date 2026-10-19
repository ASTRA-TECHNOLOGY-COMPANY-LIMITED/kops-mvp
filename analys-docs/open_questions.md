# Open Questions, Assumptions & Decisions

Câu hỏi chỉ KLMAS hoặc PO trả lời. Khi gặp một câu ở đây trong lúc làm task: dùng giả định ghi trong bảng, ghi rõ trong PR là đang dựa trên giả định nào, và báo PO. Khi có câu trả lời, PO cập nhật cột "Giả định đang dùng" thành quyết định, kèm ngày và nguồn.

**Phase 1 = MVP data warehouse** (`dw/`, kế hoạch ở `plans/MVP_PHASE1_PLAN.md`): nạp Excel, báo cáo sản xuất ngày, bảng kiểm, email, biên bản họp vào một kho; dashboard tiến độ, xuất hàng, đối soát, độ tươi dữ liệu. Phase 1 **chỉ cần giải quyết các câu ở mục 1**. Câu ở mục 2 để nguyên giả định, hỏi khi tới giai đoạn cần.

Mức độ trong Phase 1:
- **Chặn**: sai thì số liệu chính trên dashboard sai. Cần câu trả lời trước buổi demo MVP.
- **Xác nhận**: MVP chạy được bằng giả định (đã để cấu hình được). KLMAS xác nhận hoặc sửa trong buổi demo.

## 1. Cần cho Phase 1 (MVP data warehouse)

### 1.1 Nghiệp vụ

| # | Mức | Câu hỏi | Ảnh hưởng tới MVP | Giả định đang dùng |
|---|---|---|---|---|
| Q1 | Chặn | File nào là **nguồn chính thức** cho SL đặt, SL đã xuất, nhà máy hiện tại? | Mọi KPI trên Control Tower | ORDER RECAP = style/màu/SL/nhà máy; Shipment Status = size và lô xuất; báo cáo ngày = cắt/vào chuyền/ra chuyền (xem Q23) |
| Q23 | Chặn | Báo cáo sản xuất ngày có phải nguồn chính thức cho SL cắt / vào chuyền / ra chuyền không? Production Status lấy số từ đâu, cập nhật lúc nào? | Dự báo ngày xong và cảnh báo trễ (`review_inspection_production.md` §2.1) | Báo cáo ngày là nguồn chính; Production Status chỉ dùng để đối soát |
| Q24 | Chặn | NATEXCO không có báo cáo ngày sau 08/09, HA HIEU chỉ có 2 ngày, 9 style đang chạy không có báo cáo nào. Còn file nào chưa gửi không? | Độ phủ dữ liệu tiến độ | Thiếu file, đã xin bổ sung (R7) |
| Q4 | Chặn | 3 style CHF3MPT6334 / CHF3WPT6745 / CHF3WSK6751 giảm 20% ở ORDER RECAP (288/320/296) nhưng Production và Shipment Status vẫn 360/400/370. Số nào là đơn hiện hành? | SL còn lại, % xuất | Theo ORDER RECAP (mới nhất), ghi `XSRC_MISMATCH` |
| Q3 | Chặn | Mã style lệch giữa các file: `CHF4WHP6851`↔`CHF4WSK6851`, `CHF4WHP6852`↔`CHF4WSK6852`, `CHFWWT6817`↔`CHF4WWT6817`. Mã nào đúng? | Ghép dữ liệu giữa các file | Map tạm, đánh dấu `STYLE_ALIAS_UNCONFIRMED`. Báo cáo ngày của TBM cũng dùng `WSK6851`, nên 2/3 nguồn dùng `WSK` |
| Q27 | Chặn | Báo cáo ngày của TBM ghi `CHE3WPT6986`, `CHE3WSK6754`, `CHE4MPT6441`, `CHE4WPT6842`, trong khi ORDER RECAP có `CHF…` cùng số. Đây là gõ sai chữ mùa (E thay F) phải không? | 4 style TBM đang mất tiến độ | Gõ sai: map sang `CHF…`, đánh dấu chưa xác nhận như Q3 |
| Q2 | Xác nhận | "SHIPPED Q'TY" có tính cả mẫu (shipping/photo sample) không? Ở từng file? | Đối soát SL xuất giữa các file | Lưu tách hàng và mẫu; % xuất chỉ tính hàng |
| Q6 | Xác nhận | Màu nền ô có còn là cách chính thức ghi trạng thái style? Ô B và D khác màu thì ưu tiên ô nào? | Cột trạng thái style | Ưu tiên ô D, rồi ô B |
| Q13 | Xác nhận | Danh sách nhà máy chính thức và mã viết tắt; quan hệ FG VINA / FG BAC GIANG / TBM; SON HA, JM (27SS) là nhà máy nào? | Scorecard theo nhà máy | Theo bảng alias trong `dw/kops_dw/config.py` |
| Q14 | Xác nhận | Dung sai xuất dư/thiếu bao nhiêu %? | Style được tính là "đã xuất" | ±5% |
| Q15 | Xác nhận | XXL và 2XL có phải một size? | Ma trận màu × size | Có |
| Q16 | Xác nhận | 5 style 27SS có ETD đầu năm 2026 (vd. CHG1WJK7504 17/01/2026): có phải sai năm (2027)? | Biểu đồ ETD mùa 27SS | Đánh dấu `ETD_OUT_OF_SEASON`, không tự sửa |
| Q26 | Xác nhận | Style bộ (VEST + JACKET, vd. CHF4WJK6801): SL đặt 350 là 350 bộ hay 350 mỗi món? | SL đạt kiểm so với SL đặt | 350 bộ = 350 mỗi món; đạt kiểm tính theo món thấp hơn |
| Q28 | Xác nhận | Dữ liệu Daehan Global / 8 SECONDS (nhà máy HAGACO) có thuộc phạm vi Phase 1 không? Ai được xem? | Chiều khách/brand, quyền xem dashboard | Nạp vào kho, tách theo brand; dashboard mặc định chỉ hiện CHALLENGER |

### 1.2 Kỹ thuật / vận hành

| # | Mức | Câu hỏi | Ảnh hưởng tới MVP | Giả định đang dùng |
|---|---|---|---|---|
| T1 | Đã quyết | Kho dùng cho vận hành (app nhập liệu) hay chỉ báo cáo? | Kiến trúc Phase 1 | Phase 1: báo cáo + đối soát từ file. App nhập liệu ở giai đoạn sau |
| T4 | Xác nhận | Tần suất cập nhật mong muốn và nơi đặt file (Google Drive, SharePoint, thư mục mạng)? | Cách thả file và chạy build | Hằng ngày; thư mục theo quy ước `PRODUCTION/<KHÁCH>/<BRAND>/<MÙA>/<NHÀ MÁY>/` |
| T5 | Xác nhận | Ai cần xem dashboard ở Phase 1 (MR, QC, quản lý, buyer)? | Có cần tách bản dashboard theo brand không | Chỉ nội bộ KLMAS và ASTRA; buyer chưa xem ở Phase 1 |

### 1.3 Dữ liệu cần xin KLMAS cho Phase 1

PO là đầu mối. Đánh dấu ✅ khi đã nhận và ghi vị trí lưu.

| # | Dữ liệu | Dùng cho | Trạng thái |
|---|---|---|---|
| R5 | Báo cáo sản xuất ngày và kế hoạch sản xuất từ nhà máy | Tiến độ may, dự báo | ✅ Đã nhận báo cáo ngày của 6 nhà máy CHALLENGER + HAGACO (`raw-docs/PRODUCTION/`). Kế hoạch sản xuất: chưa |
| R7 | Báo cáo ngày còn thiếu: NATEXCO sau 08/09, HA HIEU trước 26/09, DONG MY sau 28/09, MTT sau 02/10, và của TIEN THANH, FG VINA | Độ phủ tiến độ (Q24) | Chưa nhận |
| R8 | Bảng kiểm hàng của các nhà máy còn lại (DONG MY, TBM) nếu có | Funnel đến bước kiểm đạt | Chưa nhận |

## 2. Không cần cho Phase 1 (để giai đoạn sau)

Giả định giữ nguyên. Không ai chặn task Phase 1 vì các câu này.

| # | Ưu tiên | Câu hỏi | Cần khi | Giả định đang dùng |
|---|---|---|---|---|
| Q25 | P1 | "DEFECT QTY" trong bảng kiểm là số sản phẩm lỗi hay số điểm lỗi? Tỷ lệ lỗi tính trên SL kiểm hay SL đạt? | Dashboard QC, scorecard kiểm viên (P3) | Số điểm lỗi; tỷ lệ = lỗi ÷ SL kiểm. Phase 1 không tính tỷ lệ lỗi |
| Q5 | P1 | Một lô xuất (vd. `8/12ETD-8/18ETA SEA`) là booking/container chung hay riêng từng nhà máy? Có số invoice/BL không? | Kế hoạch xuất, packing list, booking (P2) | Chung theo (ETD, ETA, phương thức) |
| Q7 | P2 | Quy tắc RDD: ETD + 12, RDD − 14 hay RDD − 10? | Lịch T&A tính ngược từ RDD (P2) | ETD + 12 (Phase 1 chỉ hiển thị) |
| Q8 | P2 | Đơn vị tiền tệ của đơn giá vải và CMPH? | Chi phí (ngoài phạm vi hiện tại) | NULL + issue |
| Q9 | P2 | Ý nghĩa ký hiệu vật tư: `G`, `C`, `C1`, `L`, `P`, `OK`, `SNAP`, `SBM`, `L+P+W` | Checklist vật tư (P2) | Lưu nguyên văn |
| Q10 | P2 | `RE`, `CMMT`, `HC` trong ghi chú mốc mẫu nghĩa là gì? | Mốc mẫu, T&A (P2) | RE = return, CMMT = comment, HC = hand carry |
| Q11 | P2 | Bảng mã nhóm hàng: ST, IT, MK, HC, GW, CP, WI, OP, HP | Chuẩn hoá năng suất, báo cáo theo nhóm hàng | Suy theo mô tả |
| Q12 | P2 | Mã năm/mùa trong style (`F3`, `G2`, `E4`) và chữ số 5 (`CHF5UGW6070`)? | Tách mã tự động | Không dùng làm khoá |
| Q17 | P2 | 7 style có trong FAB nhưng không có trong ORDER RECAP: đã huỷ hay đổi mã? | Nạp FAB, cảnh báo vật tư (P2) | INFO issue |
| Q18 | P2 | Block `CHE4…` mùa trước trong Shipment Status có cần theo dõi không? | Backfill mùa cũ (P4) | Bỏ qua block rỗng |
| Q29 | P3 | Có SMV theo style/nhóm hàng để chuẩn hoá năng suất không? | Scorecard năng suất | Chưa có; Phase 1 không xếp hạng năng suất |
| Q19 | P3 | Cột giá / thanh toán / PO / C/O trong ORDER RECAP nằm ở hệ thống nào? | Tài chính (ngoài phạm vi) | Chưa nạp |
| Q20 | P3 | `(BE: SAND)` trong ô màu là "before: SAND"? | Lịch sử đổi màu chi tiết | Có |
| Q21 | P3 | 해리감 (PART) là gì? | Nạp FAB | Lưu nguyên văn |
| Q22 | P3 | Ảnh thiết kế trong ORDER RECAP có cần lưu không? | Màn ORDER RECAP trong app | Không |
| T2 | P1 | Hạ tầng production: on-prem, cloud hay Microsoft? | App vận hành (P0 của app) | PostgreSQL managed; Phase 1 dùng DuckDB cục bộ |
| T3 | P2 | Công cụ BI có sẵn (Power BI, Metabase…)? | Khi cần BI ngoài dashboard HTML | Dashboard HTML của DW |
| T6 | P3 | Mở rộng sang brand khác và dữ liệu QC chi tiết? | Sau Phase 1 | Thiết kế đã có chiều brand |
| T7 | P3 | Thời gian lưu dữ liệu raw | Vận hành lâu dài | 2 năm |

### Dữ liệu xin sau Phase 1

| # | Dữ liệu | Dùng cho | Trạng thái |
|---|---|---|---|
| R1 | 1–2 mùa CHALLENGER đã kết thúc: ORDER RECAP, Shipment Status, Production Status | Backfill, scorecard (A-03, A-02) | Chưa nhận |
| R2 | Minimap/order list của ít nhất 2 brand khác | AI nhận dạng minimap (D-07) | Chưa nhận |
| R3 | 1 tuần báo cáo kiểm chi tiết (Excel + ảnh, có mã lỗi) và mẫu báo cáo của 3–6 brand | Mô hình QC, PDF theo brand (Q-01, Q-03) | Chưa nhận |
| R4 | Danh sách kiểm viên, khu vực, nhà máy chuyên trách; địa chỉ nhà máy | Phân công kiểm viên (Q-05) | Chưa nhận |
| R6 | 20–30 email/Kakao mẫu với buyer (ẩn danh nếu cần) | Trích thay đổi bằng AI, trợ lý trả lời (P-05, A-05) | Chưa nhận; Phase 1 dùng 4 email SAMPLE |

## 3. Giả định kỹ thuật đã áp dụng trong phân tích

- Giá trị số và ngày lấy từ cache của Excel (không tính lại công thức). Nếu file chưa được tính lại trước khi lưu, giá trị có thể cũ.
- `.xlsb` được đọc qua bản chuyển đổi bằng LibreOffice để lấy màu ô; ảnh và định dạng có điều kiện chưa được đối chiếu đầy đủ.
- PDF chỉ dùng text layer; chưa OCR các trang ảnh.
- Màu trạng thái đọc theo legend dòng 1–2 của ORDER RECAP; màu theme được so theo mã theme + tint.
- Mọi thống kê số dòng và số style là đếm đầy đủ, không lấy mẫu.
