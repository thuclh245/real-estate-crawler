import sys
import os
from pathlib import Path
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

def publish_parquet_to_bq(parquet_path: Path, table_id: str, partition_field: str = "snapshot_date"):
    """
    Loads a partitioned Parquet file into a specific BigQuery table using Time Partitioning.
    Use WRITE_TRUNCATE to replace only the specific partition slice.
    """
    # 1. Initialize client (will automatically look for GOOGLE_APPLICATION_CREDENTIALS)
    try:
        client = bigquery.Client()
    except Exception as e:
        print(f"[ERROR] Failed to initialize BigQuery Client: {e}")
        print("[INFO] Please verify that your GOOGLE_APPLICATION_CREDENTIALS environment variable is set.")
        return False

    # 2. Configure partitioned loading job
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Overwrites the target partition day
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_field
        ),
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED
    )

    print(f"\n[BQ PUBLISH] Loading partitioned Parquet: {parquet_path}...")
    print(f"[BQ PUBLISH] Target BigQuery Table: {table_id}")
    
    try:
        with open(parquet_path, "rb") as source_file:
            load_job = client.load_table_from_file(
                source_file, table_id, job_config=job_config
            )
            
        load_job.result()  # Block and wait for job completion
        print(f"✓ [SUCCESS] BigQuery load job finished successfully for: {table_id}")
        return True
    except GoogleAPIError as api_err:
        print(f"✗ [API ERROR] BigQuery failed to load {parquet_path}: {api_err}")
        return False
    except Exception as err:
        print(f"✗ [UNEXPECTED ERROR] Failed to load {parquet_path}: {err}")
        return False

def main():
    gold_base = Path("data/gold")
    
    # Read environment dataset prefix or default to production dataset
    dataset_id = os.getenv("BQ_DATASET_ID", "bigdata-subject-real-estate-lakehouse.gold")
    
    # Mapping of local Gold tables to target BigQuery tables
    tables = {
        "gold_listing_snapshots": f"{dataset_id}.fact_listing_snapshot",
        "gold_market_by_district_daily": f"{dataset_id}.market_by_district_daily",
        "gold_market_by_property_type_daily": f"{dataset_id}.market_by_property_type_daily",
        "gold_data_quality_daily": f"{dataset_id}.data_quality_daily",
        "gold_removed_listings": f"{dataset_id}.gold_removed_listings"
    }
    
    print("=== STARTING BIGQUERY PUBLISH PHASE ===")
    success_count = 0
    attempt_count = 0
    
    for folder_name, table_id in tables.items():
        folder_path = gold_base / folder_name
        if folder_path.exists():
            # Standard partitioned layouts contain Parquet files down the partition hierarchy
            parquet_files = list(folder_path.glob("**/*.parquet"))
            
            if not parquet_files:
                print(f"[INFO] No parquet files found in Gold directory: {folder_path}")
                continue
                
            for file in parquet_files:
                attempt_count += 1
                # Determine correct partition column (gold_data_quality_daily partitioned on crawl_date)
                partition_col = "crawl_date" if "data_quality" in folder_name else "snapshot_date"
                
                success = publish_parquet_to_bq(file, table_id, partition_col)
                if success:
                    success_count += 1
        else:
            print(f"[WARN] Gold directory does not exist: {folder_path}")
            
    print(f"\n=== BIGQUERY PUBLISH COMPLETE: {success_count}/{attempt_count} files loaded. ===")

if __name__ == "__main__":
    main()
