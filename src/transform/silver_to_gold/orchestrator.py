from __future__ import annotations

from pyspark.sql import functions as F

from .aggregations import (
    build_gold_current_listings,
    build_gold_data_quality_daily,
    build_gold_market_by_district_daily,
    build_gold_market_by_property_type_daily,
)
from .dedup import add_dedup_key, add_duplicate_flags, dedup_daily
from .lifecycle import build_listing_lifecycle, build_removed_listings
from .reader import read_silver
from .snapshot import add_info_change_tracking, add_price_change_tracking, build_snapshot_table
from .spark_session import create_spark
from .writer import write_gold_table, write_phase3_summary


SILVER_BASE_PATH = "data/silver"
GOLD_BASE_PATH = "data/gold"

GOLD_TABLES_CREATED = [
    "gold_current_listings",
    "gold_listing_snapshots",
    "gold_market_by_district_daily",
    "gold_market_by_property_type_daily",
    "gold_data_quality_daily",
    "gold_removed_listings",
]


def main():
    spark = create_spark()

    print("=== READ SILVER ===")
    silver_df = read_silver(spark, SILVER_BASE_PATH)

    print("=== ADD DEDUP KEY ===")
    silver_df = add_dedup_key(silver_df)

    print("=== ADD DUPLICATE FLAGS ===")
    silver_df = add_duplicate_flags(silver_df)

    print("=== RECORD COUNT BY DATE BEFORE DEDUP ===")
    silver_df.groupBy("crawl_date").count().orderBy("crawl_date").show(truncate=False)

    print("=== DEDUP METHOD COUNT ===")
    silver_df.groupBy("dedup_method").count().show(truncate=False)

    print("=== DUPLICATE SUMMARY ===")
    silver_df.groupBy("crawl_date").agg(
        F.count("*").alias("total_records"),
        F.sum(F.when(F.col("is_duplicate_in_snapshot"), 1).otherwise(0)).alias("duplicate_records"),
        F.countDistinct("dedup_key").alias("distinct_dedup_keys"),
    ).orderBy("crawl_date").show(truncate=False)

    print("=== DAILY DEDUP ===")
    daily_deduped_df = dedup_daily(silver_df)
    daily_deduped_df.groupBy("crawl_date").count().orderBy("crawl_date").show(truncate=False)

    print("=== BUILD LIFECYCLE ===")
    lifecycle_df = build_listing_lifecycle(daily_deduped_df)

    print("=== BUILD SNAPSHOT TABLE ===")
    snapshot_df = build_snapshot_table(daily_deduped_df, lifecycle_df)

    print("=== ADD PRICE CHANGE TRACKING ===")
    snapshot_df = add_price_change_tracking(snapshot_df)

    print("=== ADD INFO CHANGE TRACKING ===")
    snapshot_df = add_info_change_tracking(snapshot_df)

    print("=== BUILD REMOVED LISTINGS ===")
    removed_df = build_removed_listings(daily_deduped_df)

    print("=== SNAPSHOT STATUS COUNT ===")
    snapshot_df.groupBy("snapshot_date", "snapshot_status").count().orderBy("snapshot_date", "snapshot_status").show(truncate=False)

    print("=== PRICE CHANGE COUNT ===")
    snapshot_df.groupBy("snapshot_date").agg(
        F.count("*").alias("snapshot_records"),
        F.sum(F.when(F.col("is_price_changed"), 1).otherwise(0)).alias("price_changed_count"),
    ).orderBy("snapshot_date").show(truncate=False)

    print("=== REMOVED COUNT ===")
    removed_df.groupBy("snapshot_date", "snapshot_status").count().orderBy("snapshot_date").show(truncate=False)

    print("=== BUILD GOLD TABLES ===")
    gold_current_df = build_gold_current_listings(snapshot_df)
    gold_market_district_df = build_gold_market_by_district_daily(snapshot_df)
    gold_market_property_type_df = build_gold_market_by_property_type_daily(snapshot_df)
    gold_quality_df = build_gold_data_quality_daily(silver_df, daily_deduped_df)

    gold_tables_created = [
        "gold_current_listings",
        "gold_listing_snapshots",
        "gold_market_by_district_daily",
        "gold_market_by_property_type_daily",
        "gold_data_quality_daily",
        "gold_removed_listings",
    ]

    print("=== WRITE GOLD TABLES ===")
    write_gold_table(gold_current_df, f"{GOLD_BASE_PATH}/gold_current_listings")
    write_gold_table(snapshot_df, f"{GOLD_BASE_PATH}/gold_listing_snapshots", partition_cols=["snapshot_date"])
    write_gold_table(gold_market_district_df, f"{GOLD_BASE_PATH}/gold_market_by_district_daily", partition_cols=["snapshot_date"])
    write_gold_table(gold_market_property_type_df, f"{GOLD_BASE_PATH}/gold_market_by_property_type_daily", partition_cols=["snapshot_date"])
    write_gold_table(gold_quality_df, f"{GOLD_BASE_PATH}/gold_data_quality_daily", partition_cols=["crawl_date"])
    write_gold_table(removed_df, f"{GOLD_BASE_PATH}/gold_removed_listings", partition_cols=["snapshot_date"])

    print("=== WRITE PHASE 3 SUMMARY ===")
    write_phase3_summary(
        silver_df=silver_df,
        snapshot_df=snapshot_df,
        gold_current_df=gold_current_df,
        gold_quality_df=gold_quality_df,
        output_path=f"{GOLD_BASE_PATH}/phase3_summary.json",
        gold_tables_created=gold_tables_created,
    )

    print("=== DONE PHASE 3 ===")
    print(f"Gold output written to: {GOLD_BASE_PATH}")

    spark.stop()
