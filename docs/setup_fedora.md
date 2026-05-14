# Hướng Dẫn Chạy Dự Án Real Estate Lakehouse trên Fedora 43

> Fedora 43 — Python 3.14.4 — OpenJDK 21

## Mục lục

1. [Setup môi trường](#1-setup-môi-trường)
2. [Crawl dữ liệu (Phase 1)](#2-crawl-dữ-liệu-phase-1)
3. [Bronze → Silver (Phase 2)](#3-bronze--silver-phase-2)
4. [Silver → Gold với PySpark (Phase 3)](#4-silver--gold-với-pyspark-phase-3)
5. [Dashboard (Phase 4)](#5-dashboard-phase-4)
6. [Pipeline tự động (Phase 5)](#6-pipeline-tự-động-phase-5)
7. [Đồng bộ GCS](#7-đồng-bộ-gcs)
8. [Tổng kết lệnh nhanh](#8-tổng-kết-lệnh-nhanh)
9. [Khắc phục sự cố](#9-khắc-phục-sự-cố)

---

## 1. Setup môi trường

### 1.1. Tạo virtual environment

```bash
cd /home/nhatdoankhanh/Project/Bigdata/real-estate-crawler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

### 1.2. Cài dependencies

> **Lưu ý Fedora 43:** `pyarrow` phải cài dạng binary wheel (tránh lỗi build từ source).

```bash
# Cài pyarrow riêng (binary, không build từ source)
pip install pyarrow --only-binary :all:

# Cài toàn bộ package còn lại
pip install crawl4ai==0.8.6 plotly==6.1.2 streamlit==1.45.1 \
  requests==2.33.1 beautifulsoup4==4.14.3 lxml==5.4.0 \
  PyYAML==6.0.3 pandas==2.2.3 python-dateutil==2.9.0.post0
```

### 1.3. Cài trình duyệt cho crawl4ai

```bash
python -m playwright install chromium
```

### 1.4. Kiểm tra

```bash
python -c "from crawl4ai import AsyncWebCrawler; print('crawl4ai OK')"
python -c "import pandas; import pyarrow; print('pandas + pyarrow OK')"
python -c "import streamlit; print('streamlit OK')"
```

---

## 2. Crawl dữ liệu (Phase 1)

### 2.1. Crawl

```bash
source .venv/bin/activate
export PYTHONPATH=src

# Smoke test (3 targets, 10 listings mỗi target)
python -m crawler.crawl --config configs/crawl_targets.yaml
```

**Các config có sẵn:**

| Config | Mục đích | Số lượng |
|--------|----------|----------|
| `configs/crawl_targets.yaml` | Smoke test nhỏ | 3 targets x 10 = ~30 listings |
| `configs/crawl_targets_scale.yaml` | Scale vừa | 3 targets x 30 listings x 3 pages |
| `configs/team/priority_a_ha_noi.yaml` | Hà Nội ưu tiên A | 4 quận x 4 loại = ~320 listings |
| `configs/team/priority_a_ha_noi_expand_01.yaml` | Hà Nội mở rộng | 6 quận x 4 loại = ~480 listings |

### 2.2. Lưu crawl_id

Sau khi chạy, terminal in ra `crawl_id`. Ví dụ:

```
crawl_id=batdongsan_20260510_104550
```

Dùng `crawl_id` này cho các bước tiếp theo. Có thể xem lại bằng:

```bash
ls -d data/bronze/source=batdongsan/crawl_date=*/crawl_id=*/
```

### 2.3. Audit kết quả crawl (tuỳ chọn)

```bash
python scripts/audit_bronze.py --crawl-id batdongsan_20260510_104550
```

### 2.4. Kiểm tra dữ liệu Bronze đã crawl

```bash
find data/bronze -type f | head -20
```

**Cấu trúc Bronze output:**

```
data/bronze/source=batdongsan/crawl_date=YYYY-MM-DD/
  crawl_id=<crawl_id>/
    raw_html/listing_id=<id>.html     # HTML gốc từng trang chi tiết
    raw_text/listing_id=<id>.txt      # Text đã strip HTML
    raw_json/listing_id=<id>.json     # JSON tổng hợp
    metadata/listing_id=<id>.json     # Metadata crawl
    crawl_log/
      crawl_summary_<crawl_id>.json   # Tổng kết crawl
      crawl_log_<crawl_id>.jsonl      # Log từng request
```

---

## 3. Bronze → Silver (Phase 2)

Chuyển dữ liệu thô (Bronze) thành dữ liệu đã parse, chuẩn hóa (Silver).

```bash
source .venv/bin/activate
export PYTHONPATH=src

# Thay <crawl_date> và <crawl_id> từ bước crawl
python -m transform.bronze_to_silver \
  --bronze-dir data/bronze/source=batdongsan/crawl_date=2026-05-10/crawl_id=batdongsan_20260510_104550 \
  --silver-dir data/silver/source=batdongsan/crawl_date=2026-05-10/crawl_id=batdongsan_20260510_104550
```

**Kết quả:** (terminal in ra `data_quality_summary.json`)

```
data/silver/source=batdongsan/crawl_date=YYYY-MM-DD/
  crawl_id=<crawl_id>/
    listings.parquet            # File chính (Parquet)
    listings.csv                # CSV sample
    data_quality_summary.json   # Chất lượng dữ liệu
    parse_error_log.csv         # Lỗi parse nếu có
```

**Các chỉ số quan trọng trong `data_quality_summary.json`:**

| Chỉ số | Target | Ý nghĩa |
|--------|--------|---------|
| `parse_success_rate` | ≥ 0.95 | Tỷ lệ parse thành công |
| `is_missing_price_rate` | ≤ 0.1 | Tỷ lệ thiếu giá |
| `is_missing_area_rate` | ≤ 0.1 | Tỷ lệ thiếu diện tích |

---

## 4. Silver → Gold với PySpark (Phase 3)

### 4.1. Cài PySpark

```bash
source .venv/bin/activate
pip install pyspark py4j
```

### 4.2. Chạy Gold ETL

```bash
source .venv/bin/activate
export PYTHONPATH=src
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk
export PATH="$JAVA_HOME/bin:$PATH"

python -m transform.silver_to_gold
```

**Quá trình này:**
1. Đọc tất cả Silver parquet files
2. Tạo `dedup_key` cho mỗi listing
3. Dedup theo từng ngày
4. Xây lifecycle: `first_seen_date`, `last_seen_date`, `active_days`
5. Tạo snapshot với status: `new`, `active`, `changed_price`, `changed_info`, `removed`
6. Tính aggregation thị trường (theo quận, loại BĐS)

### 4.3. Output Gold

```
data/gold/
├── phase3_summary.json                    # Tổng kết
├── gold_current_listings/                 # Trạng thái mới nhất
├── gold_listing_snapshots/                # Lịch sử theo ngày
├── gold_market_by_district_daily/         # Thống kê theo quận
├── gold_market_by_property_type_daily/    # Thống kê theo loại BĐS
├── gold_data_quality_daily/               # Chất lượng dữ liệu
└── gold_removed_listings/                 # Listing bị gỡ
```

### 4.4. Validate Gold

```bash
python -m validation.check_phase3
```

Kết quả mong đợi:
```
PASS: phase3_summary.json
PASS: gold_current_listings rows=...
PASS: gold_listing_snapshots rows=...
...
PASS: Phase 3 validation checklist
```

### 4.5. Debug (tuỳ chọn)

```bash
python -m validation.check_gold
```

---

## 5. Dashboard (Phase 4)

```bash
source .venv/bin/activate
streamlit run dashboard/app.py
```

Mở trình duyệt tại: **http://localhost:8501**

**Các tab:**
| Tab | Chức năng |
|-----|-----------|
| Overview | Tổng quan pipeline, số listing, snapshot dates |
| Data Quality | Chất lượng dữ liệu theo ngày |
| Market | Biểu đồ giá/diện tích theo quận, loại BĐS |
| Listings Explorer | Tra cứu chi tiết từng listing |
| Snapshot Tracking | Theo dõi lifecycle listing |

---

## 6. Pipeline tự động (Phase 5)

Script chạy toàn bộ pipeline từ crawl → Silver → Gold → Validate → GCS.

### 6.1. Chạy full pipeline

```bash
source .venv/bin/activate
export PYTHONPATH=src
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk

chmod +x scripts/run_phase5_pipeline_linux.sh
bash scripts/run_phase5_pipeline_linux.sh
```

### 6.2. Các tuỳ chọn

```bash
# Smoke test (chỉ crawl + Bronze→Silver, dừng sớm)
export PIPELINE_MODE=smoke
bash scripts/run_phase5_pipeline_linux.sh

# Chạy với config tuỳ chỉnh
export CRAWL_CONFIGS=configs/crawl_targets.yaml
bash scripts/run_phase5_pipeline_linux.sh

# Không sync GCS
export SYNC_TO_GCS=false
bash scripts/run_phase5_pipeline_linux.sh
```

### 6.3. Kết quả pipeline

Sau mỗi lần chạy, log được ghi tại:

```
data/logs/daily_pipeline/
  run_date=YYYY-MM-DD/
    daily_run_summary.json
```

---

## 7. Đồng bộ GCS

### 7.1. Cài Google Cloud CLI

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://packages.cloud.google.com/yum/repos/google-cloud-cli-dnf
sudo dnf install -y google-cloud-cli
```

### 7.2. Đăng nhập

```bash
gcloud auth login --no-launch-browser
gcloud config set project bigdata-subject
```

### 7.3. Upload data

```bash
bash scripts/gcs/sync_to_gcs.sh
```

### 7.4. Tải data từ GCS về

```bash
bash scripts/gcs/sync_from_gcs.sh
```

---

## 8. Tổng kết lệnh nhanh

```bash
# === 1. Kích hoạt môi trường ===
source .venv/bin/activate
export PYTHONPATH=src

# === 2. Crawl ===
python -m crawler.crawl --config configs/crawl_targets.yaml

# === 3. Bronze → Silver ===
# (thay crawl_date và crawl_id)
python -m transform.bronze_to_silver \
  --bronze-dir data/bronze/source=batdongsan/crawl_date=2026-05-10/crawl_id=batdongsan_20260510_104550 \
  --silver-dir data/silver/source=batdongsan/crawl_date=2026-05-10/crawl_id=batdongsan_20260510_104550

# === 4. Gold ETL ===
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk
export PATH="$JAVA_HOME/bin:$PATH"
python -m transform.silver_to_gold

# === 5. Validate ===
python -m validation.check_phase3

# === 6. Dashboard ===
streamlit run dashboard/app.py
```

---

## 9. Khắc phục sự cố

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| `Failed building wheel for pyarrow` | PyArrow build từ source thiếu Arrow C++ | `pip install pyarrow --only-binary :all:` |
| `ModuleNotFoundError: No module named 'crawl4ai'` | Chưa cài crawl4ai | `pip install crawl4ai==0.8.6` |
| `JAVA_HOME is not set` | Thiếu Java hoặc chưa set biến | `export JAVA_HOME=/usr/lib/jvm/java-21-openjdk` |
| `JAVA_GATEWAY_EXITED` | PySpark không tìm thấy Java | Kiểm tra `java -version`, set đúng `JAVA_HOME` |
| `No module named 'py4j'` | PySpark thiếu py4j | `pip install pyspark py4j` |
| Python không tìm thấy module `src` | Thiếu PYTHONPATH | `export PYTHONPATH=src` |
| `.venv/bin/activate: No such file or directory` | Chưa tạo venv | `python3 -m venv .venv` |
| crawl4ai chặn, http 403/429 | Batdongsan chống crawl | Kiểm tra `stop_on_block`, tăng `request_delay_seconds` |
| Gold table validation fail | File Gold cũ | Chạy lại `silver_to_gold`, xoá `data/gold/` cũ |
