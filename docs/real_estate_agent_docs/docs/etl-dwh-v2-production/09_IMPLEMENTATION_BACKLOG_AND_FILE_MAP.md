# 09 - Implementation Backlog and File Map

## Purpose

This backlog translates the v2 specs into staged implementation work. It is ordered by dependency and production risk, not calendar timeline.

## Stage 1 Backlog - Foundation

| Work package | Expected result | Likely repo areas |
|---|---|---|
| Run class and publish state | Summaries distinguish production, smoke, manual, test, backfill | `src/observability/`, `dashboard/`, `scripts/` |
| Invalid summary protection | Zero-record test summaries do not look like latest healthy production | `dashboard/app.py`, run summary readers |
| Preflight | Runtime, Spark, config, destination checks | `scripts/`, `src/validation/` |
| Quality promotion gate | Generated, validated, published states are explicit | `src/validation/`, `src/observability/`, pipeline scripts |
| Metadata seed | Table and run catalog exist | `docs/metadata/`, `data/metadata/` |
| Quarantine contract | Failed conformance paths are measurable | `src/transform/`, `data/quarantine/` |

## Stage 2 Backlog - Warehouse

| Work package | Expected result | Likely repo areas |
|---|---|---|
| Warehouse module | Build dimensions and facts | `src/warehouse/` or `src/transform/warehouse/` |
| Dimension builders | Date, source, location, property type, listing dimensions | warehouse module |
| Fact builders | Snapshot, change event, data quality facts | warehouse module |
| Warehouse validation | Grain, FK, count reconciliation | `src/validation/` |
| Warehouse docs | Bus matrix and schema catalog | v2 docs, metadata docs |
| Serving export | Local validated export and BigQuery publish path | `scripts/`, `src/publish/` |

## Stage 3 Backlog - Multi-Source

| Work package | Expected result | Likely repo areas |
|---|---|---|
| Adapter base | Shared source abstraction | `src/crawler/sources/` |
| Batdongsan adapter migration | Existing production source fits adapter design | `src/crawler/` |
| Alonhadat promotion | Candidate source reaches Bronze and Silver contracts | `src/crawler/sources/alonhadat/` |
| Nhatot evaluation | Source contract fit and promotion decision | `src/crawler/sources/nhatot/` |
| Source fixtures | Parser and mapping regression data | `tests/fixtures/`, `tests/` |
| Source scorecards | Comparable source metrics | `src/observability/`, `data/reports/` |
| Cross-source candidates | Non-destructive property candidate matching | `src/transform/`, `data/gold/` |

## Stage 4 Backlog - Orchestration and Cloud

| Work package | Expected result | Likely repo areas |
|---|---|---|
| Airflow DAG | Task-visible daily run | `dags/` or orchestration package |
| Backfill commands | Controlled reparse, rebuild, republish | `scripts/`, DAG params |
| CI workflow | Tests and contracts on changes | `.github/workflows/` |
| Runtime packaging | Reproducible dependencies and deploy path | `requirements*`, Docker or environment docs |
| IAM and secrets docs | Safe cloud operation | deployment docs |
| BigQuery publish | Warehouse and serving datasets | `src/publish/`, `scripts/` |

## Stage 5 Backlog - BI

| Work package | Expected result | Likely repo areas |
|---|---|---|
| Power BI export or connector | Validated data source for report authoring | `data/powerbi/`, publish scripts |
| BI serving views | Consumer-safe flattened views | BigQuery SQL or publish module |
| Power BI report spec | Pages, filters, measures | v2 BI docs and report artifact |
| Streamlit ops split | Technical dashboard remains focused | `dashboard/app.py` |
| Freshness visibility | Report shows data date and publish state | serving views, BI measures |

## Recommended New Modules

```text
src/warehouse/
src/publish/
src/crawler/sources/
src/quality/
dags/
docs/metadata/
data/metadata/
data/quarantine/
data/powerbi/
```

Adopt module names that fit the final repo structure, but keep responsibilities separate.

## Existing Files That Need Careful Compatibility

| Existing file | Compatibility note |
|---|---|
| `src/crawler/crawl.py` | Batdongsan logic is production baseline; adapter migration should avoid behavior regression |
| `src/transform/bronze_to_silver.py` | Current parser path should become source-aware without breaking Bronze reprocessing |
| `src/transform/silver_to_gold.py` | Current Gold marts remain valid while warehouse builders are added |
| `src/validation/check_phase3.py` | Keep Gold validation; add v2 warehouse validation separately |
| `dashboard/app.py` | Do not break technical dashboard while Power BI is introduced |
| `scripts/run_daily_pipeline.*` | Can remain entrypoints while Airflow wraps or replaces orchestration |

## Definition of Done by Work Package

Every production work package should provide:

```text
implementation
test or validation
structured evidence
docs update
operational failure behavior
```

## Dependency Notes

```text
warehouse facts depend on stable Silver identity and conformed property/location fields
Power BI production model depends on warehouse or serving views
multi-source BI comparison depends on source scorecards and conformed dimensions
orchestrated publish depends on validation and publish state rules
```

## Optional V2 Extension - ML

ML should start after DWH and quality contracts are stable.

Recommended entry conditions:

```text
fact_listing_snapshot exists
valid price analysis subset is defined
data leakage policy is written
train/test split is time-aware
feature lineage is traceable to warehouse inputs
```

ML outputs should not block core v2 ETL/DWH production acceptance.

