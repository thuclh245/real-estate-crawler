from __future__ import annotations

from pyspark.sql import Window
from pyspark.sql import functions as F


def build_listing_lifecycle(daily_deduped_df):
    return daily_deduped_df.groupBy("dedup_key").agg(
        F.min("crawl_date").alias("first_seen_date"),
        F.max("crawl_date").alias("last_seen_date"),
        F.countDistinct("crawl_date").alias("active_days"),
    )


def build_removed_listings(daily_deduped_df):
    dates_df = daily_deduped_df.select("crawl_date").distinct()

    # Thu thập danh sách ngày về Driver (vì chỉ có khoảng 20-30 ngày)
    sorted_dates = sorted([row["crawl_date"] for row in dates_df.collect()])

    if len(sorted_dates) < 2:
        return (
            daily_deduped_df.limit(0)
            .withColumn("snapshot_date", F.lit(None).cast("string"))
            .withColumn("last_seen_before_removed", F.lit(None).cast("string"))
            .withColumn("snapshot_status", F.lit("removed"))
            .withColumn("is_removed_listing", F.lit(True))
        )

    # Ánh xạ ngày hiện tại -> ngày crawl kế tiếp
    mapping = {}
    for i in range(len(sorted_dates) - 1):
        mapping[sorted_dates[i]] = sorted_dates[i + 1]

    # Xây dựng cột next_crawl_date bằng biểu thức F.when (tránh Window & Join đắt đỏ)
    expr = F.when(F.col("crawl_date") == sorted_dates[0], F.lit(mapping[sorted_dates[0]]))
    for d in sorted_dates[1:-1]:
        expr = expr.when(F.col("crawl_date") == d, F.lit(mapping[d]))
    expr = expr.otherwise(F.lit(None).cast("string"))

    prev_with_next = daily_deduped_df.withColumn("next_crawl_date", expr).filter(
        F.col("next_crawl_date").isNotNull()
    )

    next_presence = daily_deduped_df.select("dedup_key", "crawl_date").withColumnRenamed(
        "crawl_date", "next_crawl_date"
    )

    removed_df = (
        prev_with_next.join(next_presence, on=["dedup_key", "next_crawl_date"], how="left_anti")
        .withColumn("snapshot_date", F.col("next_crawl_date"))
        .withColumn("last_seen_before_removed", F.col("crawl_date"))
        .withColumn("snapshot_status", F.lit("removed"))
        .withColumn("is_removed_listing", F.lit(True))
        .drop("next_crawl_date")
    )

    return removed_df
