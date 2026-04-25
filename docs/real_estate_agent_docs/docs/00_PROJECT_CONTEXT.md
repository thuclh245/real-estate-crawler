# 00 - Project Context

## Project name

**A Big Data Lakehouse Platform for Real Estate Listings and Market Analytics in Vietnam**

## Main goal

Xây dựng một nền tảng dữ liệu Big Data kiểu lakehouse cho dữ liệu tin đăng bất động sản. Trọng tâm là data engineering/platform, không phải chỉ scrape CSV hay chỉ làm ML.

Pipeline tổng quát:

```text
Web sources
  -> Crawler
  -> Bronze: raw HTML / raw text / metadata JSON / crawl log
  -> Spark Batch ETL
  -> Silver: cleaned standardized listing snapshots
  -> Snapshot tracking + Deduplication
  -> Gold: analytics tables
  -> Dashboard + optional ML baseline
```

## Scope đã chốt

```text
Main analysis: Hà Nội
Technical scale extension: Toàn Việt Nam
Primary source: batdongsan.com.vn
Future sources: alonhadat, nhatot, muabannhadat
Crawl style: daily batch snapshot, not real-time streaming
Storage style: Bronze/Silver/Gold lakehouse
Processing: Spark batch ETL
Dashboard: data quality + market overview + district analysis + trend
ML: optional baseline using clean Gold subset
ML target: unit_price_vnd_m2
```

## Course alignment

Dự án cần thể hiện đúng tinh thần Big Data:

- Data lifecycle: raw -> cleaned -> curated.
- Distributed/batch processing with Spark.
- Scalable storage design: local prototype, later GCS/HDFS/object storage.
- Traceability: crawl_id, crawl_date, source, metadata, lineage.
- Quality management: missing flags, duplicate rate, parse success.
- Reprocessing: raw HTML retained in Bronze.

## Key argument for report

Không nên bảo vệ dự án bằng câu “dataset cực lớn”. Nên bảo vệ bằng logic:

> Dữ liệu tin đăng bất động sản có volume tăng theo snapshot, variety do nhiều loại tài sản/nhiều kiểu giá/nhiều nguồn, veracity do missing values/duplicates/noisy text, và value qua dashboard/market analytics/ML baseline. Vì vậy cần lakehouse, Spark ETL, data quality monitoring và snapshot tracking.

## In scope

- Crawl listing pages and detail pages where permitted.
- Store raw HTML/text/metadata/log in Bronze.
- Parse and standardize data into Silver.
- Deduplicate and track listing lifecycle.
- Build Gold analytics tables.
- Build dashboard.
- Optional baseline valuation model.

## Out of scope for v1

- Real-time streaming pipeline.
- Exact house-level geocoding/GPS.
- Downloading real images.
- Full MLOps/online serving.
- Enterprise-grade deployment.
- Bypassing CAPTCHA or anti-bot protections.
