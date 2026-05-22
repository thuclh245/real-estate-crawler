# 07 - Data Quality, Observability, Metadata, and Governance

## Purpose

This document defines cross-stage control requirements. It applies to current Gold outputs, new warehouse tables, multi-source ingestion, orchestration, and BI publication.

## Data Quality Layers

| Layer | Quality focus |
|---|---|
| Bronze | Fetch health, raw artifact completeness, source audit |
| Silver | Parsing, conformance, normalization, required field coverage |
| Gold marts | Snapshot lifecycle logic, dedup, aggregation consistency |
| Warehouse | Grain uniqueness, foreign keys, dimensional conformance |
| Serving | Publish freshness, schema stability, consumer-safe views |

## Quality Rule Classes

### Blocking Rules

Block publication when:

```text
required table missing
fact grain uniqueness fails
required dimension foreign keys fail without unknown member policy
zero records produced for a full expected run without explicit no-data reason
schema contract breaks for published serving table
critical source identity fields are missing
```

### Warning Rules

Warn and publish only when policy permits:

```text
parse success rate falls below target
missing price rate rises above baseline
missing area rate rises above baseline
duplicate rate spikes
blocked crawl rate rises
source coverage shrinks sharply
```

### Informational Rules

Track for diagnosis:

```text
negotiable price rate
outlier price rate
outlier area rate
location confidence mix
source parser version mix
feature extraction coverage
```

## Suggested Threshold Framework

Thresholds should be configuration, not hard-coded across jobs.

```yaml
quality:
  blocking:
    zero_records_for_full_run: true
    warehouse_fk_failure_rate: 0.0
    duplicate_fact_grain_count: 0
  warning:
    parse_success_rate_min: 0.90
    missing_price_rate_max: 0.15
    missing_area_rate_max: 0.15
    duplicate_rate_max: 0.20
```

Threshold values must be reviewed after source onboarding because each source can have different raw field behavior.

## Quarantine

### Quarantine Reasons

```text
parse_exception
required_identity_missing
invalid_schema
invalid_source_mapping
warehouse_fk_reject
invalid_measure_value
```

### Quarantine Record Requirements

```text
quarantine_id
run_id
source_code
input_path
record_identity
rejection_stage
rejection_reason
error_message
parser_version
captured_at
raw_reference_path
```

Rows in quarantine are not silent drops. They remain measurable and inspectable.

## Observability Domains

### Run Metrics

```text
task status
task duration
retry count
input partitions
output partitions
record counts
publish status
```

### Source Metrics

```text
request count
success count
failure count
blocked count
redirect mismatch count
average raw artifact size
parse success rate
```

### Data Metrics

```text
duplicate rate
missing field rates
invalid field rates
warehouse reject rate
freshness
fact and dimension reconciliation counts
```

## Alert Categories

| Alert | Severity |
|---|---|
| Pipeline task failed | High |
| Publish blocked | High |
| Full run produced zero records | High |
| Warehouse validation failed | High |
| Source blocked rate spike | Medium to high |
| Parse success degraded | Medium |
| Missing price or area degraded | Medium |
| Freshness lag | Medium |

## Metadata Catalog

### Table Catalog Fields

```text
table_name
layer
description
business_owner
technical_owner
grain
primary_key_or_business_key
partition_columns
producer_job
input_tables
consumer_outputs
schema_columns
quality_rules
retention_policy
pii_or_sensitive_notes
```

### Job Catalog Fields

```text
job_name
entrypoint
orchestrator_task_id
inputs
outputs
retry_policy
idempotency_notes
validation_rules
publish_behavior
```

## Lineage

Minimum lineage path:

```text
source target
  -> bronze crawl_id and raw artifact
  -> silver normalized row
  -> gold snapshot or current listing
  -> warehouse fact and dimensions
  -> serving view
  -> dashboard or report
```

Every published fact row must retain enough identity to trace back to:

```text
source_code
crawl_date
crawl_id or run scope
listing identity
parser/model version
```

## Retention

Recommended policy categories:

| Data class | Policy intent |
|---|---|
| Bronze raw | Retain long enough for parser reprocessing and audit |
| Silver normalized | Retain historical conformed snapshots |
| Gold marts | Rebuildable but versioned or publish-tracked |
| Warehouse facts | Retain analytical history |
| Logs and reports | Retain run evidence and incident evidence |
| Debug artifacts | Retain selectively to control storage growth |

Exact retention durations should be environment configuration and must account for budget and compliance.

## Sensitive Data Notes

Real estate listing text may contain contact or seller hints. V2 should:

```text
avoid collecting unnecessary personal data
avoid exposing raw contact data in BI reports
document masked or excluded fields
restrict raw Bronze access more tightly than aggregated BI access
```

## Acceptance

```text
[ ] Quality rules are classified as blocking, warning, or informational.
[ ] Thresholds are configuration-controlled.
[ ] Quarantine is measurable.
[ ] Run and source metrics are persisted.
[ ] Metadata catalog covers published tables.
[ ] Lineage is documented from source to BI.
[ ] Alerts are tied to operator action.
```

