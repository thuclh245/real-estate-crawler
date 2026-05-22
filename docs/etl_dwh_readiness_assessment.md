# Đánh giá mức độ đáp ứng ETL, DWH và Data Engineering của dự án Real Estate Crawler

Ngày đánh giá: 2026-05-18  
Dự án: `real-estate-crawler`  
Tài liệu đối chiếu:

- Ảnh mô hình ETL gồm Source Systems, Extract, Clean/Conform, Deliver, ETL Management Services, ETL Data Stores, Metadata và Presentation Server.
- File `phan_tich_noi_dung_2_file_VDT_Data_Engineering.md`, tóm tắt các khái niệm Data Integration, ETL/ELT, Batch/Streaming, Data Lake, Data Warehouse, Dimensional Modeling, Fact/Dimension, Bus Matrix, NiFi/Airflow và các yêu cầu vận hành pipeline.
- Repo hiện tại trong `E:\Viscode\real-estate-crawler`.

## 1. Kết luận ngắn

Dự án hiện đã đạt mức **MVP Data Lakehouse batch pipeline khá đầy đủ**:

```text
Batdongsan.com.vn
  -> Crawler
  -> Bronze raw layer
  -> Silver cleaned/enriched layer
  -> Gold analytical layer
  -> Streamlit dashboard
  -> GCS sync
  -> Observability summary/report
```

Tuy nhiên dự án **chưa đạt mức production data platform hoàn chỉnh** nếu xét theo đầy đủ mô hình ETL/DWH trong ảnh và nội dung VDT Data Engineering. Những phần còn thiếu đáng kể là:

- Chưa có nhiều source dữ liệu thực sự.
- Chưa có Airflow/NiFi orchestration.
- Chưa có ML pipeline thực thi.
- Chưa có dimensional model dạng fact/dimension rõ ràng, chỉ mới có Gold analytical tables.
- Cloud mới ở mức GCS + VM, chưa có managed warehouse/orchestrator như BigQuery, Dataproc, Composer.
- Metadata/lineage/governance mới ở mức file path, summary JSON và docs, chưa có metadata repository đúng nghĩa.
- Data quality có nhưng số liệu hiện còn cần cải thiện.

## 2. Bảng đánh giá tổng quan

| Hạng mục | Mức đáp ứng | Bằng chứng hiện có | Nhận xét |
|---|---:|---|---|
| Batch data pipeline | Tốt | `scripts/run_daily_pipeline.sh`, `src/crawler`, `src/transform` | Thiết kế đúng hướng batch ETL/ELT |
| Data Lake/Bronze raw layer | Tốt | `data/bronze/source=...`, raw HTML/text/metadata | Có lưu raw để schema-on-read |
| Silver clean/conform | Tốt | `src/transform/bronze_to_silver.py`, parser, normalizer, enrichment | Đã chuẩn hóa giá, diện tích, location, feature |
| Gold serving layer | Khá | `src/transform/silver_to_gold.py`, `data/gold/*` | Có snapshot, current listings, market aggregates |
| Dashboard/presentation | Khá | `dashboard/app.py` | Có Overview, Quality, Pipeline Health, Market, Listings, Snapshot |
| Observability | Khá | `src/observability`, `data/logs/daily_pipeline`, reports | Đã có summary/report, nhưng chưa alert |
| Data quality | Trung bình-khá | `quality_checks.py`, `gold_data_quality_daily`, reports | Có đo, nhưng parse/missing rates cần cải thiện |
| Metadata/lineage | Trung bình | raw paths, parser version, processed_at, docs | Chưa có metadata repository/lineage graph |
| Multi-source integration | Yếu | Chỉ `batdongsan.com.vn` | Chưa có adapter nguồn khác |
| Airflow/NiFi orchestration | Chưa có | Không có DAG/flow | Script runner chưa thay thế orchestration production |
| ML pipeline | Chưa có thực thi | Có docs ML baseline spec | Chưa có train/evaluate/predict pipeline |
| Cloud-native platform | Trung bình | GCS + VM | Chưa có BigQuery/Composer/Dataproc/Cloud Run/IaC |
| Dimensional modeling | Trung bình | Gold tables có fact-like data | Chưa tách dim_date, dim_location, dim_property_type |
| CI/CD | Yếu | Unit tests local | Chưa có GitHub Actions/Docker/deploy pipeline |

## 3. Đối chiếu với mô hình ETL trong ảnh

### 3.1. Source Systems

Trong ảnh, Source Systems bao gồm operational systems, ERP, user desktops, MDM, external suppliers, RDBMS, flat files, XML, messages, logs và proprietary formats.

Dự án hiện có:

- Website source: `batdongsan.com.vn`.
- Config nguồn crawl: `configs/crawl_targets.yaml`, `configs/team/*.yaml`.
- Raw artifacts: HTML, text, metadata JSON.
- Logs crawler và pipeline.

Mức đáp ứng: **một phần**.

Điểm đạt:

- Đã có external web source.
- Đã có raw HTML/text/metadata tương ứng dữ liệu bán cấu trúc và phi cấu trúc.
- Có log pipeline và crawl.

Điểm thiếu:

- Chưa có nguồn thứ hai như `alonhadat`, `muaban.net`, `chotot`, API, CSV external, log hành vi người dùng.
- Chưa có MDM/reference data riêng cho địa giới hành chính, dự án, chủ đầu tư, tiện ích xung quanh.
- Chưa có source dạng message queue hoặc near-realtime event.

Khuyến nghị:

- Tạo `src/crawler/sources/` với interface chung: `SourceAdapter`, `ListingParser`, `UrlBuilder`.
- Thêm ít nhất một nguồn phụ để chứng minh data integration đa nguồn.
- Thêm reference data: danh mục quận/phường, dự án, tọa độ hoặc POI.

### 3.2. Extract

Trong ảnh, Extract gồm profile data, capture changes, extract.

Dự án hiện có:

- `src/crawler/crawl.py`
- `src/crawler/fetcher.py`
- `src/crawler/url_builder.py`
- Crawl config theo target.
- Bronze raw artifact path theo `source/crawl_date/crawl_id`.

Mức đáp ứng: **khá**.

Điểm đạt:

- Có batch crawler.
- Có crawl id và partition theo ngày.
- Có raw data phục vụ reprocess.

Điểm thiếu:

- Chưa có CDC đúng nghĩa. Dự án đang crawl snapshot theo ngày, chưa capture change tại source.
- Chưa có source profiling report trước khi transform.
- Chưa có retry/backoff/blocked-rate dashboard ở mức hoàn chỉnh.

Khuyến nghị:

- Bổ sung crawl audit summary theo target: requested URLs, success count, failed count, blocked count, duplicate source URLs.
- Lưu crawl profile vào `data/logs/crawl_audit/`.

### 3.3. Clean, Conform

Trong ảnh, Clean/Conform gồm xử lý lỗi dữ liệu, conform dimensions, populate error schema.

Dự án hiện có:

- `src/crawler/parsing/batdongsan_parser.py`
- `src/crawler/parsing/normalizers.py`
- `src/crawler/parsing/quality_checks.py`
- `src/crawler/parsing/feature_extractors.py`
- `src/transform/bronze_to_silver.py`

Mức đáp ứng: **tốt cho MVP**.

Điểm đạt:

- Chuẩn hóa `price_vnd`, `area_m2`, `unit_price_vnd_m2`.
- Chuẩn hóa city/district/ward ở mức parser.
- Có quality flags: missing price, missing area, invalid/outlier price/area.
- Có regex enrichment: legal info, red/pink book, furniture, frontage, car access, business suitability, direction, building name.
- Có parse status và parse error message.

Điểm thiếu:

- Chưa có error schema/quarantine table riêng cho bad records.
- Chưa có conform dimension đúng nghĩa như `dim_location`, `dim_property_type`, `dim_date`.
- Chưa có data contract validation bằng Pandera/Great Expectations.

Số liệu hiện tại từ `data/gold/phase3_summary.json`:

```text
total_silver_records: 9627
total_current_listings: 2722
duplicate_rate: 10.41%
parse_success_rate: 89.34%
missing_price_rate: 10.35%
missing_area_rate: 10.66%
missing_location_rate: 0.00%
```

Nhận xét: có cơ chế đo chất lượng, nhưng `parse_success_rate < 90%` và missing price/area khoảng 10% là điểm cần giải thích hoặc cải thiện.

### 3.4. Deliver

Trong ảnh, Deliver gồm surrogate keys, SCDs, hierarchies, dimension tables, fact tables.

Dự án hiện có Gold tables:

```text
gold_current_listings: 2722 rows
gold_listing_snapshots: 9083 rows
gold_market_by_district_daily: 625 rows
gold_market_by_property_type_daily: 69 rows
gold_data_quality_daily: 17 rows
gold_removed_listings: 3274 rows
```

Mức đáp ứng: **khá nhưng chưa đúng chuẩn dimensional warehouse**.

Điểm đạt:

- Có `dedup_key` như business key ổn định.
- Có snapshot lifecycle: new, active, changed_info, changed_price, removed.
- Có bảng aggregate theo district và property type.
- Có price change và info change tracking.

Điểm thiếu:

- Chưa có surrogate key dạng integer cho fact/dimension.
- Chưa có SCD Type 2 dimension table rõ ràng.
- Chưa tách fact/dimension theo Kimball:
  - `fact_listing_snapshot`
  - `fact_price_change`
  - `dim_date`
  - `dim_location`
  - `dim_property_type`
  - `dim_source`
  - `dim_project`
- Chưa có bus matrix chính thức trong repo.

Khuyến nghị:

- Giữ Gold hiện tại làm analytical marts.
- Thêm một lớp `gold_star_schema/` hoặc `warehouse/` để chứng minh DWH modeling.

### 3.5. ETL Management Services

Trong ảnh, phần này gồm job scheduler/monitor, backup/recovery/restart, version control/migration, data quality workbench, lineage/dependency, problem escalation, parallelizing/pipelining, security/compliance.

Dự án hiện có:

- Script runner: `scripts/run_daily_pipeline.sh`, `scripts/run_daily_pipeline.ps1`.
- Observability: `src/observability/run_summary.py`, `quality_report.py`.
- Pipeline Health dashboard.
- GCS sync scripts.
- Unit tests.

Mức đáp ứng: **trung bình**.

Điểm đạt:

- Có script chạy tuần tự pipeline.
- Có daily summary và data quality report.
- Có tests: 33 tests pass ở lần kiểm tra gần nhất.
- Có sync GCS.

Điểm thiếu:

- Chưa có Airflow/Cloud Composer DAG.
- Chưa có retry policy theo từng task.
- Chưa có alert email/Slack.
- Chưa có task-level SLA.
- Chưa có lineage graph.
- Chưa có secrets/IAM/IaC.
- Chưa có CI/CD.

Khuyến nghị ưu tiên:

```text
1. Thêm Airflow DAG hoặc ít nhất docs/airflow_design.md.
2. Thêm task-level logs và retry config.
3. Thêm alert khi pipeline_status=failed hoặc quality_level=needs_attention.
4. Thêm GitHub Actions chạy unittest.
```

### 3.6. ETL Data Stores

Trong ảnh, ETL Data Stores gồm process history, staged data, snapshot/archive, dimension masters, metadata repository, lookup/decode tables, hierarchy masters, audit dimension data.

Dự án hiện có:

- Bronze: raw/staged source artifacts.
- Silver: cleaned normalized records.
- Gold: snapshot/current/aggregate tables.
- Logs: `data/logs/daily_pipeline`.
- Reports: `data/reports`.
- Docs schema.

Mức đáp ứng: **khá**.

Điểm thiếu:

- Chưa có lookup table chuẩn cho địa giới/dự án/property type.
- Chưa có metadata repository độc lập.
- Chưa có audit dimension data.
- Chưa có retention/archival policy rõ ràng.

### 3.7. Metadata

Trong ảnh, metadata gồm process metadata, technical metadata và business metadata.

Dự án hiện có:

- `parser_version`, `processed_at`
- raw paths: `raw_html_path`, `raw_text_path`, `metadata_path`
- `phase3_summary.json`
- `daily_run_summary.json`
- schema docs trong `docs/schema/`

Mức đáp ứng: **trung bình**.

Thiếu:

- Source descriptions chuẩn hóa.
- Data dictionary đầy đủ cho mọi column.
- Business rule logic mapping đầy đủ.
- ETL job logs có cấu trúc.
- Retention/security metadata.
- Lineage dependency từ Bronze -> Silver -> Gold theo table/column.

Khuyến nghị:

- Tạo `docs/metadata_catalog.md`.
- Tạo `data/metadata/table_catalog.json`.
- Ghi job metadata vào `data/logs/pipeline_runs/*.json`.

### 3.8. Presentation Server

Trong ảnh, Presentation Server gồm dimensional models, aggregate navigation, conformed dimensions/facts.

Dự án hiện có:

- Streamlit dashboard: `dashboard/app.py`.
- Gold tables phục vụ dashboard.
- Market aggregates.
- Pipeline Health tab.

Mức đáp ứng: **khá cho BI dashboard**, **trung bình cho DWH presentation chuẩn**.

Điểm thiếu:

- Chưa có semantic layer hoặc SQL warehouse.
- Chưa có BigQuery dataset.
- Chưa có conformed dimension/fact physical tables.
- Dashboard chạy local, chưa deploy Cloud Run/VM service chính thức.

## 4. Đối chiếu với nội dung VDT Data Engineering

### 4.1. Batch, Near Realtime, Realtime

Dự án hiện là **batch pipeline**. Điều này phù hợp với bài toán crawl bất động sản theo ngày.

Đạt:

- Batch crawler.
- Batch Bronze-to-Silver.
- Batch Silver-to-Gold bằng Spark.
- Batch dashboard refresh theo dữ liệu đã sync.

Chưa có:

- Near realtime.
- Realtime.
- Kafka/Flink/Spark Streaming.

Đánh giá: **đạt nếu mục tiêu là batch analytics**, chưa đạt nếu yêu cầu realtime.

### 4.2. ETL hay ELT

Dự án thực tế là mô hình **ELT/lakehouse lai ETL**:

```text
Extract website
Load raw vào Bronze
Transform Bronze -> Silver
Transform Silver -> Gold
Serve Dashboard
```

Đây là thiết kế phù hợp Data Lake/Lakehouse vì giữ raw data trong Bronze.

Đánh giá: **đạt tốt**.

### 4.3. Volume, Velocity, Variety, Veracity

| Tiêu chí | Hiện trạng | Đánh giá |
|---|---|---|
| Volume | 9627 Silver records, 9083 snapshot rows | Vừa, đủ demo; chưa phải big data lớn |
| Velocity | Batch theo ngày | Phù hợp bài toán |
| Variety | HTML, text, JSON metadata, parquet/csv | Khá, nhưng mới một website |
| Veracity | Có quality checks/report | Có nền tảng, nhưng quality còn cần cải thiện |

### 4.4. Data Lake và Data Warehouse

Data Lake:

- Bronze giữ raw HTML/text/metadata.
- GCS lưu Bronze/Silver/Gold.

Data Warehouse:

- Gold là serving/analytics layer.
- Có aggregate tables.

Đánh giá:

- Data Lake: **khá tốt**.
- Data Warehouse chuẩn dimensional: **chưa hoàn chỉnh**.

### 4.5. Dimensional Modeling

Theo nội dung VDT, cần xác định:

```text
Business process
Grain
Dimensions
Facts
Bus matrix
```

Dự án hiện có thể suy ra:

- Business process: listing crawl, listing snapshot tracking, market price analysis.
- Grain của snapshot: một listing theo một snapshot date.
- Dimensions tiềm năng: date, location, property type, source, project.
- Facts tiềm năng: listing snapshot fact, price change fact, removed listing fact.

Nhưng repo hiện chưa có bảng dim/fact rõ ràng.

Khuyến nghị thiết kế star schema:

```text
dim_date(date_key, date, day, month, quarter, year)
dim_location(location_key, city, district, ward, street)
dim_property_type(property_type_key, property_type_group, business_type)
dim_source(source_key, source_name)
dim_project(project_key, project_name, district, city)

fact_listing_snapshot(
  date_key,
  location_key,
  property_type_key,
  source_key,
  project_key,
  listing_id,
  price_vnd,
  area_m2,
  unit_price_vnd_m2,
  bedroom_count,
  bathroom_count,
  quality_score,
  snapshot_status
)
```

## 5. Các vấn đề lớn của pipeline hiện tại

### 5.1. Nguồn dữ liệu chưa đa dạng

Hiện chỉ có Batdongsan. Trong khi yêu cầu Data Integration thường nhấn mạnh nhiều nguồn.

Tác động:

- Khó chứng minh integration đa nguồn.
- Không có cross-source dedup.
- Không có nguồn bổ sung để kiểm chứng giá.

### 5.2. Chưa có orchestration production

Script runner tốt cho MVP nhưng chưa phải Airflow/NiFi.

Tác động:

- Khó retry từng task.
- Khó backfill có kiểm soát.
- Khó theo dõi dependency và SLA.

### 5.3. ML mới ở mức định hướng

Repo có tài liệu ML baseline trong `docs/real_estate_agent_docs/docs/11_ML_BASELINE_SPEC.md`, nhưng chưa có module train/evaluate/predict.

Thiếu:

- `src/ml/`
- feature table cho ML
- model artifact
- evaluation report
- prediction table
- dashboard tab prediction

### 5.4. Cloud chưa đủ tầng

Đã có GCS và VM, nhưng chưa có:

- BigQuery dataset.
- Cloud Composer/Airflow.
- Dataproc hoặc Serverless Spark.
- Cloud Run dashboard.
- Secret Manager.
- Cloud Monitoring alert.
- Terraform/IaC.

### 5.5. Data quality hiện có cảnh báo thật

Số liệu hiện tại:

```text
parse_success_rate: 89.34%
missing_price_rate: 10.35%
missing_area_rate: 10.66%
duplicate_rate: 10.41%
```

Đây không phải lỗi kiến trúc, nhưng là điểm cần giải thích trong báo cáo. Nếu bảo vệ đồ án, nên có phần phân tích nguyên nhân và kế hoạch cải thiện parser.

### 5.6. Có summary thủ công ngày 2026-05-14

Hiện local có:

```text
data/logs/daily_pipeline/run_date=2026-05-14/daily_run_summary.json
```

File này có `total_silver_records = 0`, tạo để test dashboard. Nếu dùng demo, nên xóa hoặc thay bằng summary thật để tránh Dashboard lấy nhầm run mới nhất.

## 6. Mức độ sẵn sàng theo nhóm tiêu chí

| Nhóm tiêu chí | Điểm ước lượng | Trạng thái |
|---|---:|---|
| Lakehouse layers Bronze/Silver/Gold | 8/10 | Tốt |
| Batch ETL/ELT pipeline | 8/10 | Tốt |
| Data quality/observability | 7/10 | Khá |
| Dashboard/BI | 7/10 | Khá |
| Documentation | 7/10 | Khá |
| DWH dimensional modeling | 5/10 | Trung bình |
| Multi-source integration | 3/10 | Yếu |
| Airflow/NiFi orchestration | 2/10 | Chưa có |
| ML pipeline | 2/10 | Chưa có thực thi |
| Cloud-native production | 4/10 | Trung bình-yếu |
| CI/CD | 3/10 | Yếu |

Tổng thể: **khoảng 6/10 nếu đánh giá theo chuẩn Data Engineering production**, nhưng **8/10 nếu đánh giá như một đồ án batch lakehouse MVP có dashboard và observability**.

## 7. Roadmap đề xuất để đạt chuẩn hơn

### P0 - Cần xử lý trước khi demo/báo cáo

1. Xóa hoặc thay thế summary giả ngày 2026-05-14.
2. Chạy `scripts/run_daily_pipeline.sh --mode smoke` trên VM.
3. Chạy full daily pipeline ít nhất một lần từ runner mới.
4. Sync đủ `gold`, `logs`, `reports` về local.
5. Chụp screenshot dashboard: Overview, Data Quality, Pipeline Health, Listings Explorer, Snapshot Tracking.
6. Viết giải thích cho các chỉ số quality chưa đẹp.

### P1 - Nâng cấp đúng tinh thần ETL/DWH

1. Thêm star schema Gold:
   - `dim_date`
   - `dim_location`
   - `dim_property_type`
   - `dim_source`
   - `fact_listing_snapshot`
2. Thêm bus matrix cho real estate analytics.
3. Thêm metadata catalog.
4. Thêm data contract validation.
5. Thêm source adapter interface để mở rộng nhiều nguồn.

### P2 - Nâng cấp pipeline lớn

1. Thêm Airflow DAG:
   - crawl
   - bronze_to_silver
   - silver_to_gold
   - validate
   - observability
   - gcs_sync
2. Thêm alert khi pipeline fail hoặc quality tụt.
3. Thêm ML baseline:
   - feature generation
   - train/test split theo thời gian
   - model training
   - evaluation
   - prediction output
4. Thêm BigQuery hoặc external table cho Gold.
5. Thêm Dockerfile và CI/CD.

## 8. Câu trả lời trực tiếp: dự án đã đảm bảo các điều trong ảnh và file chưa?

Đã đảm bảo:

- Có luồng Extract -> Clean/Conform -> Deliver ở mức batch.
- Có Bronze/Silver/Gold tương ứng Data Lake/Lakehouse.
- Có raw storage để giữ dữ liệu gốc.
- Có Gold serving tables cho dashboard.
- Có data quality checks và observability.
- Có documentation schema/architecture/report outline.
- Có GCS sync.

Chưa đảm bảo đầy đủ:

- Chưa có nhiều source systems.
- Chưa có Airflow/NiFi scheduler/monitor đúng nghĩa.
- Chưa có metadata repository đầy đủ.
- Chưa có fact/dimension warehouse chuẩn.
- Chưa có SCD/surrogate key đúng chuẩn DWH.
- Chưa có ML pipeline chạy thật.
- Chưa có cloud-native managed architecture.
- Chưa có CI/CD và alerting.

Kết luận: dự án hiện **đảm bảo tốt phần cốt lõi của một batch lakehouse ETL/ELT project**, đủ để trình bày như một đồ án Data Engineering có Bronze/Silver/Gold, dashboard và observability. Nếu muốn đạt chuẩn “pipeline lớn” như trong mô hình ETL enterprise, cần bổ sung orchestration, multi-source, dimensional warehouse, metadata governance, ML pipeline và cloud-native deployment.
