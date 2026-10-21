# raw-docs — tài liệu gốc từ KLMAS

Thư mục này là **bản tải về cục bộ** của các file KLMAS lưu trên **Google Drive của KLMAS**. Cây thư mục bên dưới do đội dự án tự sắp cho dễ tìm; Drive của KLMAS có cấu trúc khác. Vì vậy khi trao đổi với KLMAS chỉ dùng **tên file** (giữ nguyên như trên Drive), không dùng đường dẫn ở đây.

**Chỉ đọc**: không sửa nội dung, không đổi tên file. Toàn bộ thư mục không đưa lên git (dữ liệu kinh doanh), trừ file README này. Xin PO để lấy bộ file.

Kho dữ liệu (`dw/`) quét toàn bộ thư mục này mỗi lần build và nhận loại file theo **tên file**. Thư mục giúp người tìm file, còn mùa, brand và nhà máy được lấy từ nội dung và tên file; đường dẫn cục bộ chỉ là phương án cuối.

## Cấu trúc

```
raw-docs/
├── COMPANY/                       Hồ sơ năng lực, giới thiệu công ty KLMAS
├── MEETINGS/                      Biên bản họp (.docx)
├── ORDER/<KHÁCH>/<MÙA>/           ORDER RECAP: master đơn hàng theo mùa (MR lập). KHÁCH = đơn vị đặt hàng với KLMAS:
│                                  CHALLENGER, DHG(DAEHAN GROBAL), JBEE, KOFA, DKM(다경물산). Brand đọc trong file
├── TRACKING/<BRAND>/<MÙA>/        Bảng theo dõi KLMAS tổng hợp: Production & Shipping Status, Shipment Status
├── PRODUCTION PLAN/<KHÁCH>/<MÙA>/  Kế hoạch sản xuất theo nhà máy (mỗi sheet một nhà máy). Từ 21/10/2026: BPK, NEPA
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
| ORDER RECAP | `ORDER/<KHÁCH>/<MÙA>/` | `YYMMDD`, mùa (`26FW`), `ORDER RECAP` |
| Kế hoạch sản xuất | `PRODUCTION PLAN/<KHÁCH>/<MÙA>/` | `YYMMDD`, mùa, `PRODUCTION PLAN` |
| Production & Shipping Status, Shipment Status | `TRACKING/<BRAND>/<MÙA>/` | `YYMMDD`, mùa, `PRODUCTION AND SHIPPING STATUS` / `SHIPMENT STATUS` |
| Báo cáo sản xuất ngày | `PRODUCTION/…/<MÙA>/<NHÀ MÁY>/` | `YYMMDD`, mùa, tên nhà máy, `DAILY PRODUCTION REPORT` |
| Bảng theo dõi kiểm (đơn KLMAS) | `INSPECTION/ORDER_TRACKING/<BRAND>/<MÙA>/` | `INSPECTION REPORT` |
| Dữ liệu kiểm bên thứ ba | `INSPECTION/THIRD_PARTY/` | `INPUT DATA` |
| Biên bản họp | `MEETINGS/` | `.docx` |

- File mới: tải từ Google Drive của KLMAS, **không đổi tên**. Chỉ copy file chưa có (so tên file); copy lại cả thư mục Drive sẽ sinh bản trùng vì cây thư mục ở đây khác cây Drive (đã xảy ra ngày 21/10, xem lịch sử).
- Có bản mới của cùng một báo cáo: **thêm file mới** với ngày mới ở đầu tên, không ghi đè file cũ. Kho dữ liệu tự lấy bản mới nhất.
- File đặt nhầm thư mục hoặc trùng nội dung: chuyển vào `_DUPLICATES/`, giữ nguyên đường dẫn con để biết gốc.

## Lịch sử sắp xếp

- **2026-10-19:** chuyển 15 file từ cấu trúc phẳng sang cấu trúc trên. Nội dung không đổi (đã kiểm md5). Danh sách và cách hoàn tác: `_REORG/2026-10-19_moves.tsv`, `_REORG/undo_2026-10-19.sh`.
- **2026-10-20:** chuyển 12 file ORDER RECAP (thư mục mới `ORDER RECAP/` của KLMAS) vào `ORDER/<KHÁCH>/<MÙA>/`. Không có file trùng nội dung. Danh sách và cách hoàn tác: `_REORG/2026-10-20_moves.tsv`, `_REORG/undo_2026-10-20.sh`. Phân tích: `analys-docs/review_order_recap_multicustomer.md`.
- **2026-10-21:** thư mục `ORDER RECAP/` được copy lại từ Drive: 12 file trùng MD5 với bản đã có chuyển vào `_DUPLICATES/ORDER RECAP/`; 1 file mới (`261021 DHG) BPK 27SS ORDER RECAP.xlsx`) vào `ORDER/DHG(DAEHAN GROBAL)/27SS/`. 2 file kế hoạch sản xuất đầu tiên vào `PRODUCTION PLAN/<KHÁCH>/<MÙA>/`; bản trùng của chúng trong `PRODUCTION/` chuyển vào `_DUPLICATES/PRODUCTION/`. Nhật ký và hoàn tác: `_REORG/2026-10-21_moves.tsv`, `_REORG/undo_2026-10-21.sh`.
