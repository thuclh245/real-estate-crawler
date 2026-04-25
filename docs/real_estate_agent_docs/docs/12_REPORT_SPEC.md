# 12 - Report Specification

## Report angle

Write as a Big Data lakehouse platform report, not as a simple web scraping report.

## Recommended structure

```text
1. Introduction
2. Problem Statement
3. Objectives and Scope
4. Functional and Non-functional Requirements
5. Data Sources and Data Challenges
6. System Architecture
7. Data Lakehouse Design
8. Data Schema: Bronze, Silver, Gold
9. Data Processing Pipeline with Spark
10. Snapshot Tracking and Deduplication
11. Data Quality Evaluation
12. Dashboard and Market Analytics
13. Optional ML Baseline
14. Evaluation
15. Limitations
16. Conclusion and Future Work
```

## Must emphasize

```text
Data is listing data, not real transaction data.
Addresses may be incomplete because sellers hide exact locations.
Some prices are negotiable or hidden in description.
Geocoding to exact house location is not guaranteed.
Crawler can be affected by website structure and anti-bot changes.
ML is only baseline, not production valuation.
```

## Required figures

```text
System architecture diagram
Bronze/Silver/Gold data flow
Crawler workflow
Spark ETL workflow
Snapshot and dedup logic
Schema diagram
Dashboard screenshots
Data quality charts
Market analytics charts
Optional ML result chart
```

## Evaluation metrics

Data collection:

```text
crawl_success_rate
records_per_day
failed_crawls
```

Data quality:

```text
parse_success_rate
duplicate_rate
missing_price_rate
missing_area_rate
missing_location_rate
```

Processing:

```text
processing_time_seconds
storage_size_by_layer
number_of_records_processed
```

## Future work

```text
more sources
Delta Lake ACID/time travel
Airflow orchestration
Google Dataproc for Spark
geocoding enrichment
entity resolution across sources
improved valuation model
monitoring and alerting
```
