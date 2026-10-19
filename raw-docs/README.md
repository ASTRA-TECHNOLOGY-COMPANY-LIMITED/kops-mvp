# raw-docs — tài liệu gốc từ KLMAS

Thư mục này chứa file gốc KLMAS gửi. **Chỉ đọc**: không sửa nội dung, không đổi tên file. Toàn bộ thư mục không đưa lên git (dữ liệu kinh doanh), trừ file README này. Xin PO để lấy bộ file.

Kho dữ liệu (`dw/`) quét toàn bộ thư mục này mỗi lần build và nhận loại file theo **tên file**. Thư mục giúp người tìm file, còn mùa, brand và nhà máy được lấy từ tên file và đường dẫn.

## Cấu trúc

```
raw-docs/
├── COMPANY/                       Hồ sơ năng lực, giới thiệu công ty KLMAS
├── MEETINGS/                      Biên bản họp (.docx)
├── ORDER/<BRAND>/<MÙA>/           ORDER RECAP: master đơn hàng theo mùa (MR lập)
├── TRACKING/<BRAND>/<MÙA>/        Bảng theo dõi KLMAS tổng hợp: Production & Shipping Status, Shipment Status
├── PRODUCTION/                    Báo cáo sản xuất ngày do nhà máy gửi
│   ├── <BRAND>/<MÙA>/<NHÀ MÁY>/              brand làm trực tiếp với KLMAS (vd. CHALLENGER)
│   └── <VENDOR>/<BRAND>/<MÙA>/<NHÀ MÁY>/     brand qua vendor (vd. DHG(DAEHAN GROBAL)/8 SECONDS)
├── INSPECTION/
│   ├── ORDER_TRACKING/<BRAND>/<MÙA>/   Bảng theo dõi kiểm hàng cho đơn KLMAS quản lý sản xuất (vd. file của HOA)
│   ├── THIRD_PARTY/                    Dữ liệu kiểm hàng bên thứ ba (INPUT DATA.xlsx: mỗi lần kiểm, mã lỗi)
│   ├── FORMS/                          Mẫu phiếu / mẫu báo cáo kiểm còn trống
│   └── SAMPLES/                        Phiếu đã điền, báo cáo kiểm hoàn chỉnh làm mẫu
├── inbox/                         Email (.eml) xuất từ hộp thư, nếu có
├── _DUPLICATES/                   Bản trùng nội dung, giữ lại để đối chiếu; kho dữ liệu bỏ qua
└── _REORG/                        Nhật ký sắp xếp lại thư mục + script hoàn tác
```

Thư mục bắt đầu bằng `_` bị kho dữ liệu bỏ qua.

## Quy ước khi thêm file

| Loại | Đặt ở | Tên file nên có |
|---|---|---|
| ORDER RECAP | `ORDER/<BRAND>/<MÙA>/` | `YYMMDD`, mùa (`26FW`), `ORDER RECAP` |
| Production & Shipping Status, Shipment Status | `TRACKING/<BRAND>/<MÙA>/` | `YYMMDD`, mùa, `PRODUCTION AND SHIPPING STATUS` / `SHIPMENT STATUS` |
| Báo cáo sản xuất ngày | `PRODUCTION/…/<MÙA>/<NHÀ MÁY>/` | `YYMMDD`, mùa, tên nhà máy, `DAILY PRODUCTION REPORT` |
| Bảng theo dõi kiểm (đơn KLMAS) | `INSPECTION/ORDER_TRACKING/<BRAND>/<MÙA>/` | `INSPECTION REPORT` |
| Dữ liệu kiểm bên thứ ba | `INSPECTION/THIRD_PARTY/` | `INPUT DATA` |
| Biên bản họp | `MEETINGS/` | `.docx` |

- Có bản mới của cùng một báo cáo: **thêm file mới** với ngày mới ở đầu tên, không ghi đè file cũ. Kho dữ liệu tự lấy bản mới nhất.
- File đặt nhầm thư mục hoặc trùng nội dung: chuyển vào `_DUPLICATES/`, giữ nguyên đường dẫn con để biết gốc.

## Lịch sử sắp xếp

- **2026-10-19:** chuyển 15 file từ cấu trúc phẳng sang cấu trúc trên. Nội dung không đổi (đã kiểm md5). Danh sách và cách hoàn tác: `_REORG/2026-10-19_moves.tsv`, `_REORG/undo_2026-10-19.sh`.
