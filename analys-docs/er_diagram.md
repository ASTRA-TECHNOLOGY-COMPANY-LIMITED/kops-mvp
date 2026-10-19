# ER Diagram

Sơ đồ dưới đây gồm tầng `core` (mô hình nghiệp vụ) và các bảng `etl` chính. Bảng `raw`, `stg`, `mart` được mô tả ở `database_design.md`. Bảng đánh dấu (P) là tạm thời.

```mermaid
erDiagram
    BRAND ||--o{ SEASON : has
    BRAND ||--o{ STYLE : owns
    SEASON ||--o{ COLLECTION : contains
    SEASON ||--o{ STYLE_ORDER : includes
    COLLECTION ||--o{ STYLE_ORDER : groups
    STYLE ||--o{ STYLE_ORDER : "ordered as"
    STYLE ||--o{ STYLE_ALIAS : "known as"
    ITEM_TYPE ||--o{ STYLE : classifies
    PRODUCT_LINE ||--o{ STYLE_ORDER : "line of"
    STYLE_STATUS ||--o{ STYLE_ORDER : "current status"
    STYLE_ORDER ||--o{ STYLE_ORDER_STATUS_HISTORY : "status over time"

    STYLE_ORDER ||--|{ STYLE_ORDER_COLOR : "has colours"
    COLOR ||--o{ STYLE_ORDER_COLOR : "is"
    COLOR ||--o{ COLOR_ALIAS : "spelled as"
    STYLE_ORDER_COLOR ||--o{ ORDER_QTY_SIZE : "size breakdown"
    SIZE ||--o{ ORDER_QTY_SIZE : "of size"
    STYLE_ORDER_COLOR ||--o{ ORDER_QTY_CHANGE : "qty history"

    FACTORY ||--o{ FACTORY_ALIAS : "spelled as"
    STYLE_ORDER ||--|{ FACTORY_ASSIGNMENT : "produced by"
    FACTORY ||--o{ FACTORY_ASSIGNMENT : "assigned"

    MILESTONE_TYPE ||--o{ MILESTONE_EVENT : typed
    STYLE_ORDER ||--o{ MILESTONE_EVENT : "progress events"
    STYLE_ORDER ||--o{ PRODUCTION_SNAPSHOT : "reported progress"
    STYLE_ORDER ||--o{ PRODUCTION_PLAN : "planned dates"

    SEASON ||--o{ SHIPMENT : "ships in"
    SHIPPING_MODE ||--o{ SHIPMENT : via
    SHIPMENT ||--|{ SHIPMENT_LINE : contains
    STYLE_ORDER_COLOR ||--o{ SHIPMENT_LINE : shipped
    SIZE ||--o{ SHIPMENT_LINE : "of size"
    FACTORY ||--o{ SHIPMENT_LINE : "shipped from"

    STYLE_ORDER ||--o{ SAMPLE_DISPATCH : "samples sent"
    SAMPLE_DISPATCH ||--|{ SAMPLE_DISPATCH_LINE : contains
    STYLE_ORDER_COLOR ||--o{ SAMPLE_DISPATCH_LINE : "sample of"

    SUPPLIER ||--o{ FABRIC : supplies
    SUPPLIER ||--o{ SUPPLIER_ALIAS : "spelled as"
    STYLE_ORDER ||--o{ STYLE_FABRIC : "fabric BOM"
    FABRIC ||--o{ STYLE_FABRIC : "used in"
    COLOR ||--o{ STYLE_FABRIC : "garment colour"
    FABRIC_SHIPMENT ||--|{ FABRIC_SHIPMENT_LINE : contains
    STYLE_FABRIC ||--o{ FABRIC_SHIPMENT_LINE : "delivered by"

    TRIM_ITEM ||--o{ STYLE_TRIM : "used in"
    STYLE_ORDER ||--o{ STYLE_TRIM : "logo / label / trim"

    STYLE_ORDER ||--o{ FACTORY_PRICE : "priced (P)"
    STYLE_ORDER ||--o{ TRADE_DOCUMENT : "documents (P)"

    SOURCE_FILE ||--o{ INGESTION_RUN : "loaded by"
    INGESTION_RUN ||--o{ DATA_ISSUE : logs
    SOURCE_FILE ||--o{ STYLE_ORDER : "provenance"
    SOURCE_FILE ||--o{ PRODUCTION_SNAPSHOT : "provenance"

    STYLE {
        int style_id PK
        varchar style_no UK
        char gender
        char item_type_code FK
        text description_en
        text name_kr
        bool is_code_valid
    }
    STYLE_ORDER {
        int style_order_id PK
        smallint season_id FK
        int collection_id FK
        int style_id FK
        varchar order_no
        varchar status_code FK
        date etd_vn
        date rdd_kr
    }
    STYLE_ORDER_COLOR {
        int soc_id PK
        int style_order_id FK
        int color_id FK
        text color_raw
        int order_qty
    }
    ORDER_QTY_SIZE {
        int soc_id PK
        varchar size_code PK
        int qty
    }
    FACTORY_ASSIGNMENT {
        int assignment_id PK
        int style_order_id FK
        int factory_id FK
        date valid_from
        date valid_to
    }
    MILESTONE_EVENT {
        bigint event_id PK
        int style_order_id FK
        varchar milestone_code FK
        smallint round_no
        varchar action
        date event_date
        text raw_text
    }
    PRODUCTION_SNAPSHOT {
        bigint snapshot_id PK
        int style_order_id FK
        date as_of_date
        int output_qty
        int inspected_qty
        int shipped_qty_reported
    }
    SHIPMENT {
        int shipment_id PK
        date etd
        date eta
        varchar mode_code FK
        text label_raw
        bool needs_review
    }
    SHIPMENT_LINE {
        bigint shipment_line_id PK
        int shipment_id FK
        int soc_id FK
        varchar size_code FK
        int qty
    }
    STYLE_FABRIC {
        bigint style_fabric_id PK
        int style_order_id FK
        int fabric_id FK
        text part_raw
        numeric consumption_order
        numeric po_qty_yd
        numeric unit_price
        char currency
        date as_of_date
    }
    SOURCE_FILE {
        bigint file_id PK
        char sha256 UK
        varchar doc_type
        date report_date
    }
```

## Giải thích quan hệ & bằng chứng

| Quan hệ | Bản số | Bằng chứng | Độ tin cậy |
|---|---|---|---|
| STYLE 1–N STYLE_ORDER | 1 style có thể có nhiều đơn ở các mùa (reorder) | `CHF4WPT5822` = REORDER R1 trong 26FW; `CHE4…` (mùa 2025) xuất hiện trong file 26FW; `CHF2…` reorder | Trung bình — chưa thấy cùng mã trong 2 mùa ở dữ liệu hiện có (giao 26FW∩27SS = ∅) |
| STYLE_ORDER 1–N STYLE_ORDER_COLOR | 1–6 màu/style | F3 dòng màu trong block; F2 dòng ORDER | Cao |
| STYLE_ORDER_COLOR 1–N ORDER_QTY_SIZE | 1–6 size | F2 header size | Cao |
| STYLE_ORDER N–M FACTORY (theo thời gian) | Thường 1 nhà máy hiện hành; có lịch sử chuyển | `260512 MOVED FACT`; FAB 0519→0615 đổi 66 dòng | Cao |
| SHIPMENT N–M STYLE_ORDER_COLOR (qua SHIPMENT_LINE) | 1 lô chứa nhiều style/nhà máy; 1 style xuất nhiều lô (1ST–4TH SHIP) | Cùng nhãn lô trên nhiều sheet F2; cột 1ST–4TH SHIP | Cao cho N–M; **giả thuyết** cho việc hợp nhất lô giữa các nhà máy (cần xác nhận lô là booking chung hay riêng từng nhà máy) |
| STYLE_ORDER 1–N SAMPLE_DISPATCH | nhiều đợt mẫu | F2 SMPL LIST | Cao |
| STYLE_ORDER 1–N STYLE_FABRIC | 3–15 phần vải/màu | FAB | Cao |
| STYLE_FABRIC N–M FABRIC_SHIPMENT | | Cột `ETD 0615 VESSEL KYLIN`… | Trung bình (cột lô tàu chỉ phủ một phần) |
| STYLE_ORDER N–M TRIM_ITEM | | LOGO STATUS `-AP_TR02 …` | Trung bình (parse text) |
| STYLE_ORDER 1–N FACTORY_PRICE (P) | | Cột TARGET/FIXED/FINAL CMPH | Thấp — chưa có dữ liệu |
