# Bronze Schema

Bronze stores source artifacts exactly as collected from the website. It is partitioned with Hive-style directories:

```text
data/bronze/source=batdongsan/crawl_date=YYYY-MM-DD/crawl_id=batdongsan_YYYYMMDD_HHMMSS/
```

## Partition Fields

| Field | Type | Description | Example |
|---|---|---|---|
| source | string | Data source name | batdongsan |
| crawl_date | date string | Crawl business date | 2026-05-12 |
| crawl_id | string | Unique crawl execution id | batdongsan_20260512_190002 |

## Artifact Fields

| Field | Type | Description | Example |
|---|---|---|---|
| listing_id | string | Source listing id used in artifact filenames | 30821374 |
| listing_url | string | Listing detail URL | https://batdongsan.com.vn/... |
| raw_html_path | string | Path to raw HTML file | raw_html/listing_id=30821374.html |
| raw_text_path | string | Path to extracted readable text | raw_text/listing_id=30821374.txt |
| metadata_path | string | Path to listing metadata JSON | metadata/listing_id=30821374.json |
| crawl_log_path | string | Optional crawl log path | crawl_log/crawl_summary.json |
| fetched_at | timestamp string | Time artifact was fetched when available | 2026-05-12T19:45:20+00:00 |
| status | string | Crawl status when available | success |

Bronze is intentionally append-only. Downstream layers should not mutate Bronze files.
