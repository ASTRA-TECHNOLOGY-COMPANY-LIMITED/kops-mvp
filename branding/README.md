# branding — logo của ứng dụng KOPS

Thư mục này được mount vào container (`/app/branding`, chỉ đọc). Muốn đổi logo: thay file, tải lại trang, không cần build lại.

| File | Dùng ở | Gợi ý |
|---|---|---|
| `logo.svg` | header và trang đăng nhập, giao diện sáng | cao 32 px, nền trong suốt; SVG hoặc đổi tên thành `logo.png` |
| `logo-dark.svg` | giao diện tối | cùng kích thước, màu sáng |
| `favicon.svg` | biểu tượng tab trình duyệt | vuông 32 × 32 |

Logo mặc định là chữ "KOPS" trung tính, không phải logo của KLMAS hay ASTRA. Có file `.png` cùng tên gốc
(`logo.png`, `logo-dark.png`, `favicon.png`) thì app dùng file `.png` trước file `.svg`. Tên công ty ở chân trang đặt bằng
`KOPS_BRAND_NAME` trong `.env` (mặc định `KLMAS`).
