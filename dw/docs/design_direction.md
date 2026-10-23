# Hướng thiết kế KOPS (G-01, 23/10/2026)

## Người dùng và ngữ cảnh

- Quản lý KLMAS (người Hàn, người Việt), MR, QC. Desktop là chính (1366–1920 px), xem nhanh trên điện thoại (390 px).
- App nội bộ, nhiều dữ liệu, mở hằng ngày để trả lời: *hôm nay việc gì khẩn, style nào trễ, nhà máy nào có vấn đề*.
- Chế độ của bề mặt (theo Impeccable): **Operate** — người dùng làm việc, không phải được thuyết phục. Thành công = tìm được việc
  khẩn và con số đúng trong vài giây, tin con số (nguồn, ngày dữ liệu, nhãn giả định luôn thấy được).

## Hướng

Điềm tĩnh, chuyên nghiệp, đọc nhanh: mật độ dữ liệu cao nhưng thoáng. Màu dành cho **dữ liệu và trạng thái**, không cho khung
(menu, nút, thẻ). Bề mặt phẳng: tách khối bằng đường 1 px hoặc một bậc tông, không đổ bóng trang trí. Trung tính về thương hiệu
cho tới khi có logo thật: màu nhấn là một token (`--accent`), đổi một chỗ khi thay logo. Không phong cách landing page, không
hiệu ứng trang trí, không chuyển động ngoài phản hồi thao tác (150–200 ms, tắt khi `prefers-reduced-motion`).

## Thứ tự ưu tiên khi các skill khuyên khác nhau

1. **Đúng và rõ số liệu**: số căn phải, chữ số đều (`tabular-nums`), đơn vị và nguồn rõ, nhãn "Giả định" không bao giờ bị ẩn.
2. **Tiếp cận WCAG 2.2 AA**: tương phản chữ ≥ 4,5:1 (chữ lớn, viền điều khiển ≥ 3:1), dùng được bằng bàn phím, focus thấy rõ,
   không chỉ dựa vào màu (trạng thái luôn có chữ hoặc biểu tượng), vùng bấm ≥ 24 px (≥ 44 px trên điện thoại).
3. **Nhất quán hệ token / component**: một nơi khai báo màu, khoảng cách, bo góc, cỡ chữ; một kiểu cho thẻ KPI, bảng, bộ lọc,
   chip "Giả định", badge mức độ, trạng thái rỗng / đang tải / lỗi.
4. **Thẩm mỹ**.

## Token (gốc)

| Nhóm | Giá trị |
|---|---|
| Nền / bề mặt | `--bg` (nền trang), `--surface` (khối), `--surface-2` (một bậc tông: header bảng khi cần, hover) |
| Chữ | `--text` (≥ 12:1), `--text-2` (phụ, ≥ 4,5:1 trên cả `--bg` và `--surface`) |
| Đường | `--line` (phân cách), `--line-strong` (viền điều khiển, ≥ 3:1) |
| Nhấn | `--accent` (link, focus, mục đang chọn); nút chính dùng `--accent` đặc, chỉ một nút chính mỗi khối |
| Trạng thái | `--critical`, `--warning`, `--good`, `--neutral` — nền nhạt + chữ đậm cùng sắc, luôn kèm nhãn |
| Dữ liệu | 8 ô màu phân loại đã kiểm mù màu (F-05), thang xanh một sắc cho độ lớn, `--syn` cho giả định |
| Khoảng cách | thang 4 px: 4, 8, 12, 16, 24, 32 |
| Bo góc | 6 px (điều khiển), 10 px (khối); không lồng khối trong khối |
| Cỡ chữ | 12 / 13 / 14 (thân) / 16 / 20 / 24 — tỉ lệ ~1,15; số KPI 24 px, nặng 600 |

## Typography

Một họ chữ hệ thống, không gọi CDN, không tải font (font CJK tự host nặng nhiều MB):
`system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", sans-serif`.
Các font này có đủ dấu tiếng Việt và Hangul trên macOS, Windows, Linux (image Docker có `fonts-noto-cjk`). Số dùng
`font-variant-numeric: tabular-nums`. Chữ Hàn dùng `word-break: keep-all` để không ngắt giữa từ. Không viết hoa toàn bộ nhãn.

## Lời khuyên của skill đã chọn bỏ (và lý do)

| Skill | Lời khuyên | Quyết định |
|---|---|---|
| UI/UX Pro Max | Fira Code / Fira Sans từ Google Fonts | Bỏ: CDN bị cấm, Fira không có Hangul. Dùng system stack ở trên |
| UI/UX Pro Max | Pattern "Enterprise Gateway" (hero, logo khách, Contact Sales) | Bỏ: dành cho trang giới thiệu, không phải app nội bộ |
| UI/UX Pro Max | Màu nhấn hổ phách cho CTA | Bỏ: hổ phách trùng sắc với trạng thái "cảnh báo"; giữ một màu nhấn xanh từ token |
| UI/UX Pro Max | Spinner khi tải dữ liệu | Bỏ: dùng khung giữ chỗ (skeleton) giữ đúng bố cục |
| Taste Skill | "Cho sản phẩm một gương mặt": typeface riêng, dấu hiệu riêng, màu thương hiệu | Hoãn: PO giữ trung tính tới khi có logo thật; font riêng không có Hangul / nặng |
| Taste Skill | Chạy `assets.mjs` tìm ảnh, thư viện hướng nghệ thuật landing page | Bỏ: gọi mạng; app không cần ảnh |
| Frontend Design | Chấp nhận rủi ro thẩm mỹ, một điểm nhấn táo bạo | Bỏ: app nội bộ, PO yêu cầu điềm tĩnh; "điểm riêng" là ma trận rủi ro và danh sách việc khẩn |
| Impeccable | Tự host một typeface có cá tính | Không áp dụng: chế độ Operate cho phép font hệ thống |

Đã áp dụng (tóm tắt): biểu tượng SVG thay emoji; KPI là chữ trong một khối chia bằng đường mảnh, không icon / sparkline;
bảng không sọc, header xám nhỏ, số căn phải; chart ít khung; màu đổi chiều nói tốt / xấu chứ không chỉ lên / xuống; trạng
thái rỗng giữ khung và một câu hướng dẫn; tiêu đề nói kết luận khi có thể.
