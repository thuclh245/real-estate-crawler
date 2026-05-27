import os
import yaml
from pathlib import Path
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError


def get_gcs_bucket() -> str:
    """Helper to resolve the target GCS bucket name from env or production configs."""
    bucket = os.getenv("GCS_BUCKET")
    if bucket:
        return bucket.replace("gs://", "")

    try:
        prod_config = Path("configs/environments/prod/pipeline_config.yaml")
        if prod_config.exists():
            with open(prod_config, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                bucket = cfg.get("gcs", {}).get("bucket")
                if bucket:
                    return bucket.replace("gs://", "")
    except Exception:
        pass

    return "bigdata-subject-real-estate-lakehouse"


def publish_gcs_to_bq(
    folder_name: str,
    table_id: str,
    partition_field: str = "snapshot_date",
    is_partitioned: bool = True,
) -> bool:
    """
    Loads Parquet files from Google Cloud Storage into BigQuery.
    If is_partitioned is True, it uses Hive Partitioning to dynamically reconstruct partition columns
    (snapshot_date / crawl_date) from path prefixes and applies Time Partitioning.
    Otherwise, it loads them as a standard flat table.
    """
    try:
        client = bigquery.Client()
    except Exception as e:
        print(f"[ERROR] Failed to initialize BigQuery Client: {e}")
        return False

    bucket_name = get_gcs_bucket()

    if is_partitioned:
        # Match using standard single wildcard * (supported by BigQuery)
        gcs_uri = f"gs://{bucket_name}/gold/{folder_name}/*"
        source_uri_prefix = f"gs://{bucket_name}/gold/{folder_name}/"

        # Configure Hive Partitioning Options to auto-detect partition columns from paths
        hive_options = bigquery.HivePartitioningOptions()
        hive_options.mode = "AUTO"
        hive_options.source_uri_prefix = source_uri_prefix

        # Configure partitioned loading job with WRITE_TRUNCATE
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            time_partitioning=bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY, field=partition_field
            ),
            hive_partitioning=hive_options,
            create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        )
    else:
        # Load flat parquet files using standard single wildcard
        gcs_uri = f"gs://{bucket_name}/gold/{folder_name}/*"

        # Configure standard non-partitioned loading job with WRITE_TRUNCATE
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        )

    print(f"\n[BQ PUBLISH] Loading folder from GCS: {gcs_uri}...")
    if is_partitioned:
        print(f"[BQ PUBLISH] Hive Source Prefix: {source_uri_prefix}")
    print(f"[BQ PUBLISH] Target BigQuery Table: {table_id}")

    try:
        load_job = client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
        load_job.result()  # Block and wait for job completion
        print(f"✓ [SUCCESS] BigQuery load job finished successfully for: {table_id}")
        return True
    except GoogleAPIError as api_err:
        print(f"✗ [API ERROR] BigQuery failed to load {gcs_uri}: {api_err}")
        return False
    except Exception as err:
        print(f"✗ [UNEXPECTED ERROR] Failed to load {gcs_uri}: {err}")
        return False


def main():
    # Auto-detect active Google Cloud Project ID from BigQuery Client
    active_project = "bigdata-subject-real-estate-lakehouse"
    try:
        client = bigquery.Client()
        active_project = client.project
        print(f"[INFO] Auto-detected active Google Cloud Project: {active_project}")
    except Exception as e:
        print(f"[INFO] Could not auto-detect GCP project, using default or env: {e}")

    dataset_env = os.getenv("BQ_DATASET_ID", "gold")
    if "." in dataset_env:
        dataset_id = dataset_env
        dataset_name = dataset_env.split(".")[1]
    else:
        dataset_id = f"{active_project}.{dataset_env}"
        dataset_name = dataset_env

    # Check and dynamically create BigQuery Dataset if it doesn't exist
    try:
        client = bigquery.Client()
        dataset_ref = client.dataset(dataset_name)
        try:
            client.get_dataset(dataset_ref)
            print(f"[INFO] Dataset {dataset_id} already exists.")
        except Exception:
            print(f"[INFO] Dataset {dataset_id} not found, creating it dynamically...")
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"  # Use US multi-region to keep costs free
            client.create_dataset(dataset, exists_ok=True)
            print(f"✓ [SUCCESS] Dataset {dataset_id} created dynamically!")
    except Exception as e:
        print(f"[WARN] Failed to verify or create dataset {dataset_id}: {e}")

    # Mapping of Gold folder names to target BigQuery tables
    tables = {
        "gold_listing_snapshots": f"{dataset_id}.fact_listing_snapshot",
        "gold_market_by_district_daily": f"{dataset_id}.market_by_district_daily",
        "gold_market_by_property_type_daily": f"{dataset_id}.market_by_property_type_daily",
        "gold_data_quality_daily": f"{dataset_id}.data_quality_daily",
        "gold_removed_listings": f"{dataset_id}.gold_removed_listings",
    }

    # Run a quick GCS cleanup of .crc files before loading to prevent BigQuery format failures
    try:
        import subprocess

        bucket_name = get_gcs_bucket()
        print(
            f"[INFO] Cleaning up .crc checksum files from GCS: gs://{bucket_name}/gold/**/*.crc ..."
        )
        # Run gcloud storage rm recursively to delete all .crc files from the GCS gold directory
        # The gcloud CLI is natively available on the VM
        subprocess.run(
            f'gcloud storage rm "gs://{bucket_name}/gold/**/*.crc"',
            shell=True,
            capture_output=True,
            text=True,
        )
        print("✓ [SUCCESS] GCS .crc files cleanup process finished.")
    except Exception as e:
        print(f"[WARN] Failed to clean up .crc files from GCS: {e}")

    print("=== STARTING BIGQUERY PUBLISH PHASE ===")
    success_count = 0
    attempt_count = 0

    for folder_name, table_id in tables.items():
        attempt_count += 1

        # Detect if GCS/local folder is actually partitioned (has "=" in subdirectory name)
        local_path = Path("data/gold") / folder_name
        is_partitioned = False
        if local_path.exists():
            subdirs = [p for p in local_path.iterdir() if p.is_dir() and "=" in p.name]
            if subdirs:
                is_partitioned = True

        print(f"[INFO] Table {folder_name} -> Partitioned: {is_partitioned}")

        # Determine correct partition column (gold_data_quality_daily partitioned on crawl_date)
        partition_col = "crawl_date" if "data_quality" in folder_name else "snapshot_date"

        success = publish_gcs_to_bq(
            folder_name, table_id, partition_col, is_partitioned=is_partitioned
        )
        if success:
            success_count += 1

    print(f"\n=== BIGQUERY PUBLISH COMPLETE: {success_count}/{attempt_count} tables loaded. ===")


if __name__ == "__main__":
    main()
