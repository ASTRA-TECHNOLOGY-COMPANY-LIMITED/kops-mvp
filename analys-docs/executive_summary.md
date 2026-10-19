# Executive Summary — Phân tích tài liệu klmas-docs & đề xuất CSDL

**Phạm vi:** 6 file trong `klmas-docs` (5 Excel + 1 PDF; 1 file là bản sao trùng 100%). Phân tích chỉ đọc; không sửa file nguồn.

## Bức tranh nghiệp vụ
KLMAS quản lý sản xuất và kiểm hàng tại Việt Nam cho brand Hàn Quốc **CHALLENGER**. Các file theo dõi vòng đời của từng **style**: chốt đơn → phân nhà máy gia công (8 nhà máy) → phát triển mẫu (REF/FPP/INLINE/TOP) → nguyên phụ liệu → cắt/may → kiểm → xuất hàng theo lô (SEA/AIR/hand-carry) sang Hàn. Mùa **26FW**: 110 style đang chạy, 62,131 pcs, phần lớn đã xuất. Mùa **27SS**: 137 style, 87,940 pcs, đang làm mẫu.

## Phát hiện quan trọng nhất
1. **Tổng số liệu sai do công thức**: file Production Status báo tổng đơn **106,681** pcs, thực tế **62,357** — vùng SUM của subtotal theo nhà máy chồng lấn nhau. Mọi KPI tổng của file này đều sai.
2. **Không có một nguồn sự thật**: cùng một style có 3 con số "đã xuất" khác nhau ở 3 file (chỉ 21/100 style khớp giữa Production Status và Order Recap). Nguyên nhân: ngày chụp khác nhau, định nghĩa có/không tính mẫu, nhập tay.
3. **Định danh không ổn định**: mã style mâu thuẫn giữa file (`…WHP6851` ↔ `…WSK6851`), lỗi gõ (`CHFWWT6817`); tên nhà máy 2–5 biến thể; màu viết tự do (`K.GREY`/`K/GREY`/`KHAKI GREY`); không có mã nhà máy, mã lô xuất, số PO/invoice.
4. **Thông tin quan trọng nằm ở chỗ khó trích xuất**: trạng thái style mã hoá bằng **màu nền ô**; milestone là **ghi chú tự do** (`7/16 SENT - 7/20 RE / 7/21 2ND SENT`); dữ liệu chi tiết size/lô nằm trong **lưới block** (144 block ở 6 sheet, 2 sheet bị ẩn).
5. **Dữ liệu tốt nhất hiện có**: file Shipment Status — parser đã trải phẳng 103 style thành 2,342 dòng color×size (đơn, xuất, mẫu) và khớp **100%** với các ô tổng của file. Order Recap là master đáng tin cho style/màu/qty.
6. Cột giá, thanh toán, PO, C/O trong Order Recap **gần như trống**; đơn giá vải **không ghi đơn vị tiền tệ**.

## Kiến trúc đề xuất
**PostgreSQL** (miễn phí, ràng buộc mạnh, JSONB, Unicode Hàn/Việt) theo **Option B: raw layer + core quan hệ chuẩn hoá + mart view**, trong 1 DB nhiều schema:
- `etl`/`raw`: đăng ký file (hash, phiên bản), lưu nguyên văn từng ô (giá trị, công thức, màu nền) → truy vết mọi con số về ô Excel gốc, nạp lại được.
- `core`: 39 bảng (16 tham chiếu/alias) — style ↔ style_order (theo mùa) ↔ màu ↔ size; phân nhà máy theo thời gian; sự kiện milestone; snapshot sản xuất; lô xuất & dòng xuất; mẫu; BOM vải & lô vải; trim/logo; bảng alias cho nhà máy/màu/NCC/mã style.
- `mart`: tổng đơn/xuất/mẫu/balance **được tính từ chi tiết**, không lưu số tổng nhập tay; view đối soát "số báo cáo vs số tính".

SQL Server là lựa chọn tương đương nếu công ty đã chuẩn hoá trên Microsoft. Không cần data warehouse ở quy mô hiện tại (~5–10k dòng chi tiết/mùa). `schema.sql` đã chạy thử thành công trên PostgreSQL 16 (tạo 48 bảng + 2 view; đã thử insert và kiểm tra ràng buộc CHECK).

## Rủi ro chính
- Template Excel thay đổi thường xuyên → parser gãy (giảm thiểu: kiểm dấu hiệu template, FAILED thay vì nạp sai).
- Chưa chốt nguồn chính thức cho qty/shipped (Q1–Q4) → DB vẫn phản ánh mâu thuẫn.
- Text milestone khó parse hoàn toàn → luôn giữ `raw_text`, chấp nhận một phần cần nhập lại.
- Năm của ngày dạng `m/d` phải suy luận.

## Ưu tiên & bước tiếp theo
1. **Nghiệp vụ trả lời các câu P1** trong `open_questions.md` (nguồn chính thức, định nghĩa shipped, mã style mâu thuẫn, khoá lô xuất, màu trạng thái).
2. **Sửa ngay** công thức subtotal của Production Status (DQ-01) — đang báo cáo sai ~70%.
3. Chốt **master data**: danh sách nhà máy + mã, bảng màu chuẩn, mã nhóm hàng, size.
4. Dựng DB theo `schema.sql`; làm parser theo thứ tự Shipment Status → Order Recap → Production Status → FAB.
5. Chạy song song với Excel 2–4 tuần, dùng báo cáo đối soát để làm sạch; sau đó chuyển nhập liệu sang app ghi thẳng vào core.

## Danh mục deliverables
`document_inventory.md` · `business_analysis.md` · `data_quality_report.md` · `database_design.md` · `schema.sql` · `er_diagram.md` · `source_to_target_mapping.csv` (98 dòng mapping) · `etl_pipeline.md` · `open_questions.md` · `executive_summary.md`
