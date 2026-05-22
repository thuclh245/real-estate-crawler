# 02 - Stage 1 Production Foundation

## Objective

Stage 1 hardens the current Batdongsan batch path before new warehouse tables, sources, and dashboards depend on it.

The key rule is:

```text
Do not scale architecture on top of ambiguous run evidence.
```

## Current Issues to Close First

| Issue | Production impact | Required handling |
|---|---|---|
| Manual summary for `2026-05-14` reports success with zero records | Dashboard and operators may treat a test artifact as latest production run | Delete, archive, mark non-production, or change summary selection rules |
| Runtime assumptions differ by interpreter | Local tests and operators can fail from missing packages | Document and enforce venv/runtime checks |
| PySpark and Java are required for Gold validation | Pipeline can pass crawl steps but fail at Gold | Add dependency preflight |
| Validation is strong for current Gold but not full v2 promotion | Bad data may reach serving tables | Add promotion gates |
| Metadata exists in files but not as a catalog | Difficult handoff and lineage | Add table and run metadata foundation |

## Stage 1 Work Packages

### S1.1 Run Evidence Hygiene

Required changes:

```text
classify run summaries as production, smoke, manual, backfill, or test
exclude test/manual artifacts from latest production run selection by default
ensure every summary carries run_id, run_date, run_mode, status, source set, and output metrics
retain failed run evidence without presenting it as published data
```

Minimum summary fields:

```text
run_id
run_date
pipeline_mode
run_class
pipeline_status
validation_status
publish_status
source_names
crawl_ids_created
input_silver_partitions
published_outputs
error_message
start_time
end_time
duration_seconds
```

### S1.2 Environment Preflight

Required checks before full pipeline execution:

```text
project Python interpreter exists
required Python packages import
PYTHONPATH is set for `src`
Java runtime exists for Spark jobs
GCS or local publish target is configured
write permissions exist for logs and output paths
```

Suggested outputs:

```text
scripts/preflight_pipeline.ps1
scripts/preflight_pipeline.sh
data/logs/preflight/run_id=<run_id>/preflight.json
```

### S1.3 Promotion Gates

Define three states:

| State | Meaning |
|---|---|
| `generated` | Job wrote outputs |
| `validated` | Table and quality checks passed |
| `published` | Output promoted to BI or cloud serving |

Rules:

1. Gold can be generated from Silver during a failed experiment.
2. Serving tables must not be published unless validation passed.
3. Quality exceptions must be explicit. A warning threshold may publish with an alert; a blocking threshold must stop publish.

### S1.4 Metadata Foundation

Add a table catalog and run catalog contract.

Expected metadata domains:

```text
technical table schema
business description
grain
keys
partitioning
producer job
consumer dashboards
retention
quality rules
lineage inputs
```

Suggested repo outputs:

```text
docs/metadata/table_catalog.md
data/metadata/table_catalog.json
data/logs/pipeline_runs/run_id=<run_id>/run_manifest.json
```

### S1.5 Data Quality Hot Fixes

Minimum actions:

1. Preserve current metrics for parse success, duplicate, missing price, missing area, and missing location.
2. Explain current quality behavior in reports instead of hiding it.
3. Add invalid run protection when record count is zero but the run claims success.
4. Create a quarantine contract for rows that cannot conform to Silver or warehouse requirements.

Suggested quarantine outputs:

```text
data/quarantine/silver_parse_errors/
data/quarantine/warehouse_rejects/
data/reports/data_quality/
```

## Stage 1 Validation

### Required Checks

```text
[ ] `.venv` unit tests pass.
[ ] Current Gold validation passes for a real run.
[ ] Latest production run selection ignores test or manual zero-record summaries.
[ ] Every full run writes structured run evidence.
[ ] Preflight identifies missing Spark runtime before Silver-to-Gold starts.
[ ] Failed parse data is measured and preserved.
[ ] Publish decision is recorded.
```

### Negative Tests

```text
[ ] Missing Gold table blocks publication.
[ ] Zero-record full run is not reported as a healthy published run.
[ ] Missing Java or PySpark fails preflight with an actionable message.
[ ] Invalid JSON summary is skipped and logged.
```

## Deliverables

| Deliverable | Description |
|---|---|
| Production run classification | Clear difference between full, smoke, manual, test, and backfill runs |
| Preflight | Runtime and destination checks before expensive work starts |
| Promotion gate | Generated, validated, and published outputs are not conflated |
| Metadata seed | Catalog and run manifest contract |
| Quality hot fixes | Summary artifact protection and quarantine design |

## Stage 1 Exit Gate

Stage 1 is complete when this statement is true:

```text
The current Batdongsan batch can be operated repeatedly with reliable run evidence, runtime checks, validation, and an explicit publish decision.
```

