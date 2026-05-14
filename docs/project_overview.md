# Tổng Quan Dự Án: Real Estate Lakehouse Pipeline

## 1. Giới thiệu

Dự án thu thập dữ liệu bất động sản từ **batdongsan.com.vn** và xây dựng pipeline lakehouse dạng batch để phục vụ phân tích thị trường.

**Kiến trúc tổng thể:** Lakehouse 3 lớp (Bronze → Silver → Gold) chạy trên VM Google Compute Engine theo lịch, đồng bộ dữ liệu lên Google Cloud Storage.

**Công nghệ chính:**
- **Ngôn ngữ:** Python 3.12
- **Crawl:** Crawl4AI, Requests, BeautifulSoup4, lxml
- **Xử lý dữ liệu:** Pandas, PySpark
- **Dashboard:** Streamlit + Plotly
- **Lưu trữ:** Parquet (chính), CSV (phụ)
- **Đám mây:** Google Cloud Storage (bucket: `gs://bigdata-subject-real-estate-lakehouse`)
- **CI/CD:** Git, Google Compute Engine VM scheduled pipeline

---

## 2. Kiến Trúc Luồng Dữ Liệu

```
                        ┌─────────────────────────┐
                        │  batdongsan.com.vn       │
                        │  (trang tin BĐS)         │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   PHASE 1: CRAWL        │
                        │   Crawl4AI / Requests   │
                        │   + HTML → Text Parser  │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   BRONZE LAYER          │
                        │   raw_html/             │
                        │   raw_text/             │
                        │   raw_json/             │
                        │   metadata/             │
                        │   crawl_log/            │
                        │   (debug/list_pages/)   │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   PHASE 2: BRONZE→SILVER │
                        │   Parser + Normalizer   │
                        │   + Quality Checks      │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   SILVER LAYER          │
                        │   listings.parquet      │
                        │   listings.csv          │
                        │   data_quality_summary  │
                        │   parse_error_log       │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   PHASE 3: SILVER→GOLD  │
                        │   PySpark ETL           │
                        └───────────┬─────────────┘
                                    │
                    ┌───────────────┼───────────────────┐
                    │               │                   │
         ┌──────────▼──────┐ ┌─────▼──────┐ ┌──────────▼──────────┐
         │ gold_current_   │ │ gold_listing│ │ gold_market_by_    │
         │ listings        │ │ _snapshots │ │ district_daily      │
         └─────────────────┘ └────────────┘ └─────────────────────┘
         ┌──────────▼──────┐ ┌─────▼──────┐ ┌──────────▼──────────┐
         │ gold_market_by_ │ │ gold_data_ │ │ gold_removed_       │
         │ property_type   │ │ quality_   │ │ listings            │
         │ _daily          │ │ daily      │ │                     │
         └─────────────────┘ └────────────┘ └─────────────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   PHASE 4: DASHBOARD    │
                        │   Streamlit + Plotly    │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   PHASE 5: ORCHESTRATION│
                        │   GCE VM (scheduled)    │
                        │   → Crawl → Transform   │
                        │   → Validate → Sync GCS │
                        └─────────────────────────┘
```

---

## 3. Cấu Trúc Thư Mục

```
real-estate-crawler/
├── configs/                        # Cấu hình crawl
│   ├── crawl_targets.yaml          # Smoke test (3 targets)
│   ├── crawl_targets_scale.yaml    # Scale batch (3 targets, nhiều page)
│   └── team/                       # Config theo nhóm
│       ├── priority_a_ha_noi.yaml       # 4 quận Hà Nội ưu tiên A
│       └── priority_a_ha_noi_expand_01.yaml  # 6 quận mở rộng
│
├── src/                            # Mã nguồn chính
│   ├── common/                     # Tiện ích dùng chung
│   │   ├── storage.py              # I/O: save_text, save_json, append_jsonl
│   │   ├── logger.py               # Ghi log JSONL
│   │   └── utils.py                # now_utc_iso, today_str, extract_listing_id
│   │
│   ├── crawler/                    # Module crawl
│   │   ├── crawl.py                # Entrypoint chính: run_crawl()
│   │   ├── crawl_config.py         # Đọc & mở rộng cấu hình YAML
│   │   ├── crawl_audit.py          # Audit location/category/seed URL
│   │   ├── fetcher.py              # fetch_html (requests / crawl4ai async)
│   │   ├── parser.py               # html_to_text, extract_phase1_stub_fields
│   │   ├── url_builder.py          # build_seed_url()
│   │   └── parsing/                # Parser chi tiết cho Silver
│   │       ├── batdongsan_parser.py    # extract_title, price, area, location...
│   │       ├── normalizers.py          # Chuẩn hóa giá, diện tích, property_type
│   │       └── quality_checks.py       # apply_quality_flags()
│   │
│   ├── transform/                  # ETL
│   │   ├── bronze_to_silver.py     # Đọc Bronze → Parser → Ghi Silver
│   │   └── silver_to_gold.py       # PySpark: Silver → 6 bảng Gold
│   │
│   └── validation/                 # Kiểm tra chất lượng
│       ├── check_phase3.py         # Validate Gold tables + phase3_summary
│       └── check_gold.py           # Script debug: in schema & sample rows
│
├── dashboard/                      # Streamlit dashboard
│   └── app.py                      # 5 tabs: Overview, Data Quality, Market,
│                                       Listings Explorer, Snapshot Tracking
│
├── scripts/                        # Scripts chạy pipeline
│   ├── run_phase5_pipeline_linux.sh    # Daily pipeline Linux/GCE VM
│   ├── run_phase5_pipeline_windows.ps1 # Helper Windows
│   ├── audit_bronze.py                # Audit Bronze sau crawl
│   ├── backfill_crawl_location_audit.py
│   └── gcs/
│       ├── sync_to_gcs.sh / .ps1      # Upload data → GCS
│       └── sync_from_gcs.sh / .ps1    # Download data từ GCS
│
├── data/                           # Dữ liệu (được tạo khi chạy)
│   ├── bronze/                     # Dữ liệu thô
│   ├── silver/                     # Dữ liệu đã parse
│   ├── gold/                       # Bảng analytics
│   ├── logs/                       # Log pipeline hàng ngày
│   └── debug/                      # Debug list pages
│
├── docs/                           # Tài liệu
│   ├── function.md                 # Chức năng từng file
│   ├── project_overview.md         # (File này)
│   └── real_estate_agent_docs/     # Tài liệu thiết kế chi tiết
│
├── requirements.txt                # Python dependencies
└── README.md                       # Hướng dẫn chính
```

---

## 4. Các Layer Dữ Liệu

### 4.1 Bronze Layer (Dữ liệu thô)

Layout thư mục:
```
data/bronze/source=batdongsan/crawl_date=YYYY-MM-DD/
  crawl_id=<crawl_id>/
    raw_html/listing_id=<id>.html       # HTML gốc của trang chi tiết
    raw_text/listing_id=<id>.txt        # Text đã strip HTML tags
    raw_json/listing_id=<id>.json       # JSON tổng hợp (metadata + extracted)
    metadata/listing_id=<id>.json       # Metadata riêng (crawl context, audit)
    crawl_log/
      crawl_log_<crawl_id>.jsonl        # Log từng request
      crawl_summary_<crawl_id>.json     # Tổng kết crawl
      crawl_location_audit_<crawl_id>.json  # Audit location
      audit_sample_<crawl_id>.csv       # Mẫu audit
```

**Chức năng:** Lưu trữ dữ liệu gốc không thay đổi (raw HTML) để có thể parse lại sau này.

### 4.2 Silver Layer (Dữ liệu đã parse)

Layout thư mục:
```
data/silver/source=batdongsan/crawl_date=YYYY-MM-DD/
  crawl_id=<crawl_id>/
    listings.parquet            # Dữ liệu đã parse (chính)
    listings.csv                # CSV convenience sample
    parse_error_log.csv         # Log lỗi parse
    data_quality_summary.json   # Tổng kết chất lượng
```

**Các bước xử lý:**
1. Đọc metadata + raw HTML/text từ Bronze
2. Parse title, price, area, location, property type bằng `batdongsan_parser.py`
3. Chuẩn hóa giá/diện tích (tỷ → VND, m²)
4. Gắn quality flags (missing, invalid, outlier)
5. Xuất Parquet + CSV

### 4.3 Gold Layer (Bảng Analytics)

Layout thư mục:
```
data/gold/
├── phase3_summary.json                      # Tổng kết Phase 3
├── gold_current_listings/                   # Trạng thái mới nhất mỗi listing
├── gold_listing_snapshots/                  # Lịch sử theo ngày (snapshot_date partition)
├── gold_market_by_district_daily/           # Tổng hợp theo quận + ngày
├── gold_market_by_property_type_daily/      # Tổng hợp theo loại BĐS + ngày
├── gold_data_quality_daily/                 # Chất lượng dữ liệu theo ngày
└── gold_removed_listings/                   # Listing bị gỡ (snapshot_date partition)
```

**6 bảng Gold chi tiết:**

| Bảng | Mục đích | Cột chính |
|------|----------|-----------|
| `gold_current_listings` | Trạng thái hiện tại mỗi listing | dedup_key, snapshot_date, price_vnd, area_m2, is_info_changed, changed_fields |
| `gold_listing_snapshots` | Lịch sử từng listing qua các ngày | dedup_key, snapshot_date, snapshot_status (new/active/changed_price/changed_info/removed), is_new_listing, is_price_changed, changed_fields |
| `gold_market_by_district_daily` | Thống kê thị trường theo quận | snapshot_date, district_norm, listing_count, median_price_vnd, avg_price_vnd, new_listing_count, price_changed_count |
| `gold_market_by_property_type_daily` | Thống kê theo loại BĐS | snapshot_date, property_type_group, listing_count, median_price_vnd, avg_price_vnd |
| `gold_data_quality_daily` | Chất lượng dữ liệu | crawl_date, total_records, parse_success_rate, duplicate_rate, missing_price_rate |
| `gold_removed_listings` | Listing đã biến mất | dedup_key, snapshot_date, last_seen_before_removed, listing_id, title_raw, price_vnd |

**Snapshot status lifecycle:**
```
Listing mới    → "new"
Còn tồn tại    → "active"
Giá thay đổi   → "changed_price"
Thông tin đổi  → "changed_info"
Biến mất       → "removed"
```

---

## 5. Mô Tả Chi Tiết Các Module

### 5.1 Crawler (`src/crawler/`)

| File | Chức năng |
|------|-----------|
| `crawl.py` | Entrypoint chính. Nhận `--config`, lặp qua từng target, fetch listing page → trích danh sách URL → fetch từng detail page → lưu Bronze |
| `fetcher.py` | Hỗ trợ 2 chế độ fetch: `requests` (đồng bộ) và `crawl4ai` (bất đồng bộ). Có retry cho lỗi HTTP 5xx |
| `crawl_config.py` | Đọc YAML, `expand_targets()` nhân bản target cho mỗi category/location, `get_target_*()` helper |
| `crawl_audit.py` | Kiểm tra seed URL redirect, so khớp location (từ detail page, breadcrumb, listing card), phân loại category match, ghi CSV audit |
| `url_builder.py` | Xây URL Batdongsan theo format: `/{category}-{location_path}` |
| `parser.py` | `html_to_text()` chuyển HTML → text đơn giản; `extract_phase1_stub_fields()` trích listing_id |

### 5.2 Parser Chi Tiết (`src/crawler/parsing/`)

| File | Chức năng |
|------|-----------|
| `batdongsan_parser.py` | `parse_listing()` là hàm chính. Trích xuất title, price_raw, area_raw, location_raw, posted_date, bedroom/bathroom count từ raw text và metadata |
| `normalizers.py` | `normalize_price()`: "3.5 tỷ" → 3.500.000.000 VND. `normalize_area()`: "124,5 m²" → 124.5. `calculate_unit_price()`, `normalize_property_type()` |
| `quality_checks.py` | `apply_quality_flags()`: gắn cờ `is_missing_price`, `is_price_negotiable`, `is_missing_area`, `is_missing_location`, `is_invalid_price`, `is_outlier_price`... |

### 5.3 Transform (`src/transform/`)

| File | Chức năng |
|------|-----------|
| `bronze_to_silver.py` | Đọc metadata JSON từ Bronze, gọi `parse_listing()` cho mỗi file, ghi `listings.parquet` + CSV + `data_quality_summary.json` |
| `silver_to_gold.py` | **PySpark job.** Đọc tất cả Silver parquet, dedup, xây lifecycle, snapshot, price change tracking, removed listings, market aggregation. Ghi 6 bảng Gold + `phase3_summary.json` |

### 5.4 Validation (`src/validation/`)

| File | Chức năng |
|------|-----------|
| `check_phase3.py` | Kiểm tra tổng thể Phase 3: phase3_summary.json đủ key, từng bảng Gold tồn tại, đủ cột, đủ hàng, khớp snapshot_date |
| `check_gold.py` | Debug: đọc từng bảng Gold, in schema + 10 dòng mẫu |

### 5.5 Common (`src/common/`)

| File | Chức năng |
|------|-----------|
| `storage.py` | Ghi file text/JSON/JSONL an toàn (tự tạo thư mục cha) |
| `logger.py` | Ghi log JSONL |
| `utils.py` | `now_utc_iso()`, `today_str()`, `extract_listing_id()`, `url_to_hash()` |

---

## 6. Dashboard (Phase 4)

Dashboard Streamlit với 5 tabs:

```
┌──────────────────────────────────────────────────────────────┐
│  Overview │ Data Quality │ Market │ Listings Explorer │ Snapshots│
├──────────────────────────────────────────────────────────────┤
│  - Tổng quan pipeline               │                        │
│  - Số lượng listing hiện tại        │                        │
│  - Chất lượng dữ liệu               │                        │
│  - Xu hướng thị trường              │                        │
│  - Tra cứu listing cá nhân          │                        │
│  - Theo dõi snapshot lifecycle      │                        │
└──────────────────────────────────────────────────────────────┘
```

Chạy: `streamlit run dashboard/app.py` → mở `http://localhost:8501`

---

## 7. Pipeline Hàng Ngày (Phase 5)

Pipeline được scheduled trên GCE VM, script: `scripts/run_phase5_pipeline_linux.sh`

**Luồng chạy:**
```
1. Crawl Bronze (với từng config)
2. Bronze → Silver (parser)
3. Silver → Gold (PySpark)
4. Validate Gold (check_phase3.py)
5. Sync Bronze/Silver/Gold/logs → GCS bucket
6. Ghi daily_run_summary.json
```

**Output mỗi lần chạy:**
```
data/logs/daily_pipeline/
  run_date=YYYY-MM-DD/
    daily_run_summary.json
```

**Các biến môi trường cấu hình:**
- `CRAWL_CONFIGS`: danh sách config (mặc định: `priority_a_ha_noi.yaml,priority_a_ha_noi_expand_01.yaml`)
- `PIPELINE_MODE`: `full` (đầy đủ) hoặc `smoke` (chỉ crawl + Bronze→Silver)
- `SYNC_TO_GCS`: `true`/`false`
- `GCS_BUCKET`: bucket đích

---

## 8. Đồng Bộ Google Cloud Storage

**Bucket:** `gs://bigdata-subject-real-estate-lakehouse`

Layout trên GCS:
```
gs://bigdata-subject-real-estate-lakehouse/
  bronze/     # Append: chỉ crawl_date/crawl_id mới
  silver/     # Append: chỉ crawl_date/crawl_id mới
  gold/       # Mirror (delete unmatched): ghi đè hoàn toàn
  logs/       # Mirror
```

**Sync scripts:**
- `scripts/gcs/sync_to_gcs.sh` / `.ps1` — Upload local lên GCS
- `scripts/gcs/sync_from_gcs.sh` / `.ps1` — Download GCS về local

---

## 9. Crawl Configuration (YAML)

File config mẫu `configs/crawl_targets.yaml`:

```yaml
source: batdongsan.com.vn
base_url: https://batdongsan.com.vn

crawl_settings:
  fetch_mode: crawl4ai
  max_pages_per_target: 1        # Số trang danh sách tối đa
  max_listings_per_target: 10     # Số listing tối đa mỗi target
  request_delay_seconds: 5       # Delay giữa các request
  concurrency: 1                 # Số luồng đồng thời
  stop_on_block: true            # Dừng nếu bị chặn
  max_retries: 1
  retry_delay_seconds: 10

targets:
  - business_type: sale
    category: ban-nha-rieng
    property_type_group: house
    city_slug: tp-ha-noi
    location_path: phuong-cau-giay-tp-ha-noi
    location_label: Cầu Giấy
    priority_group: A
    seed_url: https://batdongsan.com.vn/ban-nha-rieng-phuong-cau-giay-tp-ha-noi
```

---

## 10. Quality Dashboard Metrics

Pipeline theo dõi các chỉ số chất lượng sau mỗi lần chạy:

| Metric | Mô tả | Target |
|--------|-------|--------|
| `crawl_success_rate` | Tỷ lệ crawl detail page thành công | ≥ 0.8 |
| `blocked_count` | Số request bị chặn | 0 hoặc thấp |
| `parse_success_rate` | Tỷ lệ parse Silver thành công | ≥ 0.95 |
| `duplicate_rate` | Tỷ lệ trùng lặp trong crawl_date | ≤ 0.3 |
| `missing_price_rate` | Tỷ lệ thiếu giá | ≤ 0.1 |
| `missing_area_rate` | Tỷ lệ thiếu diện tích | ≤ 0.1 |
| `missing_location_rate` | Tỷ lệ thiếu địa điểm | ≤ 0.05 |

---

## 11. Tính Năng Chính

1. **Crawl tự động** từ batdongsan.com.vn với cấu hình linh hoạt
2. **Audit location/category** tự động sau mỗi lần crawl
3. **Phát hiện chặn (anti-bot)** và dừng an toàn
4. **3-layer lakehouse** (Bronze → Silver → Gold)
5. **Price tracking** qua nhiều snapshot: phát hiện thay đổi giá, thông tin
6. **Phát hiện listing bị gỡ** (removed listings)
7. **Market analytics** theo quận, loại BĐS, thời gian
8. **Dashboard trực quan** trên Streamlit
9. **Pipeline tự động** trên GCE VM với daily_run_summary
10. **Đồng bộ GCS** cho team làm việc nhóm

---

## 12. Các Phase Dự Án

| Phase | Mô tả | Trạng thái |
|-------|-------|------------|
| Phase 1 | Crawl + Bronze layer | ✅ Hoàn thành |
| Phase 2 | Bronze → Silver parser + quality checks | ✅ Hoàn thành |
| Phase 3 | PySpark Silver → Gold ETL + validation | ✅ Hoàn thành |
| Phase 4 | Streamlit dashboard | ✅ Hoàn thành |
| Phase 5 | Pipeline orchestration trên GCE VM | ✅ Hoàn thành |

**Hướng phát triển tương lai:**
- BigQuery + Looker Studio serving layer
- Dataproc / Managed Spark
- Cloud Composer / Airflow orchestration
- ML valuation model
