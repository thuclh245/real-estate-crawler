from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Support running directly or as module
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from warehouse.orchestrator import build_warehouse_outputs
from validation.check_warehouse import check_warehouse_summary, check_warehouse_tables

GOLD_BASE_PATH = Path("data/gold")
WAREHOUSE_BASE_PATH = Path("data/warehouse")
POWERBI_BASE_PATH = Path("data/powerbi")


def _read_table(warehouse_base_path: Path, table_name: str) -> pd.DataFrame:
    """Reads a partitioned Parquet table from warehouse output into a single DataFrame."""
    table_path = warehouse_base_path / table_name
    if not table_path.exists():
        raise FileNotFoundError(f"Missing warehouse table directory: {table_path}")

    parquet_files = sorted(table_path.glob("**/*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found under: {table_path}")

    frames = [pd.read_parquet(file_path) for file_path in parquet_files]
    return pd.concat(frames, ignore_index=True, sort=False)


def publish_powerbi_marts(
    gold_base_path: Path = GOLD_BASE_PATH,
    warehouse_base_path: Path = WAREHOUSE_BASE_PATH,
    powerbi_base_path: Path = POWERBI_BASE_PATH,
) -> bool:
    """
    Orchestrates building, validating, and exporting warehouse tables for Power BI.
    Aborts and returns False if validations fail.
    """
    print("=== STARTING POWER BI PUBLISHING PHASE ===")
    run_id = os.getenv("RUN_ID") or f"manual_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # 1. Build local warehouse dimension and fact tables
    print(f"[PowerBI] Building warehouse from gold: {gold_base_path} -> {warehouse_base_path}")
    try:
        build_warehouse_outputs(
            gold_base_path=gold_base_path,
            warehouse_base_path=warehouse_base_path,
        )
        print("[OK] [PowerBI] Warehouse built successfully.")
    except Exception as err:
        print(f"[ERROR] [PowerBI] Failed to build warehouse: {err}")
        return False

    # 2. Validate warehouse tables before publishing to Power BI
    print("[PowerBI] Validating warehouse integrity...")
    try:
        check_warehouse_summary(warehouse_base_path)
        check_warehouse_tables(warehouse_base_path, gold_base_path)
        print("[OK] [PowerBI] Warehouse validation passed.")
    except SystemExit as exit_err:
        print(f"[ERROR] [PowerBI] Warehouse validation failed (SystemExit): {exit_err}")
        return False
    except Exception as err:
        print(f"[ERROR] [PowerBI] Unexpected validation error: {err}")
        return False

    # 3. Export each warehouse table to CSV for Power BI Desktop
    powerbi_base_path.mkdir(parents=True, exist_ok=True)
    tables_to_export = [
        "dim_date",
        "dim_source",
        "dim_property_type",
        "dim_location_basic",
        "dim_listing",
        "fact_listing_snapshot",
        "fact_data_quality_daily",
    ]

    table_row_counts = {}
    latest_snapshot_date = None

    print(f"[PowerBI] Exporting tables to: {powerbi_base_path}...")
    for table_name in tables_to_export:
        try:
            df = _read_table(warehouse_base_path, table_name)
            row_count = len(df)
            table_row_counts[table_name] = row_count

            csv_path = powerbi_base_path / f"{table_name}.csv"
            # na_rep="" ensures negotiable / None values are empty strings, not "0" or "NaN"
            # encoding="utf-8-sig" ensures Power BI on Windows reads international text (Vietnamese accents) perfectly
            df.to_csv(csv_path, index=False, na_rep="", encoding="utf-8-sig")
            print(f"  -> Exported {table_name}.csv ({row_count} rows)")

            # Dynamically resolve latest snapshot date from dim_date
            if table_name == "dim_date" and not df.empty and "date_value" in df.columns:
                latest_date_val = pd.to_datetime(df["date_value"]).max()
                latest_snapshot_date = latest_date_val.strftime("%Y-%m-%d")

        except Exception as err:
            print(f"[ERROR] [PowerBI] Failed to export table {table_name}: {err}")
            return False

    # Fallback if dim_date was somehow empty
    if not latest_snapshot_date:
        latest_snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 4. Generate refresh manifest metadata
    manifest_path = powerbi_base_path / "refresh_manifest.json"
    manifest = {
        "last_refresh_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
        "warehouse_schema_version": "warehouse_v1",
        "table_row_counts": table_row_counts,
        "latest_snapshot_date": latest_snapshot_date,
        "refresh_status": "success",
        "run_id": run_id,
    }

    try:
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[OK] [PowerBI] Manifest generated at: {manifest_path}")
    except Exception as err:
        print(f"[ERROR] [PowerBI] Failed to write manifest: {err}")
        return False

    print("=== POWER BI PUBLISHING COMPLETE (SUCCESS) ===")
    return True


if __name__ == "__main__":
    success = publish_powerbi_marts()
    sys.exit(0 if success else 1)
