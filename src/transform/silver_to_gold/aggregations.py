from __future__ import annotations

from pyspark.sql import Window
from pyspark.sql import functions as F


def build_gold_current_listings(snapshot_df):
    window_spec = Window.partitionBy("dedup_key").orderBy(F.col("snapshot_date").desc())
    return (
        snapshot_df.withColumn("rn", F.row_number().over(window_spec))
        .filter(F.col("rn") == 1)
        .drop("rn")
    )


def build_gold_market_by_district_daily(snapshot_df):
    df = snapshot_df.filter(F.col("snapshot_status") != "removed")
    return df.groupBy(
        "snapshot_date", "city_norm", "district_norm", "property_type_group"
    ).agg(
        F.count("*").alias("listing_count"),
        F.expr("percentile_approx(price_vnd, 0.5)").alias("median_price_vnd"),
        F.avg("price_vnd").alias("avg_price_vnd"),
        F.expr("percentile_approx(area_m2, 0.5)").alias("median_area_m2"),
        F.expr("percentile_approx(unit_price_vnd_m2, 0.5)").alias(
            "median_unit_price_vnd_m2"
        ),
        F.avg("unit_price_vnd_m2").alias("avg_unit_price_vnd_m2"),
        F.sum(F.when(F.col("snapshot_status") == "new", 1).otherwise(0)).alias(
            "new_listing_count"
        ),
        F.sum(F.when(F.col("is_price_changed"), 1).otherwise(0)).alias(
            "price_changed_count"
        ),
        F.sum(F.when(F.col("price_unit") == "negotiable", 1).otherwise(0)).alias(
            "negotiable_price_count"
        ),
    )


def build_gold_market_by_property_type_daily(snapshot_df):
    df = snapshot_df.filter(F.col("snapshot_status") != "removed")
    return df.groupBy("snapshot_date", "property_type_group").agg(
        F.count("*").alias("listing_count"),
        F.expr("percentile_approx(price_vnd, 0.5)").alias("median_price_vnd"),
        F.avg("price_vnd").alias("avg_price_vnd"),
        F.expr("percentile_approx(area_m2, 0.5)").alias("median_area_m2"),
        F.expr("percentile_approx(unit_price_vnd_m2, 0.5)").alias(
            "median_unit_price_vnd_m2"
        ),
        F.sum(F.when(F.col("price_unit") == "negotiable", 1).otherwise(0)).alias(
            "negotiable_price_count"
        ),
        F.sum(F.when(F.col("snapshot_status") == "new", 1).otherwise(0)).alias(
            "new_listing_count"
        ),
        F.sum(F.when(F.col("is_price_changed"), 1).otherwise(0)).alias(
            "price_changed_count"
        ),
    )


def build_gold_data_quality_daily(df_before_dedup, df_after_dedup):
    base_quality = df_before_dedup.groupBy("crawl_date", "source").agg(
        F.count("*").alias("total_records"),
        F.sum(F.when(F.col("parse_status") == "success", 1).otherwise(0)).alias(
            "parse_success_count"
        ),
        F.sum(F.when(F.col("is_missing_price"), 1).otherwise(0)).alias(
            "missing_price_count"
        ),
        F.sum(F.when(F.col("is_price_negotiable"), 1).otherwise(0)).alias(
            "negotiable_price_count"
        ),
        F.sum(F.when(F.col("is_missing_area"), 1).otherwise(0)).alias(
            "missing_area_count"
        ),
        F.sum(F.when(F.col("is_missing_location"), 1).otherwise(0)).alias(
            "missing_location_count"
        ),
        F.sum(F.when(F.col("is_invalid_price"), 1).otherwise(0)).alias(
            "invalid_price_count"
        ),
        F.sum(F.when(F.col("is_invalid_area"), 1).otherwise(0)).alias(
            "invalid_area_count"
        ),
        F.sum(F.when(F.col("is_duplicate_in_snapshot"), 1).otherwise(0)).alias(
            "duplicate_record_count"
        ),
        F.countDistinct("dedup_key").alias("distinct_dedup_key_count"),
    )

    return (
        base_quality.withColumn(
            "parse_success_rate", F.col("parse_success_count") / F.col("total_records")
        )
        .withColumn(
            "missing_price_rate", F.col("missing_price_count") / F.col("total_records")
        )
        .withColumn(
            "negotiable_price_rate",
            F.col("negotiable_price_count") / F.col("total_records"),
        )
        .withColumn(
            "missing_area_rate", F.col("missing_area_count") / F.col("total_records")
        )
        .withColumn(
            "missing_location_rate",
            F.col("missing_location_count") / F.col("total_records"),
        )
        .withColumn(
            "invalid_price_rate", F.col("invalid_price_count") / F.col("total_records")
        )
        .withColumn(
            "invalid_area_rate", F.col("invalid_area_count") / F.col("total_records")
        )
        .withColumn(
            "duplicate_rate", F.col("duplicate_record_count") / F.col("total_records")
        )
    )
