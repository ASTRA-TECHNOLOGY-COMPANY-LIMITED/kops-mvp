---
title: "KOPS MVP Phase 1 — lệnh khởi động cho agent"
status: ready
created: 2026-10-19
---

# Lệnh khởi động cho agent thực hiện MVP Phase 1

Dán nguyên phần dưới đây cho agent điều phối (hoặc một agent Claude Code duy nhất) trong repo `kops-mvp`.

---

Bạn thực hiện **KOPS MVP Phase 1**: mở rộng data warehouse trong `dw/` để nạp báo cáo sản xuất ngày và bảng kiểm hàng, dự báo ngày xong bằng sản lượng thực tế, đo độ tươi dữ liệu theo nhà máy, và hiển thị funnel số lượng cho từng style.

**Đọc theo thứ tự trước khi làm:**
1. `GUIDELINES.md`: quy tắc chung, nhất là §5 quy trình, §7 quy tắc dữ liệu, §8 bảo mật.
2. `dw/README.md`: kiến trúc hiện tại và cách chạy.
3. `analys-docs/review_inspection_production.md`: vì sao làm việc này.
4. `analys-docs/mvp_phase1_spec.md`: đặc tả. **Đây là nguồn sự thật cho quy tắc và golden numbers.**
5. `plans/MVP_PHASE1_PLAN.md`: danh sách task M1-01 → M1-11, phụ thuộc, tiêu chí nghiệm thu, mẫu báo cáo.
6. `analys-docs/open_questions.md` Phần 1: các giả định đang dùng.

**Phạm vi:** chỉ các task trong plan. Không làm tỷ lệ lỗi, năng suất theo công nhân, app nhập liệu, đăng nhập. Không sửa `raw-docs/`.

**Cách làm:**
- Theo thứ tự phụ thuộc trong plan; mỗi task một nhánh `feat/M1-xx-…` và một commit hoặc PR riêng.
- Sau mỗi task chạy `cd dw && KOPS_TODAY=2026-10-19 .venv/bin/python -m kops_dw`. Build phải xong và mọi golden test PASS trước khi sang task sau.
- Với M1-08, mở `dw/build/dashboard.html` bằng trình duyệt headless, chụp màn hình các tab ở cả sáng/tối và desktop/mobile, rồi tự xem lại trước khi báo xong.

**Tiêu chí hoàn thành toàn bộ:**
- 11 task đạt tiêu chí nghiệm thu trong plan.
- Golden G1–G13 (spec §8) và 19 test cũ đều PASS. Test W33 đổi 49 → 18, có ghi chú lý do.
- Build lại từ thư mục sạch theo README chạy được.
- Tài liệu đã cập nhật, không mâu thuẫn với code.
- Không có dữ liệu thật, tên kiểm viên hay `dw/build/` trong git.

**Dừng và hỏi PO khi:** số đo khác golden number; gặp template báo cáo mới; cần đổi quy tắc trong spec hoặc trả lời câu hỏi mở; sắp làm thao tác không đảo ngược được (xoá dữ liệu, push lên `main`).

**Báo cáo:** sau mỗi task, báo theo mẫu ở plan §4. Khi xong toàn bộ, gửi PO một báo cáo tổng gồm:
- Bảng 11 task kèm trạng thái.
- Kết quả `python -m kops_dw test` đầy đủ.
- Đường dẫn ảnh chụp dashboard.
- Thời gian build trước và sau.
- Golden number nào lệch và vì sao.
- Các câu Ưu tiên 1–2 trong `open_questions.md` KLMAS chưa trả lời, và số liệu nào đang chạy theo giả định của câu đó.
