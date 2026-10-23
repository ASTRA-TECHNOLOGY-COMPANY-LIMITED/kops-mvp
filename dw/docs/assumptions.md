# Giả định đang dùng (assumption_id)

Mỗi giả định có mã `ASM-…`. Mã xuất hiện trong dữ liệu (`sim.*.assumption_id`), trong code (comment) và trên dashboard (tooltip
của mọi số có phần giả định). Thay bằng dữ liệu / câu trả lời thật thì xoá giả định ở đây và ở code.

## Giả định nghiệp vụ (áp lên dữ liệu thật)

| assumption_id | Áp cho | Giả định | Câu hỏi KLMAS | Thay bằng thật khi |
|---|---|---|---|---|
| ASM-SEASON-01 | `dim.season` (ngày bắt đầu / kết thúc mùa) | Mùa = khoảng bán hàng: SS tháng 2–7, FW tháng 8 – tháng 1 năm sau | (mới) lịch mùa của từng brand | KLMAS gửi lịch mùa |
| ASM-DAILY-01 | Báo cáo sản xuất ngày của vendor (`config.VENDOR_BRAND`) | File `DHG-…` là của brand 8 SECONDS | (mới) báo cáo HAGACO có lẫn BEANPOLE KIDS không | file ghi brand trong nội dung |
| ASM-FRESH-01 | Độ tươi dữ liệu nhà máy | Đếm ngày thứ 2–6 nằm giữa ngày báo cáo cuối và hôm nay (không tính 2 đầu); ≤ 2 FRESH, 3–5 STALE, > 5 DARK | (mới) nhà máy có gửi báo cáo thứ 7 không | KLMAS chốt lịch gửi |
| ASM-QC-01 | Tỉ lệ lỗi (bảng kiểm KLMAS dòng D, INPUT DATA cột DEFECT QTY) | DEFECT QTY là số **điểm lỗi**; tỉ lệ = lỗi ÷ SL đã kiểm | Q26 | KLMAS trả lời Q26 |
| ASM-QC-02 | Kết quả lần kiểm bên thứ ba | REMARK có chữ `REJECT` → REJECT, còn lại PASS | Q31 | sheet DATA có cột kết quả |
| ASM-LINK-01 | Đổi lô hàng email → style | Lô thành phẩm trong email gắn với style có lô cùng nhà máy trong Shipment Status, ETD lệch ≤ 3 ngày | Q17 | AI đọc email (D-03) hoặc booking trong Shipment Status |

## Dữ liệu giả định (schema `sim`, `is_synthetic = true`)

Sinh bởi `kops_dw/sim.py`, seed cố định `20261023`, tái lập được (cùng dữ liệu thật → cùng số). Phân phối lấy từ cycle thật
CHALLENGER 26FW; không có số tròn tự đặt. Tắt bằng `KOPS_SIM=0`. Không bao giờ vào `core`, `fact` hay check golden.

| assumption_id | Dữ liệu | Cách sinh | Tham số (đo từ dữ liệu thật) | Câu hỏi / dữ liệu cần | Thay bằng thật khi |
|---|---|---|---|---|---|
| ASM-SIM-01 | 2 mùa trước của CHALLENGER: 25FW, 25SS (style, lô xuất, lần kiểm) | Lấy mẫu style 26FW (cho 25FW) / 27SS (cho 25SS): số style × U(0,85–1,05), SL × U(0,9–1,1), ETD lùi 1 / 2 năm; lô đầu = ETD + độ trễ rút từ 26FW; SL xuất = SL × tỉ lệ xuất rút từ 26FW; một lần kiểm trước lô đầu | độ trễ lô đầu, tỉ lệ xuất / đặt, phương thức (26FW); tỉ lệ lỗi theo nhà máy (bảng kiểm KLMAS) | ORDER RECAP + Shipment Status 25SS / 25FW | KLMAS gửi file mùa cũ |
| ASM-SIM-02 | Sản lượng ngày cho style đang may mà nhà máy không gửi báo cáo ngày (CHALLENGER: TIEN THANH, FG VINA, NATEXCO, HA HIEU; DHG: B85, FG VINA, SON HA…) | Chuỗi ngày (bỏ Chủ nhật) kết thúc trước ETD 5 ngày; mỗi ngày = trung vị sản lượng ngày thật của nhà máy (không có thì rút từ mọi nhà máy) × U(0,6–1,3), dừng ở hôm nay hoặc khi đủ SL | sản lượng ngày theo nhà máy (báo cáo ngày CHALLENGER) | D3 / Q03: báo cáo ngày của các nhà máy này | nhà máy gửi báo cáo ngày |
| ASM-SIM-03 | Kết quả kiểm + lỗi cho style chưa có dữ liệu kiểm mà ETD đã qua (DHG 26FW, DKM 26FW, 2 style CHALLENGER) | Một lần kiểm 1–4 ngày trước ETD: SL kiểm = SL × U(0,9–1), lỗi = SL kiểm × tỉ lệ lỗi của nhà máy × U(0,7–1,3); REJECT với xác suất bằng tỉ lệ REJECT thật | tỉ lệ lỗi theo nhà máy (bảng kiểm KLMAS), tỉ lệ REJECT (INPUT DATA) | bảng kiểm của các khách này | KLMAS gửi bảng kiểm |
| ASM-SIM-04 | Lô xuất cho khách không gửi Shipment Status (DHG 26FW) với style đã qua ETD | Một lô = ETD + độ trễ rút từ 26FW; SL = SL đặt × tỉ lệ xuất rút từ 26FW | như ASM-SIM-01 | Shipment Status của DHG | KLMAS gửi file |
| ASM-SIM-05 | Mã lỗi của các lần kiểm giả định | Mỗi điểm lỗi rút một mã theo tần suất mã lỗi thật trong INPUT DATA (Pareto) | 296 mã, tần suất thật | Q32 (nhóm mã theo loại hàng) | có dữ liệu lỗi thật của khách |

Không sinh dữ liệu cho style có ETD sớm hơn ngày đầu mùa − 120 ngày (nghi gõ sai năm, vd. KOFA 27SS ETD 02/2026).
