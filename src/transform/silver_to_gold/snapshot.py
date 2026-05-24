from __future__ import annotations

from pyspark.sql import Window
from pyspark.sql import functions as F


def build_snapshot_table(daily_deduped_df, lifecycle_df):
    snapshot_df = daily_deduped_df.join(lifecycle_df, on="dedup_key", how="left")
    snapshot_df = snapshot_df.withColumn(
        "is_new_listing", F.col("crawl_date") == F.col("first_seen_date")
    )
    snapshot_df = snapshot_df.withColumn(
        "snapshot_status",
        F.when(F.col("is_new_listing"), F.lit("new")).otherwise(F.lit("active")),
    )
    return snapshot_df.withColumnRenamed("crawl_date", "snapshot_date")


def add_price_change_tracking(snapshot_df):
    window_spec = Window.partitionBy("dedup_key").orderBy("snapshot_date")

    snapshot_df = snapshot_df.withColumn(
        "previous_price_vnd", F.lag("price_vnd").over(window_spec)
    )
    snapshot_df = snapshot_df.withColumn("current_price_vnd", F.col("price_vnd"))
    snapshot_df = snapshot_df.withColumn(
        "price_change_vnd",
        F.when(
            F.col("previous_price_vnd").isNotNull()
            & F.col("current_price_vnd").isNotNull(),
            F.col("current_price_vnd") - F.col("previous_price_vnd"),
        ),
    )
    snapshot_df = snapshot_df.withColumn(
        "price_change_pct",
        F.when(
            F.col("previous_price_vnd").isNotNull()
            & F.col("current_price_vnd").isNotNull()
            & (F.col("previous_price_vnd") != 0),
            (F.col("current_price_vnd") - F.col("previous_price_vnd"))
            / F.col("previous_price_vnd"),
        ),
    )
    snapshot_df = snapshot_df.withColumn(
        "is_price_changed",
        F.when(
            F.col("previous_price_vnd").isNotNull()
            & F.col("current_price_vnd").isNotNull()
            & (F.col("previous_price_vnd") != F.col("current_price_vnd"))
            & (F.col("price_unit") != "negotiable"),
            F.lit(True),
        ).otherwise(F.lit(False)),
    )
    return snapshot_df.withColumn(
        "snapshot_status",
        F.when(
            F.col("is_new_listing").eqNullSafe(F.lit(False))
            & F.col("is_price_changed"),
            F.lit("changed_price"),
        ).otherwise(F.col("snapshot_status")),
    )


def add_info_change_tracking(snapshot_df):
    window_spec = Window.partitionBy("dedup_key").orderBy("snapshot_date")
    tracked_fields = [
        "price_vnd",
        "area_m2",
        "title_raw",
        "description_raw",
        "district_norm",
        "property_type_group",
    ]

    df = snapshot_df
    change_expressions = []

    for field_name in tracked_fields:
        if field_name not in df.columns:
            continue

        previous_col = f"previous_{field_name}"
        changed_col = f"is_{field_name}_changed"

        df = df.withColumn(previous_col, F.lag(F.col(field_name)).over(window_spec))
        df = df.withColumn(
            changed_col,
            F.when(
                F.col(previous_col).isNotNull()
                & F.col(field_name).isNotNull()
                & (
                    F.col(previous_col).cast("string")
                    != F.col(field_name).cast("string")
                ),
                F.lit(True),
            ).otherwise(F.lit(False)),
        )

        change_expressions.append(
            F.when(F.col(changed_col), F.lit(field_name)).otherwise(F.lit(None))
        )

    if change_expressions:
        df = df.withColumn("changed_fields", F.concat_ws(",", *change_expressions))
        df = df.withColumn("is_info_changed", F.length(F.col("changed_fields")) > 0)
    else:
        df = df.withColumn("changed_fields", F.lit(""))
        df = df.withColumn("is_info_changed", F.lit(False))

    return df
