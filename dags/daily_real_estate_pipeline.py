from datetime import datetime, timedelta
import json
from pathlib import Path
from airflow import DAG
from airflow.utils.task_group import TaskGroup
from airflow.operators.bash import BashOperator

# Default arguments for robust production orchestration
default_args = {
    "owner": "real_estate_lakehouse",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 27),
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": ["lehuyfc321@realestate-lakehouse.com"],
}


def on_task_failure(context):
    """
    Callback executed upon task failure to log the incident and flag publish blocks.
    """
    task_instance = context["task_instance"]
    run_id = context["run_id"]
    exception = context.get("exception")

    # Resolve REPO_ROOT dynamically in callback
    dags_folder = Path(__file__).resolve().parent
    repo_root = dags_folder.parent
    if not (repo_root / "scripts").exists():
        repo_root = Path("/home/lehuyfc321/real-estate-crawler")

    # 1. Write failure incident log locally
    log_dir = repo_root / "data" / "logs" / "pipeline_runs" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    failure_record = {
        "timestamp": datetime.utcnow().isoformat(),
        "task_id": task_instance.task_id,
        "run_id": run_id,
        "exception": str(exception) if exception else "Task failed without explicit exception",
    }

    with open(log_dir / "task_failures.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(failure_record, ensure_ascii=False) + "\n")

    print(
        f"[ALERT] Task {task_instance.task_id} failed. Failure registered in task_failures.jsonl."
    )


# Resolve the repository root dynamically based on the DAG file location,
# and fallback to a default if it's copied elsewhere.
DAGS_FOLDER = Path(__file__).resolve().parent
REPO_ROOT = DAGS_FOLDER.parent
if not (REPO_ROOT / "scripts").exists():
    REPO_ROOT = Path("/home/lehuyfc321/real-estate-crawler")

with DAG(
    "daily_real_estate_lakehouse",
    default_args=default_args,
    description="Automated Crawl, Transform, Validate and BigQuery serving load",
    schedule="0 19 * * *",
    catchup=False,
    max_active_runs=1,
    on_failure_callback=on_task_failure,
) as dag:
    # 1. Preflight checks to validate Spark and config files before expensive workloads start
    preflight = BashOperator(
        task_id="preflight_check",
        bash_command="bash scripts/preflight_pipeline.sh --run-id {{ run_id }} --require-spark",
        cwd=str(REPO_ROOT),
    )

    # 2. Ingestion Task Group: handles crawls and Bronze-to-Silver transformations
    with TaskGroup("ingest_and_silver") as IngestionGroup:
        # Ingest batdongsan listings
        ingest_batdongsan = BashOperator(
            task_id="ingest_batdongsan",
            bash_command="export CRAWL_CONFIGS=configs/team/batdongsan_house_150.yaml && bash scripts/run_daily_pipeline.sh --mode full",
            cwd=str(REPO_ROOT),
        )

        # Ingest nhatot listings
        ingest_nhatot = BashOperator(
            task_id="ingest_nhatot",
            bash_command="export CRAWL_CONFIGS=configs/sources/nhatot.yaml && bash scripts/run_daily_pipeline.sh --mode full",
            cwd=str(REPO_ROOT),
        )

    # 3. Analytics Task Group: PySpark Silver-to-Gold aggregations and analytical marts
    with TaskGroup("silver_to_gold_marts") as AnalyticsGroup:
        gold_transform = BashOperator(
            task_id="gold_spark_marts",
            bash_command="export PYTHONPATH=src SPARK_DRIVER_MEMORY=2g && .venv/bin/python -m transform.silver_to_gold",
            cwd=str(REPO_ROOT),
        )

    # 4. Validation Task Group: executes Gold contract and quality threshold check gates
    with TaskGroup("validate_gold_tables") as ValidationGroup:
        check_readiness = BashOperator(
            task_id="check_gold_readiness",
            bash_command="export PYTHONPATH=src && .venv/bin/python -m validation.check_gold_readiness",
            cwd=str(REPO_ROOT),
        )

    # 5. Publication Task Group: loads optimized partitioned Gold Parquet tables into BigQuery and exports Power BI flat marts
    with TaskGroup("publish_serving") as PublishGroup:
        publish_bq = BashOperator(
            task_id="publish_to_bigquery",
            bash_command="export PYTHONPATH=src && .venv/bin/python -m publish.bigquery",
            cwd=str(REPO_ROOT),
        )

        publish_pbi = BashOperator(
            task_id="publish_to_powerbi",
            bash_command="export PYTHONPATH=src && .venv/bin/python -m publish.powerbi",
            cwd=str(REPO_ROOT),
        )

    # Establish end-to-end task execution dependencies
    preflight >> IngestionGroup >> AnalyticsGroup >> ValidationGroup >> PublishGroup
