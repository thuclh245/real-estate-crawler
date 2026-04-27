import json
from pathlib import Path

from pyspark.sql import SparkSession

GOLD_BASE_PATH = Path("data/gold")

REQUIRED_TABLES = {
    "gold_current_listings": {
        "min_count": 1,
        "columns": [
            "dedup_key",
            "snapshot_date",
            "listing_url",
            "price_vnd",
            "area_m2",
            "is_info_changed",
            "changed_fields",
        ],
    },
    "gold_listing_snapshots": {
        "min_count": 1,
        "columns": [
            "dedup_key",
            "snapshot_date",
            "snapshot_status",
            "is_new_listing",
            "is_info_changed",
            "changed_fields",
        ],
    },
    "gold_market_by_district_daily": {
        "min_count": 1,
        "columns": ["snapshot_date", "district_norm", "property_type_group", "listing_count"],
    },
    "gold_market_by_property_type_daily": {
        "min_count": 1,
        "columns": ["snapshot_date", "property_type_group", "listing_count"],
    },
    "gold_data_quality_daily": {
        "min_count": 1,
        "columns": ["crawl_date", "total_records", "parse_success_rate", "duplicate_rate"],
    },
    "gold_removed_listings": {
        "min_count": 0,
        "columns": [
            "dedup_key",
            "snapshot_date",
            "last_seen_before_removed",
            "listing_id",
            "listing_url",
            "title_raw",
            "price_vnd",
            "area_m2",
            "district_norm",
            "property_type_group",
            "snapshot_status",
            "is_removed_listing",
        ],
    },
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def create_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("CheckPhase3")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "Asia/Ho_Chi_Minh")
        .getOrCreate()
    )


def check_phase3_summary() -> None:
    summary_path = GOLD_BASE_PATH / "phase3_summary.json"
    if not summary_path.exists():
        fail(f"Missing {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    required_keys = [
        "total_silver_records",
        "total_current_listings",
        "duplicate_record_count",
        "duplicate_rate",
        "parse_success_rate",
        "missing_price_rate",
        "missing_area_rate",
        "missing_location_rate",
        "snapshot_dates",
        "gold_tables_created",
    ]

    missing_keys = [key for key in required_keys if key not in summary]
    if missing_keys:
        fail(f"phase3_summary.json missing keys: {missing_keys}")

    if summary["total_silver_records"] <= 0:
        fail("total_silver_records must be greater than 0")

    if summary["total_current_listings"] <= 0:
        fail("total_current_listings must be greater than 0")

    for rate_key in [
        "duplicate_rate",
        "parse_success_rate",
        "missing_price_rate",
        "missing_area_rate",
        "missing_location_rate",
    ]:
        value = summary[rate_key]
        if value < 0 or value > 1:
            fail(f"{rate_key} must be between 0 and 1, got {value}")

    expected_tables = set(REQUIRED_TABLES.keys())
    created_tables = set(summary["gold_tables_created"])
    missing_tables = expected_tables - created_tables
    if missing_tables:
        fail(f"phase3_summary.json does not list tables: {sorted(missing_tables)}")

    print("PASS: phase3_summary.json")


def check_gold_tables(spark: SparkSession) -> None:
    for table_name, rule in REQUIRED_TABLES.items():
        table_path = GOLD_BASE_PATH / table_name
        if not table_path.exists():
            fail(f"Missing Gold table path: {table_path}")

        df = spark.read.parquet(str(table_path))
        row_count = df.count()
        if row_count < rule["min_count"]:
            fail(f"{table_name} has {row_count} rows, expected >= {rule['min_count']}")

        missing_columns = [col for col in rule["columns"] if col not in df.columns]
        if missing_columns:
            fail(f"{table_name} missing columns: {missing_columns}")

        print(f"PASS: {table_name} rows={row_count}")


def main() -> None:
    spark = create_spark()
    try:
        check_phase3_summary()
        check_gold_tables(spark)
    finally:
        spark.stop()

    print("PASS: Phase 3 validation checklist")


if __name__ == "__main__":
    main()
