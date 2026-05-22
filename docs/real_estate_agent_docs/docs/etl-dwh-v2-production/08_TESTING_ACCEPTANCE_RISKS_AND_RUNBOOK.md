# 08 - Testing, Acceptance, Risks, and Runbook

## Test Strategy

V2 needs tests at more than one level.

| Test layer | Purpose |
|---|---|
| Unit | Parsers, normalizers, feature rules, quality logic, summary generation |
| Contract | Bronze metadata, Silver schema, warehouse facts/dimensions, serving views |
| Integration | Source crawl fixture to Bronze, Bronze to Silver, Silver to warehouse |
| End-to-end | Orchestrated daily run with publish decision |
| Regression | Prevent known source/parser/summary failures from returning |
| BI validation | Relationship model, filters, data freshness, metric reconciliation |

## Required Automated Checks

```text
[ ] Existing unit test suite remains green.
[ ] Source parser fixtures cover each promoted source.
[ ] Warehouse fact grain uniqueness test exists.
[ ] Warehouse dimension member uniqueness test exists.
[ ] Reconciliation test compares validated snapshot output to warehouse fact count.
[ ] Serving schema test prevents breaking Power BI dependencies.
[ ] Run summary validator rejects invalid production evidence.
```

## Acceptance Pack

The final production acceptance pack should include:

```text
run manifest for a successful production-class batch
task-level orchestration evidence
quality report and threshold result
warehouse schema docs
bus matrix
table catalog
Power BI report screenshots or report artifact
Streamlit operations screenshots
backfill test evidence
CI result
risk review
runbook
```

## System Acceptance Checklist

### Pipeline

```text
[ ] Multiple runs do not overwrite Bronze history.
[ ] Reprocessing can start from Bronze.
[ ] Validated Silver promotes to Gold and warehouse.
[ ] Invalid data is flagged or quarantined.
[ ] Publish path records success or block reason.
```

### DWH

```text
[ ] Fact and dimension grains are documented.
[ ] Foreign keys resolve or use explicit unknown members.
[ ] Dates, sources, locations, and property types are conformed.
[ ] Power BI can use facts and dimensions without raw parser logic.
```

### Multi-Source

```text
[ ] Batdongsan remains stable.
[ ] At least one additional source is production-promoted.
[ ] Source comparison is possible without losing lineage.
[ ] Cross-source matching does not erase source listing identity.
```

### Orchestration and Cloud

```text
[ ] Airflow or production orchestrator shows task status.
[ ] Retries and backfills are documented.
[ ] CI covers core tests and contracts.
[ ] IAM and secrets are documented.
[ ] BigQuery serving data is refreshed only after validation.
```

### BI

```text
[ ] Power BI uses stable serving data.
[ ] Core KPI measures reconcile with warehouse data.
[ ] Filters for date, district, property type, and source work.
[ ] Data freshness is visible.
[ ] Streamlit remains useful for technical inspection.
```

## Risk Register

| Risk | Impact | Mitigation | Owner focus |
|---|---|---|---|
| Source HTML changes | Parser failure and missing fields | Bronze retention, parser fixtures, source scorecards | Ingestion |
| Anti-bot restrictions | Failed or blocked crawls | Rate limit, approved fetch modes, blocked detection, no bypass policy | Ingestion |
| Multi-source field mismatch | Invalid comparisons | Conformed Silver contract and source mapping tests | Modeling |
| Cross-source false dedup | Wrong market metrics | Preserve source identity and use candidate matching first | Modeling |
| Summary/test artifact confusion | Wrong latest run view | Run class, publish state, summary filters | Operations |
| Spark runtime drift | Gold or warehouse failure | Preflight, pinned runtime, CI fixtures | Platform |
| BI schema drift | Broken reports | Serving views and schema contract tests | BI |
| Cloud permission gap | Publish failure | IAM design and deployment check | Platform |
| Quality degradation | Misleading analytics | Thresholds, alerts, quarantine, trend reports | Data quality |

## Incident Categories

```text
source access failure
parser regression
data quality publish block
warehouse validation failure
cloud publish failure
BI refresh failure
```

## Runbook Outline

### Daily Run

```text
1. Confirm orchestrator run state.
2. Check source crawl scorecards.
3. Check Silver and warehouse validation.
4. Confirm publish status.
5. Review alerts and data freshness.
```

### Failed Crawl

```text
1. Identify source and target scope.
2. Inspect blocked, failed, and redirect audit metrics.
3. Preserve failed raw evidence.
4. Decide retry, reduce scope, or defer source publication.
```

### Parser Regression

```text
1. Compare parser fixture failures and missing field spikes.
2. Reprocess affected Bronze partitions after parser fix.
3. Rebuild Silver, Gold, and warehouse for affected scope.
4. Republish only after validation.
```

### Warehouse Rebuild

```text
1. Freeze serving publish if schema is changing.
2. Rebuild dimensions.
3. Rebuild facts.
4. Validate fact grain, FK integrity, and reconciliation.
5. Refresh serving views and BI only after checks pass.
```

### BI Refresh Failure

```text
1. Check serving dataset freshness.
2. Check Power BI credentials and schema compatibility.
3. Confirm no publish block occurred upstream.
4. Re-run refresh after upstream state is valid.
```

## Final Readiness Statement

Use this statement only after the checklist is satisfied:

```text
V2 is production-ready for batch real estate listing analytics because it provides controlled ingestion, conformed Silver data, dimensional warehouse contracts, validated publication, multi-source lineage, observable orchestration, governed BI serving, and documented recovery procedures.
```

