# Chức năng thư mục và file (tóm tắt + chi tiết `src`)

Tập hợp mô tả ngắn gọn cho các thư mục rồi đi sâu vào chức năng từng file chính trong `src/`.

## Tổng quan thư mục

- `README.md`: Hướng dẫn thiết lập, lệnh chạy và mô tả các phase của pipeline.
- `requirements.txt`: Danh sách dependency Python cho môi trường dev.
- `configs/`: chứa cấu hình crawl (`crawl_targets.yaml`, `crawl_targets_scale.yaml`).
- `data/`: nơi lưu Bronze / Silver / Gold theo layout lakehouse.
- `docs/`: tài liệu kỹ thuật và quy trình cho nhóm.
- `scripts/`: orchestration, audit và helper (Linux/Windows).
- `scripts/gcs/`: helper `sync_to_gcs` / `sync_from_gcs` dùng `gcloud storage`.

## Mô tả chi tiết các file trong `src/`

`src/common/utils.py`

- Hàm: `now_utc_iso()`, `today_str()`, `extract_listing_id()`, `url_to_hash()`, `get_listing_id_or_hash()`.
- Mục đích: tiện ích liên quan thời gian và định danh listing (tách ID từ URL hoặc hash).

`src/common/storage.py`

- Hàm: `ensure_dir()`, `save_text_file()`, `save_json_file()`, `append_jsonl()`.
- Mục đích: thao tác I/O an toàn (tạo thư mục cha, ghi text/JSON/JSONL).

`src/common/logger.py`

- Hàm: `append_jsonl()` để ghi log JSONL (tạo thư mục cha nếu cần).

`src/crawler/crawl.py`

- Chứa entrypoint crawler và logic chính thu thập trang danh sách và chi tiết, trích URLs, lưu HTML/raw, metadata, và crawl summary.
- Hàm/khối quan trọng: `make_crawl_id()`, `is_blocked_page()`, `save_list_page_debug()`, `parse_detail_page_location_fields()`, `extract_listing_entries_from_listing_page()`, `run_crawl()`.

`src/crawler/fetcher.py`

- Hàm: `fetch_with_retry()`, `fetch_html_requests()`, `fetch_html_crawl4ai()`.
- Mục đích: lấy HTML với retry; hỗ trợ chế độ `requests` và `crawl4ai` (async).

`src/crawler/parser.py`

- Hàm: `html_to_text()`, `extract_listing_id()`, `extract_phase1_stub_fields()`.
- Mục đích: chuyển HTML → text cho Bronze và trích các trường stub giai đoạn 1.

`src/crawler/crawl_config.py`

- Hàm: `load_config()`, `expand_targets()`, `get_target_city()`, `get_target_location_path()`, `get_target_location_slug()`, `get_target_location_label()`.
- Mục đích: đọc YAML config và sinh danh sách target cho crawler.

`src/crawler/crawl_audit.py`

- Nhiều hàm audit/normalization: `normalize_text()`, `validate_seed_url()`, `check_location_match()`, `audit_location()`, `write_audit_sample_csv()`.
- Mục đích: xác thực seed URL, so khớp location/category, ghi sample audit CSV và in cảnh báo lỗi.

`src/crawler/url_builder.py`

- Hàm: `build_seed_url(base_url, category_slug, location_path, page_number)`.
- Mục đích: xây URL trang danh sách theo form `/{category}-{location}` và trang số.

`src/crawler/parsing/batdongsan_parser.py`

- Các hàm trích xuất và parse: `extract_title()`, `extract_price_raw()`, `extract_area_raw()`, `extract_location_raw()`, `extract_posted_date_raw()`, `extract_bedroom_count()`, `extract_bathroom_count()`, `parse_listing()`.
- Mục đích: chuyển raw HTML/text + metadata từ Bronze thành record normalized cho Silver (giá, diện tích, location, property_type, seller info, v.v.).

`src/crawler/parsing/normalizers.py`

- Hàm: `clean_text()`, `parse_vietnamese_number()`, `normalize_price()`, `normalize_area()`, `calculate_unit_price()`, `calculate_total_price()`, `normalize_property_type()`.
- Mục đích: chuẩn hoá chuỗi giá/diện tích và tính toán đơn vị/giá trị số.

`src/crawler/parsing/quality_checks.py`

- Hàm: `apply_quality_flags(record)`.
- Mục đích: gắn cờ chất lượng trên mỗi record Silver (missing price/area/location, outliers, parse_status).

`src/transform/bronze_to_silver.py`

- Hàm chính: `run_bronze_to_silver(bronze_dir, silver_dir, parser_version)`.
- Mục đích: đọc metadata và raw files từ Bronze, gọi parser để tạo records, ghi `listings.parquet`, `listings.csv`, `parse_error_log.csv` và `data_quality_summary.json` trong Silver.

`src/transform/silver_to_gold.py`

- PySpark job: `create_spark()`, `read_silver()`, `add_dedup_key()`, `build_listing_lifecycle()`, `ensure_columns()` và nhiều bước chuyển đổi/aggregate.
- Mục đích: từ Silver tạo các bảng Gold: `gold_current_listings`, `gold_listing_snapshots`, `gold_market_by_district_daily`, `gold_market_by_property_type_daily`, `gold_data_quality_daily`, `gold_removed_listings`.

`src/validation/check_phase3.py`

- Kiểm tra `phase3_summary.json` và các bảng Gold tồn tại, có các cột tối thiểu và số lượng hàng mong đợi. Hàm entrypoint `main()` thực hiện validation dùng Spark.

`src/validation/check_gold.py`

- Script debug: in schema và show sample rows cho các bảng Gold (dùng Spark) — hữu ích khi inspect/output review.

## Muốn mở rộng?

- Tôi có thể thêm các ví dụ lệnh `python -m ...` (copy-ready) vào cuối file, hoặc sinh một bảng mapping `module -> CLI command` để dễ chạy từng bước. Bạn muốn tôi thêm lệnh mẫu không?
