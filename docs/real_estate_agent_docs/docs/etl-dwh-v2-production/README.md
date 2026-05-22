# ETL DWH V2 Production Specification

## Purpose

This folder defines version 2 of the Real Estate Crawler data platform as a production-oriented ETL, lakehouse, DWH, orchestration, data quality, and BI specification.

Version 2 is not a rewrite of the current project. It promotes the current batch lakehouse pipeline into a controlled production path:

```text
Web sources
  -> Source adapters and crawl audit
  -> Bronze raw storage
  -> Silver normalized and conformed listings
  -> Gold analytical marts
  -> Warehouse star schema
  -> BigQuery serving datasets
  -> Power BI market dashboards
  -> Streamlit technical and operational dashboard
```

## Scope Decision

The v2 scope covers all major readiness gaps:

1. DWH star schema and dimensional modeling.
2. Production multi-source onboarding for Batdongsan, Alonhadat, and Nhatot.
3. Orchestration, CI/CD, cloud operation, backfill, and restart behavior.
4. Data quality, observability, metadata, lineage, and governance.
5. BI presentation with Power BI while keeping Streamlit for technical operations.

The project remains batch-first. Realtime streaming is not a blocking requirement for v2.

## Document Map

| File | Use |
|---|---|
| `00_V2_SCOPE_BASELINE_AND_SUCCESS_CRITERIA.md` | Current baseline, production definition, scope, non-goals, and target acceptance |
| `01_TARGET_ARCHITECTURE_AND_STAGE_GATES.md` | Target architecture and stage order without timeline assumptions |
| `02_STAGE_1_PRODUCTION_FOUNDATION.md` | Reliability, environment, data quality hot fixes, metadata foundation, and operational hygiene |
| `03_STAGE_2_DWH_STAR_SCHEMA.md` | Dimensional model, grains, bus matrix, dimensions, facts, and warehouse outputs |
| `04_STAGE_3_MULTI_SOURCE_PIPELINE.md` | Source adapter contract, onboarding Alonhadat/Nhatot, source normalization, and cross-source dedup |
| `05_STAGE_4_ORCHESTRATION_CICD_AND_CLOUD.md` | Airflow DAG, retries, backfills, CI/CD, IAM, secrets, deployment, and run control |
| `06_STAGE_5_BI_PRESENTATION_AND_POWERBI.md` | Power BI model, report pages, BigQuery serving path, and Streamlit role split |
| `07_DATA_QUALITY_OBSERVABILITY_METADATA_AND_GOVERNANCE.md` | Quality rules, observability metrics, alerts, metadata catalog, lineage, and retention |
| `08_TESTING_ACCEPTANCE_RISKS_AND_RUNBOOK.md` | Test strategy, acceptance gates, risk register, production readiness checks, and runbook outline |
| `09_IMPLEMENTATION_BACKLOG_AND_FILE_MAP.md` | Work packages, expected repo changes, dependencies, and recommended execution order |

## Stage Order

The recommended implementation order is stage-based:

```text
Stage 1  Production foundation and correctness
Stage 2  DWH star schema and serving contracts
Stage 3  Multi-source production pipeline
Stage 4  Orchestration, CI/CD, and cloud operation
Stage 5  BI presentation and Power BI
Stage 6  Production acceptance and runbook hardening
```

Each stage must satisfy its gate before the next stage becomes the default production path. Prototype work may run in parallel, but production promotion must respect the gates.

## Relationship to Existing Docs

The files in the parent `docs` folder describe the MVP and earlier phase contracts. The v2 files in this folder supersede them only where production design differs.

Important compatibility rules:

1. Keep the current Bronze, Silver, and Gold outputs working while v2 is introduced.
2. Do not silently rename current Gold analytical tables already used by Streamlit.
3. Add warehouse star schema outputs as a new serving contract instead of breaking the existing Gold marts.
4. Promote Alonhadat and Nhatot only after they satisfy the source adapter, quality, audit, and validation contracts.

