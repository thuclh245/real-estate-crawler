# 00 - V2 Scope, Baseline, and Success Criteria

## Product Goal

Version 2 turns the current project into a production-oriented batch data platform for real estate listing analytics.

The target is not only a project demo. The target is a system that can be operated repeatedly, audited, validated, extended to new sources, and consumed by BI users without depending on manual inspection of local folders.

## Current Baseline

The repo already has a useful MVP foundation:

```text
Batdongsan crawler
  -> Bronze raw HTML/text/JSON/metadata/log
  -> Silver parser and feature enrichment
  -> Spark Silver-to-Gold transform
  -> Gold analytical tables
  -> Streamlit dashboard
  -> Daily run summary and quality report
  -> GCS sync helpers
```

Current production-relevant code and data paths include:

```text
src/crawler/
src/transform/bronze_to_silver.py
src/transform/silver_to_gold.py
src/validation/check_phase3.py
src/observability/
dashboard/app.py
scripts/run_daily_pipeline.sh
scripts/run_daily_pipeline.ps1
data/bronze/
data/silver/
data/gold/
data/logs/daily_pipeline/
```

Current Gold analytical outputs are:

```text
gold_current_listings
gold_listing_snapshots
gold_market_by_district_daily
gold_market_by_property_type_daily
gold_data_quality_daily
gold_removed_listings
```

These outputs stay supported in v2 because they already serve Streamlit and validation.

## Baseline Findings That V2 Must Address

| Gap | Current state | V2 requirement |
|---|---|---|
| DWH dimensional model | Analytical Gold exists, fact and dimension tables do not | Add explicit warehouse star schema |
| Multi-source integration | Batdongsan is the production path; Alonhadat/Nhatot are test scripts and test data | Add source adapter contract and promote validated sources |
| Orchestration | Script runner and scheduled VM exist | Add task-level orchestration, retries, backfills, and dependency visibility |
| CI/CD | Local unit tests exist | Add automated validation and deployment controls |
| Metadata and lineage | Raw paths, parser version, summaries, and docs exist | Add table catalog, job metadata, lineage, and retention rules |
| Data quality | Quality flags and metrics exist | Add contracts, thresholds, quarantine, trend alerts, and exception handling |
| Serving | Local Streamlit reads Gold | Add governed BI serving path, preferably BigQuery plus Power BI |
| Operational safety | Some manual summaries and local runtime assumptions exist | Remove invalid demo artifacts from production decision logic |

## Production Definition for V2

V2 is production-ready only when all of the following are true:

1. A daily batch can be orchestrated end to end without manual handoff between crawl, transform, validate, publish, and report steps.
2. A failed task can be retried or backfilled without corrupting Bronze history or leaving ambiguous Gold outputs.
3. Data consumers can query a stable DWH model with documented fact grain, dimensions, measures, and source lineage.
4. Source onboarding does not require copying the Batdongsan pipeline and editing hard-coded paths across the repo.
5. Data quality failures are measured, classified, and visible before data is promoted to BI serving tables.
6. Operational evidence exists for each run: run id, source set, task status, record counts, quality metrics, and published outputs.
7. Dashboard consumers are separated from engineering diagnostics:
   - Power BI serves business analytics.
   - Streamlit remains available for pipeline health, data quality inspection, and listing exploration.

## Priority Order

The v2 priority is ordered by production risk:

1. Correctness and run safety.
2. Stable DWH contracts.
3. Source extensibility and conformance.
4. Orchestration and cloud operation.
5. BI serving and user-facing reporting.
6. Optional ML production extension after data contracts are stable.

## In Scope

```text
Batch source ingestion
Source adapter architecture
Bronze raw retention
Silver normalized listing contract
Warehouse star schema
Gold analytical marts compatibility
Quality gates and quarantine
Metadata catalog and lineage
Airflow DAG and CI/CD
GCS and BigQuery publication path
Power BI semantic model and reports
Operational runbook and acceptance checks
```

## Out of Scope for Core V2

These topics are useful, but they must not block the core v2 production path:

```text
Realtime crawling or streaming
Automated CAPTCHA bypass
Exact property geocoding for every listing
Actual transaction price truth
High-accuracy valuation model
Mobile app or public customer portal
Full enterprise data governance platform
```

## V2 Success Evidence

The final v2 implementation must produce evidence artifacts:

| Evidence | Minimum artifact |
|---|---|
| End-to-end run | Airflow run summary or equivalent task-level run record |
| Data quality | Rule results, thresholds, quarantined exceptions, quality report |
| DWH model | Fact and dimension tables plus schema docs and bus matrix |
| Multi-source | At least two sources promoted through Bronze, Silver, warehouse, and BI outputs |
| BI serving | Power BI dataset/report connected to stable serving tables |
| Operations | Runbook, backfill instructions, alert conditions, recovery path |
| Automation | CI test result and deployment/publish controls |

## Naming and Compatibility Rules

1. Current analytical Gold table names stay valid for v2 compatibility.
2. New DWH tables should live in a distinct warehouse namespace or folder.
3. Source names must be normalized and stable across Bronze, Silver, Gold, warehouse, logs, and BI.
4. Every published table must define primary business keys, grain, partitions, required columns, and nullability rules.

