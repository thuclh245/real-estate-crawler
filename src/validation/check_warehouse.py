from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

WAREHOUSE_BASE_PATH = Path("data/warehouse")
GOLD_BASE_PATH = Path("data/gold")

REQUIRED_TABLES = {
    "dim_date": {
        "min_count": 1,
        "columns": [
            "date_key",
            "date_value",
            "day_of_month",
            "day_of_week",
            "week_of_year",
            "month",
            "month_name",
            "quarter",
            "year",
            "is_weekend",
        ],
    },
    "dim_source": {
        "min_count": 1,
        "columns": [
            "source_key",
            "source_code",
            "source_name",
            "source_domain",
            "source_type",
            "is_active",
            "first_onboarded_at",
        ],
    },
    "dim_property_type": {
        "min_count": 1,
        "columns": [
            "property_type_key",
            "business_type",
            "property_type_group",
            "property_type_code",
            "property_type_label",
            "is_residential",
            "is_land",
            "is_commercial",
        ],
    },
    "dim_location_basic": {
        "min_count": 1,
        "columns": [
            "location_key",
            "country_code",
            "country_name",
            "city_code",
            "city_name",
            "district_code",
            "district_name",
            "ward_code",
            "ward_name",
            "location_level",
            "location_confidence",
            "location_match_method",
            "is_reference_matched",
        ],
    },
    "dim_listing": {
        "min_count": 1,
        "columns": [
            "listing_key",
            "source_key",
            "source_listing_id",
            "source_listing_url",
            "dedup_key",
            "first_seen_date_key",
            "last_seen_date_key",
            "listing_identity_method",
        ],
    },
    "fact_listing_snapshot": {
        "min_count": 1,
        "columns": [
            "snapshot_date_key",
            "source_key",
            "listing_key",
            "location_key",
            "property_type_key",
            "price_vnd",
            "area_m2",
            "unit_price_vnd_m2",
            "bedroom_count",
            "bathroom_count",
            "frontage_width_m",
            "quality_score",
            "snapshot_status",
            "is_new_listing",
            "is_active_listing",
            "is_removed_listing",
            "is_price_changed",
            "is_info_changed",
            "price_change_vnd",
            "price_change_pct",
            "has_legal_info",
            "has_car_access",
            "is_price_negotiable",
        ],
    },
    "fact_data_quality_daily": {
        "min_count": 1,
        "columns": [
            "crawl_date_key",
            "source_key",
            "total_records",
            "parse_success_count",
            "parse_success_rate",
            "duplicate_record_count",
            "duplicate_rate",
            "missing_price_count",
            "missing_price_rate",
            "missing_area_count",
            "missing_area_rate",
            "missing_location_count",
            "missing_location_rate",
            "quarantine_count",
            "publish_blocked_flag",
        ],
    },
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def load_summary(warehouse_base_path: Path = WAREHOUSE_BASE_PATH) -> dict:
    summary_path = warehouse_base_path / "warehouse_summary.json"
    if not summary_path.exists():
        fail(f"Missing {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _read_table(warehouse_base_path: Path, table_name: str) -> pd.DataFrame:
    table_path = warehouse_base_path / table_name
    if not table_path.exists():
        fail(f"Missing warehouse table path: {table_path}")

    parquet_files = sorted(table_path.glob("**/*.parquet"))
    if not parquet_files:
        fail(f"No parquet files found under: {table_path}")

    frames = []
    for file_path in parquet_files:
        df = pd.read_parquet(file_path)
        for parent in file_path.parents:
            if parent == table_path:
                break
            if "=" in parent.name:
                part_col, part_val = parent.name.split("=", 1)
                df[part_col] = part_val
        frames.append(df)

    return pd.concat(frames, ignore_index=True, sort=False)


def _read_optional_table(base_path: Path, table_name: str) -> pd.DataFrame | None:
    table_path = base_path / table_name
    if not table_path.exists():
        return None

    parquet_files = sorted(table_path.glob("**/*.parquet"))
    if not parquet_files:
        return None

    frames = []
    for file_path in parquet_files:
        df = pd.read_parquet(file_path)
        for parent in file_path.parents:
            if parent == table_path:
                break
            if "=" in parent.name:
                part_col, part_val = parent.name.split("=", 1)
                df[part_col] = part_val
        frames.append(df)

    return pd.concat(frames, ignore_index=True, sort=False)


def _require_known_values(
    df: pd.DataFrame, column_name: str, allowed_values: set, table_name: str
) -> None:
    if column_name not in df.columns:
        fail(f"{table_name} missing required column for foreign-key validation: {column_name}")

    invalid_values = df.loc[
        df[column_name].isna() | ~df[column_name].isin(allowed_values), column_name
    ]
    if not invalid_values.empty:
        values = sorted(set(invalid_values.dropna().tolist()))
        fail(f"{table_name} has unresolved values in {column_name}: {values}")


def _require_unknown_member(
    df: pd.DataFrame, key_column: str, expected_value, table_name: str
) -> None:
    if key_column not in df.columns:
        fail(f"{table_name} missing required column for unknown-member validation: {key_column}")
    if expected_value not in set(df[key_column].tolist()):
        fail(f"{table_name} missing explicit unknown member for {key_column}={expected_value}")


def check_warehouse_summary(warehouse_base_path: Path = WAREHOUSE_BASE_PATH) -> None:
    summary = load_summary(warehouse_base_path)
    required_keys = [
        "warehouse_schema_version",
        "table_row_counts",
        "warehouse_tables_created",
    ]
    missing_keys = [key for key in required_keys if key not in summary]
    if missing_keys:
        fail(f"warehouse_summary.json missing keys: {missing_keys}")
    if not summary["warehouse_tables_created"]:
        fail("warehouse_tables_created must not be empty")


def _unique_count(df: pd.DataFrame, columns: list[str]) -> int:
    return int(df.drop_duplicates(subset=columns).shape[0])


def _check_snapshot_reconciliation(warehouse_base_path: Path, gold_base_path: Path) -> None:
    gold_snapshot_df = _read_optional_table(gold_base_path, "gold_listing_snapshots")
    if gold_snapshot_df is None:
        gold_snapshot_df = _read_optional_table(gold_base_path, "gold_current_listings")
    if gold_snapshot_df is None:
        fail(f"Missing Gold snapshot table under {gold_base_path}")

    fact_df = _read_table(warehouse_base_path, "fact_listing_snapshot")
    
    # Identify unique snapshots at the grain level to reconcile correctly in the presence of duplicate parquet rows
    grain_cols = []
    for col in ["snapshot_date", "source", "dedup_key", "listing_id"]:
        if col in gold_snapshot_df.columns:
            grain_cols.append(col)
            
    unique_gold_df = gold_snapshot_df.drop_duplicates(subset=grain_cols) if grain_cols else gold_snapshot_df
    gold_count = int(unique_gold_df.shape[0])
    fact_count = int(fact_df.shape[0])
    if fact_count != gold_count:
        fail(
            "fact_listing_snapshot record count does not reconcile to Gold snapshot output: "
            f"fact={fact_count}, gold={gold_count} (source raw={int(gold_snapshot_df.shape[0])})"
        )

    print(f"PASS: fact_listing_snapshot reconciles to Gold snapshot rows={gold_count}")


def check_warehouse_tables(
    warehouse_base_path: Path = WAREHOUSE_BASE_PATH,
    gold_base_path: Path | None = None,
) -> None:
    summary = load_summary(warehouse_base_path)
    expected_row_counts = summary.get("table_row_counts", {})

    dim_date_df = _read_table(warehouse_base_path, "dim_date")
    dim_source_df = _read_table(warehouse_base_path, "dim_source")
    dim_property_type_df = _read_table(warehouse_base_path, "dim_property_type")
    dim_location_basic_df = _read_table(warehouse_base_path, "dim_location_basic")
    dim_listing_df = _read_table(warehouse_base_path, "dim_listing")

    dim_date_keys = set(dim_date_df["date_key"].tolist())
    dim_source_keys = set(dim_source_df["source_key"].tolist())
    dim_property_type_keys = set(dim_property_type_df["property_type_key"].tolist())
    dim_location_keys = set(dim_location_basic_df["location_key"].tolist())
    dim_listing_keys = set(dim_listing_df["listing_key"].tolist())

    for table_name, rule in REQUIRED_TABLES.items():
        df = _read_table(warehouse_base_path, table_name)
        row_count = int(df.shape[0])
        if row_count < rule["min_count"]:
            fail(f"{table_name} has {row_count} rows, expected >= {rule['min_count']}")

        missing_columns = [
            column_name for column_name in rule["columns"] if column_name not in df.columns
        ]
        if missing_columns:
            fail(f"{table_name} missing columns: {missing_columns}")

        if table_name == "dim_date" and row_count != _unique_count(df, ["date_key"]):
            fail("dim_date contains duplicate date_key values")
        if table_name == "dim_source" and row_count != _unique_count(df, ["source_key"]):
            fail("dim_source contains duplicate source_key values")
        if table_name == "dim_property_type" and row_count != _unique_count(
            df, ["property_type_key"]
        ):
            fail("dim_property_type contains duplicate property_type_key values")
        if table_name == "dim_location_basic" and row_count != _unique_count(df, ["location_key"]):
            fail("dim_location_basic contains duplicate location_key values")
        if table_name == "dim_listing" and row_count != _unique_count(df, ["listing_key"]):
            fail("dim_listing contains duplicate listing_key values")

        if table_name == "dim_source":
            _require_unknown_member(df, "source_key", 0, table_name)
        if table_name == "dim_property_type":
            _require_unknown_member(df, "property_type_key", "0000000000000000", table_name)
        if table_name == "dim_location_basic":
            _require_unknown_member(df, "location_key", "0000000000000000", table_name)

        if table_name == "dim_listing":
            _require_known_values(df, "source_key", dim_source_keys, table_name)
            _require_known_values(df, "first_seen_date_key", dim_date_keys, table_name)
            _require_known_values(df, "last_seen_date_key", dim_date_keys, table_name)
        if table_name == "fact_listing_snapshot":
            _require_known_values(df, "snapshot_date_key", dim_date_keys, table_name)
            _require_known_values(df, "source_key", dim_source_keys, table_name)
            _require_known_values(df, "listing_key", dim_listing_keys, table_name)
            _require_known_values(df, "location_key", dim_location_keys, table_name)
            _require_known_values(df, "property_type_key", dim_property_type_keys, table_name)
            key_count = _unique_count(df, ["snapshot_date_key", "source_key", "listing_key"])
            if row_count != key_count:
                fail("fact_listing_snapshot contains duplicate fact grain values")
        if table_name == "fact_data_quality_daily":
            _require_known_values(df, "crawl_date_key", dim_date_keys, table_name)
            _require_known_values(df, "source_key", dim_source_keys, table_name)
            key_count = _unique_count(df, ["crawl_date_key", "source_key"])
            if row_count != key_count:
                fail("fact_data_quality_daily contains duplicate fact grain values")

        expected_count = expected_row_counts.get(table_name)
        if expected_count is not None and row_count != int(expected_count):
            fail(f"{table_name} row count mismatch: table={row_count}, summary={expected_count}")

        print(f"PASS: {table_name} rows={row_count}")

    if gold_base_path is not None:
        _check_snapshot_reconciliation(warehouse_base_path, gold_base_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate warehouse outputs.")
    parser.add_argument("--warehouse-base-path", default=str(WAREHOUSE_BASE_PATH))
    parser.add_argument("--gold-base-path", default=None)
    args = parser.parse_args()

    warehouse_base_path = Path(args.warehouse_base_path)
    gold_base_path = Path(args.gold_base_path) if args.gold_base_path else None

    check_warehouse_summary(warehouse_base_path)
    check_warehouse_tables(warehouse_base_path, gold_base_path)
    print("PASS: Warehouse validation checklist")


if __name__ == "__main__":
    main()
