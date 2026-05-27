from datetime import datetime, timedelta
import os
import json
from pathlib import Path
from airflow import DAG
from airflow.decorators import task
from airflow.utils.task_group import TaskGroup
from airflow.operators.bash import BashOperator

# Default arguments for robust production orchestration
default_args = {
    'owner': 'real_estate_lakehouse',
    'depends_on_past': False,
    'start_date': datetime(2026, 5, 27),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': True,
    'email': ['lehuyfc321@realestate-lakehouse.com'],
}

def on_task_failure(context):
    """
    Callback executed upon task failure to log the incident and flag publish blocks.
    """
    task_instance = context['task_instance']
    run_id = context['run_id']
    exception = context.get('exception')
    
    # 1. Write failure incident log locally
    log_dir = Path(f"data/logs/pipeline_runs/{run_id}")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    failure_record = {
        "timestamp": datetime.utcnow().isoformat(),
        "task_id": task_instance.task_id,
        "run_id": run_id,
        "exception": str(exception) if exception else "Task failed without explicit exception",
    }
    
    with open(log_dir / "task_failures.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(failure_record, ensure_ascii=False) + "\n")
        
    print(f"[ALERT] Task {task_instance.task_id} failed. Failure registered in task_failures.jsonl.")

with DAG(
    'daily_real_estate_lakehouse',
    default_args=default_args,
    description='Automated Crawl, Transform, Validate and BigQuery serving load',
    schedule_interval='30 3 * * *',  # Runs daily at 03:30 AM UTC (10:30 AM ICT)
    catchup=False,
    max_active_runs=1,
    on_failure_callback=on_task_failure,
) as dag:

    # 1. Preflight checks to validate Spark and config files before expensive workloads start
    preflight = BashOperator(
        task_id='preflight_check',
        bash_command='scripts/preflight_pipeline.sh --run-id {{ run_id }} --require-spark',
    )

    # 2. Ingestion Task Group: handles crawls and Bronze-to-Silver transformations
    with TaskGroup('ingest_and_silver') as IngestionGroup:
        
        # Ingest batdongsan listings
        ingest_batdongsan = BashOperator(
            task_id='ingest_batdongsan',
            bash_command='export CRAWL_CONFIGS=configs/team/batdongsan_house_150.yaml && scripts/run_daily_pipeline.sh --mode full',
        )

        # Ingest nhatot listings
        ingest_nhatot = BashOperator(
            task_id='ingest_nhatot',
            bash_command='export CRAWL_CONFIGS=configs/sources/nhatot.yaml && scripts/run_daily_pipeline.sh --mode full',
        )

    # 3. Analytics Task Group: PySpark Silver-to-Gold aggregations and analytical marts
    with TaskGroup('silver_to_gold_marts') as AnalyticsGroup:
        
        gold_transform = BashOperator(
            task_id='gold_spark_marts',
            bash_command='export SPARK_DRIVER_MEMORY=2g && python -m transform.silver_to_gold',
        )

    # 4. Validation Task Group: executes Gold contract and quality threshold check gates
    with TaskGroup('validate_gold_tables') as ValidationGroup:
        
        check_readiness = BashOperator(
            task_id='check_gold_readiness',
            bash_command='python -m validation.check_gold_readiness',
        )

    # 5. Publication Task Group: loads optimized partitioned Gold Parquet tables into BigQuery
    with TaskGroup('publish_serving') as PublishGroup:
        
        publish_bq = BashOperator(
            task_id='publish_to_bigquery',
            bash_command='python -m publish.bigquery',
        )

    # Establish end-to-end task execution dependencies
    preflight >> IngestionGroup >> AnalyticsGroup >> ValidationGroup >> PublishGroup
