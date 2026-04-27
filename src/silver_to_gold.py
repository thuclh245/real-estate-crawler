import json
from datetime import datetime
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

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


def log_step(message: str) -> None:
    print(f"[silver_to_gold] {message}")

def create_spark() -> SparkSession:
    warehouse_dir = Path("spark-warehouse").resolve().as_uri()

    return (
        SparkSession.builder
        .appName("SilverToGoldRealEstate")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "Asia/Ho_Chi_Minh")
        .config("spark.sql.warehouse.dir", warehouse_dir)
        .getOrCreate()
    )

def read_silver(spark: SparkSession, silver_base_path: str):
    silver_path = Path(silver_base_path)
    log_step(f"Reading silver data from base path: {silver_path}")

    # New layout: source=*/crawl_date=*/crawl_id=*/listings.parquet
    parquet_files = list(silver_path.glob("source=*/crawl_date=*/crawl_id=*/listings.parquet"))
    log_step(f"Found {len(parquet_files)} parquet file(s) in crawl_id-partitioned layout")

    # Backward compatibility: source=*/crawl_date=*/listings.parquet
    if not parquet_files:
        log_step("No files found in crawl_id layout, falling back to legacy crawl_date layout")
        parquet_files = list(silver_path.glob("source=*/crawl_date=*/listings.parquet"))
        log_step(f"Found {len(parquet_files)} parquet file(s) in legacy layout")

    if not parquet_files:
        raise FileNotFoundError(
            f"Cannot find listings.parquet under {silver_base_path}/source=*/crawl_date=*/(crawl_id=*/ )"
        )

    paths = [str(p) for p in parquet_files]
    preview = paths[:3]
    log_step("Sample parquet paths:")
    for p in preview:
        print(f"  - {p}")
    if len(paths) > len(preview):
        log_step(f"... and {len(paths) - len(preview)} more file(s)")

    log_step("Loading parquet files into Spark DataFrame")
    df = spark.read.parquet(*paths)
    log_step(f"Initial columns: {', '.join(df.columns)}")

    # Fill partition columns from input file path if they are missing.
    if "crawl_date" not in df.columns:
        log_step("Column 'crawl_date' is missing, extracting from input file path")
        df = df.withColumn(
            "crawl_date",
            F.regexp_extract(F.input_file_name(), r"crawl_date=([0-9]{4}-[0-9]{2}-[0-9]{2})", 1),
        )

    if "source" not in df.columns:
        log_step("Column 'source' is missing, extracting from input file path")
        df = df.withColumn(
            "source",
            F.regexp_extract(F.input_file_name(), r"source=([^/\\]+)", 1),
        )

    if "crawl_id" not in df.columns:
        log_step("Column 'crawl_id' is missing, extracting from input file path")
        df = df.withColumn(
            "crawl_id",
            F.regexp_extract(F.input_file_name(), r"crawl_id=([^/\\]+)", 1),
        )

    log_step("Silver DataFrame is ready")

    return df

def build_listing_lifecycle(daily_deduped_df):
    """
    Tạo lifecycle cho mỗi listing:
    - first_seen_date
    - last_seen_date
    - active_days
    """

    lifecycle_df = (
        daily_deduped_df
        .groupBy("dedup_key")
        .agg(
            F.min("crawl_date").alias("first_seen_date"),
            F.max("crawl_date").alias("last_seen_date"),
            F.countDistinct("crawl_date").alias("active_days")
        )
    )

    return lifecycle_df

def add_dedup_key(df):
    """
    Tạo dedup_key ổn định cho mỗi listing để dùng xuyên suốt các bước Silver -> Gold.
    Ưu tiên listing_id, sau đó listing_url, cuối cùng mới fallback theo từng dòng.
    """

    if "dedup_key" in df.columns:
        if "dedup_method" not in df.columns:
            df = df.withColumn("dedup_method", F.lit("preexisting"))
        return df

    source_col = (
        F.coalesce(F.col("source").cast("string"), F.lit("unknown_source"))
        if "source" in df.columns
        else F.lit("unknown_source")
    )

    id_key = None
    if "listing_id" in df.columns:
        normalized_listing_id = F.trim(F.col("listing_id").cast("string"))
        id_key = F.when(
            F.length(normalized_listing_id) > 0,
            F.concat_ws("::", source_col, normalized_listing_id),
        )

    url_key = None
    if "listing_url" in df.columns:
        normalized_url = F.lower(F.regexp_extract(F.col("listing_url").cast("string"), r"^[^?#]+", 0))
        normalized_url = F.regexp_replace(normalized_url, r"/+$", "")
        url_key = F.when(
            F.length(F.trim(F.col("listing_url").cast("string"))) > 0,
            F.concat_ws("::", source_col, normalized_url),
        )

    fallback_string_parts = [source_col]

    if "title_raw" in df.columns:
        fallback_string_parts.append(F.lower(F.trim(F.coalesce(F.col("title_raw").cast("string"), F.lit("")))))
    else:
        fallback_string_parts.append(F.lit(""))

    if "district_norm" in df.columns:
        fallback_string_parts.append(F.lower(F.trim(F.coalesce(F.col("district_norm").cast("string"), F.lit("")))))
    else:
        fallback_string_parts.append(F.lit(""))

    if "area_m2" in df.columns:
        fallback_string_parts.append(F.coalesce(F.col("area_m2").cast("string"), F.lit("")))
    else:
        fallback_string_parts.append(F.lit(""))

    if "price_vnd" in df.columns:
        fallback_string_parts.append(F.coalesce(F.col("price_vnd").cast("string"), F.lit("")))
    else:
        fallback_string_parts.append(F.lit(""))

    fallback_string = F.concat_ws("||", *fallback_string_parts)
    fallback_key = F.concat_ws("::", source_col, F.sha2(fallback_string, 256))
    candidates = [c for c in [id_key, url_key] if c is not None]

    if candidates:
        dedup_key_expr = F.coalesce(*candidates, fallback_key)
    else:
        dedup_key_expr = fallback_key

    if id_key is not None and url_key is not None:
        dedup_method_expr = (
            F.when(id_key.isNotNull(), F.lit("listing_id"))
             .when(url_key.isNotNull(), F.lit("listing_url"))
             .otherwise(F.lit("content_hash"))
        )
    elif id_key is not None:
        dedup_method_expr = F.when(id_key.isNotNull(), F.lit("listing_id")).otherwise(F.lit("content_hash"))
    elif url_key is not None:
        dedup_method_expr = F.when(url_key.isNotNull(), F.lit("listing_url")).otherwise(F.lit("content_hash"))
    else:
        dedup_method_expr = F.lit("content_hash")

    return (
        df.withColumn("dedup_key", dedup_key_expr)
          .withColumn("dedup_method", dedup_method_expr)
    )

def ensure_columns(df, columns_with_default):
    for col_name, default_value in columns_with_default.items():
        if col_name not in df.columns:
            df = df.withColumn(col_name, F.lit(default_value))
    return df

def dedup_daily(df):
    """
    Giữ lại 1 record cho mỗi dedup_key trong cùng crawl_date.
    Ưu tiên bản ghi có processed_at mới hơn, rồi crawl_id, rồi listing_url.
    """

    df = ensure_columns(df, {
        "processed_at": None,
        "crawl_id": None,
        "listing_url": None,
        "parse_status": None,
        "price_vnd": None,
        "price_unit": None,
        "area_m2": None,
        "district_norm": None,
        "location_raw": None,
    })

    df = df.withColumn(
        "quality_score",
        F.lit(0)
        + F.when(F.col("parse_status") == "success", 10).otherwise(0)
        + F.when(F.col("price_vnd").isNotNull(), 5).otherwise(0)
        + F.when(F.col("price_unit") == "negotiable", 3).otherwise(0)
        + F.when(F.col("area_m2").isNotNull(), 5).otherwise(0)
        + F.when(F.col("district_norm").isNotNull(), 3).otherwise(0)
        + F.when(F.col("location_raw").isNotNull(), 2).otherwise(0)
    )

    window_spec = Window.partitionBy("crawl_date", "dedup_key").orderBy(
        F.col("quality_score").desc(),
        F.col("processed_at").desc_nulls_last(),
        F.col("crawl_id").desc_nulls_last(),
        F.col("listing_url").desc_nulls_last(),
    )

    return (
        df.withColumn("dedup_row_number", F.row_number().over(window_spec))
          .filter(F.col("dedup_row_number") == 1)
          .drop("dedup_row_number")
    )

def build_snapshot_table(daily_deduped_df, lifecycle_df):
    """
    Tạo bảng snapshot theo từng ngày.
    Mỗi record = 1 listing xuất hiện trong 1 ngày crawl.
    """

    snapshot_df = daily_deduped_df.join(
        lifecycle_df,
        on="dedup_key",
        how="left"
    )

    snapshot_df = snapshot_df.withColumn(
        "is_new_listing",
        F.col("crawl_date") == F.col("first_seen_date")
    )

    snapshot_df = snapshot_df.withColumn(
        "snapshot_status",
        F.when(F.col("is_new_listing"), F.lit("new"))
         .otherwise(F.lit("active"))
    )

    snapshot_df = snapshot_df.withColumnRenamed("crawl_date", "snapshot_date")

    return snapshot_df

def add_price_change_tracking(snapshot_df):
    """
    So sánh price_vnd của cùng dedup_key theo thời gian.
    """

    window_spec = Window.partitionBy("dedup_key").orderBy("snapshot_date")

    snapshot_df = snapshot_df.withColumn(
        "previous_price_vnd",
        F.lag("price_vnd").over(window_spec)
    )

    snapshot_df = snapshot_df.withColumn(
        "current_price_vnd",
        F.col("price_vnd")
    )

    snapshot_df = snapshot_df.withColumn(
        "price_change_vnd",
        F.when(
            F.col("previous_price_vnd").isNotNull() & F.col("current_price_vnd").isNotNull(),
            F.col("current_price_vnd") - F.col("previous_price_vnd")
        )
    )

    snapshot_df = snapshot_df.withColumn(
        "price_change_pct",
        F.when(
            F.col("previous_price_vnd").isNotNull()
            & F.col("current_price_vnd").isNotNull()
            & (F.col("previous_price_vnd") != 0),
            (F.col("current_price_vnd") - F.col("previous_price_vnd")) / F.col("previous_price_vnd")
        )
    )

    snapshot_df = snapshot_df.withColumn(
        "is_price_changed",
        F.when(
            F.col("previous_price_vnd").isNotNull()
            & F.col("current_price_vnd").isNotNull()
            & (F.col("previous_price_vnd") != F.col("current_price_vnd"))
            & (F.col("price_unit") != "negotiable"),
            F.lit(True)
        ).otherwise(F.lit(False))
    )

    snapshot_df = snapshot_df.withColumn(
        "snapshot_status",
        F.when(
            F.col("is_new_listing").eqNullSafe(F.lit(False)) & F.col("is_price_changed"),
            F.lit("changed_price")
        )
         .otherwise(F.col("snapshot_status"))
    )

    return snapshot_df

def add_duplicate_flags(df):
    """
    Tính duplicate trong cùng một crawl_date.
    Nếu cùng crawl_date + dedup_key có nhiều record thì đó là duplicate trong snapshot.
    """

    if "dedup_key" not in df.columns:
        df = add_dedup_key(df)

    duplicate_group = (
        df.groupBy("crawl_date", "dedup_key")
        .agg(F.count("*").alias("duplicate_group_size"))
    )

    df = df.join(duplicate_group, on=["crawl_date", "dedup_key"], how="left")

    df = df.withColumn(
        "is_duplicate_in_snapshot",
        F.col("duplicate_group_size") > 1
    )

    return df

def build_removed_listings(daily_deduped_df):
    """
    Tạo record removed:
    Nếu listing xuất hiện ở ngày trước nhưng không xuất hiện ở ngày sau,
    thì tạo 1 record removed tại ngày sau.
    """

    dates = [
        row["crawl_date"]
        for row in daily_deduped_df.select("crawl_date").distinct().orderBy("crawl_date").collect()
    ]

    if len(dates) < 2:
        return (
            daily_deduped_df.limit(0)
            .withColumn("snapshot_date", F.lit(None).cast("string"))
            .withColumn("last_seen_before_removed", F.lit(None).cast("string"))
            .withColumn("snapshot_status", F.lit("removed"))
            .withColumn("is_removed_listing", F.lit(True))
        )

    removed_dfs = []

    for i in range(1, len(dates)):
        prev_date = dates[i - 1]
        curr_date = dates[i]

        prev_df = (
            daily_deduped_df
            .filter(F.col("crawl_date") == prev_date)
        )

        curr_df = (
            daily_deduped_df
            .filter(F.col("crawl_date") == curr_date)
            .select("dedup_key")
            .distinct()
        )

        removed_keys = (
            prev_df.join(curr_df, on="dedup_key", how="left_anti")
            .withColumn("snapshot_date", F.lit(curr_date))
            .withColumn("last_seen_before_removed", F.lit(prev_date))
            .withColumn("snapshot_status", F.lit("removed"))
            .withColumn("is_removed_listing", F.lit(True))
        )

        removed_dfs.append(removed_keys)

    if not removed_dfs:
        return (
            daily_deduped_df.limit(0)
            .withColumn("snapshot_date", F.lit(None).cast("string"))
            .withColumn("last_seen_before_removed", F.lit(None).cast("string"))
            .withColumn("snapshot_status", F.lit("removed"))
            .withColumn("is_removed_listing", F.lit(True))
        )

    result = removed_dfs[0]
    for df in removed_dfs[1:]:
        result = result.unionByName(df)

    return result

def build_gold_current_listings(snapshot_df):
    """
    Lấy trạng thái mới nhất của mỗi listing.
    """

    window_spec = Window.partitionBy("dedup_key").orderBy(F.col("snapshot_date").desc())

    current_df = (
        snapshot_df
        .withColumn("rn", F.row_number().over(window_spec))
        .filter(F.col("rn") == 1)
        .drop("rn")
    )

    return current_df

def build_gold_market_by_district_daily(snapshot_df):
    """
    Aggregation theo ngày + quận + loại BĐS.
    """

    df = snapshot_df.filter(F.col("snapshot_status") != "removed")

    result = (
        df.groupBy("snapshot_date", "city_norm", "district_norm", "property_type_group")
        .agg(
            F.count("*").alias("listing_count"),
            F.expr("percentile_approx(price_vnd, 0.5)").alias("median_price_vnd"),
            F.avg("price_vnd").alias("avg_price_vnd"),
            F.expr("percentile_approx(area_m2, 0.5)").alias("median_area_m2"),
            F.expr("percentile_approx(unit_price_vnd_m2, 0.5)").alias("median_unit_price_vnd_m2"),
            F.avg("unit_price_vnd_m2").alias("avg_unit_price_vnd_m2"),
            F.sum(F.when(F.col("snapshot_status") == "new", 1).otherwise(0)).alias("new_listing_count"),
            F.sum(F.when(F.col("is_price_changed"), 1).otherwise(0)).alias("price_changed_count"),
            F.sum(F.when(F.col("price_unit") == "negotiable", 1).otherwise(0)).alias("negotiable_price_count")
        )
    )

    return result

def build_gold_market_by_property_type_daily(snapshot_df):
    """
    Aggregation theo ngày + loại bất động sản.
    """

    df = snapshot_df.filter(F.col("snapshot_status") != "removed")

    result = (
        df.groupBy("snapshot_date", "property_type_group")
        .agg(
            F.count("*").alias("listing_count"),
            F.expr("percentile_approx(price_vnd, 0.5)").alias("median_price_vnd"),
            F.avg("price_vnd").alias("avg_price_vnd"),
            F.expr("percentile_approx(area_m2, 0.5)").alias("median_area_m2"),
            F.expr("percentile_approx(unit_price_vnd_m2, 0.5)").alias("median_unit_price_vnd_m2"),
            F.sum(F.when(F.col("price_unit") == "negotiable", 1).otherwise(0)).alias("negotiable_price_count"),
            F.sum(F.when(F.col("snapshot_status") == "new", 1).otherwise(0)).alias("new_listing_count"),
            F.sum(F.when(F.col("is_price_changed"), 1).otherwise(0)).alias("price_changed_count"),
        )
    )

    return result

def build_gold_data_quality_daily(df_before_dedup, df_after_dedup):
    """
    Tạo bảng data quality daily.
    """

    base_quality = (
        df_before_dedup
        .groupBy("crawl_date", "source")
        .agg(
            F.count("*").alias("total_records"),
            F.sum(F.when(F.col("parse_status") == "success", 1).otherwise(0)).alias("parse_success_count"),
            F.sum(F.when(F.col("is_missing_price"), 1).otherwise(0)).alias("missing_price_count"),
            F.sum(F.when(F.col("is_price_negotiable"), 1).otherwise(0)).alias("negotiable_price_count"),
            F.sum(F.when(F.col("is_missing_area"), 1).otherwise(0)).alias("missing_area_count"),
            F.sum(F.when(F.col("is_missing_location"), 1).otherwise(0)).alias("missing_location_count"),
            F.sum(F.when(F.col("is_invalid_price"), 1).otherwise(0)).alias("invalid_price_count"),
            F.sum(F.when(F.col("is_invalid_area"), 1).otherwise(0)).alias("invalid_area_count"),
            F.sum(F.when(F.col("is_duplicate_in_snapshot"), 1).otherwise(0)).alias("duplicate_record_count"),
            F.countDistinct("dedup_key").alias("distinct_dedup_key_count")
        )
    )

    quality = (
        base_quality
        .withColumn("parse_success_rate", F.col("parse_success_count") / F.col("total_records"))
        .withColumn("missing_price_rate", F.col("missing_price_count") / F.col("total_records"))
        .withColumn("negotiable_price_rate", F.col("negotiable_price_count") / F.col("total_records"))
        .withColumn("missing_area_rate", F.col("missing_area_count") / F.col("total_records"))
        .withColumn("missing_location_rate", F.col("missing_location_count") / F.col("total_records"))
        .withColumn("invalid_price_rate", F.col("invalid_price_count") / F.col("total_records"))
        .withColumn("invalid_area_rate", F.col("invalid_area_count") / F.col("total_records"))
        .withColumn("duplicate_rate", F.col("duplicate_record_count") / F.col("total_records"))
    )

    return quality

def write_gold_table(df, output_path: str, partition_cols=None):
    """
    Ghi Gold table ra Parquet.
    """
    def cast_void_columns_to_string(input_df):
        # Spark CSV cannot write NullType (shown as VOID in error messages).
        result_df = input_df
        for field in result_df.schema.fields:
            if isinstance(field.dataType, T.NullType):
                result_df = result_df.withColumn(field.name, F.col(field.name).cast("string"))
        return result_df

    writer = df.write.mode("overwrite")

    if partition_cols:
        writer = writer.partitionBy(*partition_cols)

    writer.parquet(output_path)

        # Ghi thêm CSV sample để kiểm tra nhanh
    sample_path = output_path + "_csv_sample"
    sample_df = cast_void_columns_to_string(df.limit(1000)).coalesce(1)
    (
        sample_df
        .write
        .mode("overwrite")
        .option("header", True)
        .csv(sample_path)
    )
def write_phase3_summary(
    silver_df,
    snapshot_df,
    gold_current_df,
    gold_quality_df,
    output_path: str,
    gold_tables_created: list[str],
) -> None:
    quality_totals = gold_quality_df.agg(
        F.sum("total_records").alias("total_silver_records"),
        F.sum("parse_success_count").alias("parse_success_count"),
        F.sum("missing_price_count").alias("missing_price_count"),
        F.sum("missing_area_count").alias("missing_area_count"),
        F.sum("missing_location_count").alias("missing_location_count"),
        F.sum("duplicate_record_count").alias("duplicate_record_count"),
    ).collect()[0]

    total_silver_records = int(quality_totals["total_silver_records"] or 0)
    duplicate_record_count = int(quality_totals["duplicate_record_count"] or 0)

    snapshot_dates = [
        row["snapshot_date"]
        for row in snapshot_df.select("snapshot_date").distinct().orderBy("snapshot_date").collect()
    ]

    summary = {
        "total_silver_records": total_silver_records,
        "total_current_listings": int(gold_current_df.count()),
        "duplicate_record_count": duplicate_record_count,
        "duplicate_rate": (
            duplicate_record_count / total_silver_records
            if total_silver_records
            else 0.0
        ),
        "parse_success_rate": (
            int(quality_totals["parse_success_count"] or 0) / total_silver_records
            if total_silver_records
            else 0.0
        ),
        "missing_price_rate": (
            int(quality_totals["missing_price_count"] or 0) / total_silver_records
            if total_silver_records
            else 0.0
        ),
        "missing_area_rate": (
            int(quality_totals["missing_area_count"] or 0) / total_silver_records
            if total_silver_records
            else 0.0
        ),
        "missing_location_rate": (
            int(quality_totals["missing_location_count"] or 0) / total_silver_records
            if total_silver_records
            else 0.0
        ),
        "snapshot_dates": snapshot_dates,
        "gold_tables_created": gold_tables_created,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log_step(f"Phase 3 summary written to: {output_file}")

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
        F.countDistinct("dedup_key").alias("distinct_dedup_keys")
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

    print("=== BUILD REMOVED LISTINGS ===")
    removed_df = build_removed_listings(daily_deduped_df)

    print("=== SNAPSHOT STATUS COUNT ===")
    snapshot_df.groupBy("snapshot_date", "snapshot_status").count().orderBy("snapshot_date", "snapshot_status").show(truncate=False)

    print("=== PRICE CHANGE COUNT ===")
    snapshot_df.groupBy("snapshot_date").agg(
        F.count("*").alias("snapshot_records"),
        F.sum(F.when(F.col("is_price_changed"), 1).otherwise(0)).alias("price_changed_count")
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
    write_gold_table(
        gold_current_df,
        f"{GOLD_BASE_PATH}/gold_current_listings"
    )

    write_gold_table(
        snapshot_df,
        f"{GOLD_BASE_PATH}/gold_listing_snapshots",
        partition_cols=["snapshot_date"]
    )

    write_gold_table(
        gold_market_district_df,
        f"{GOLD_BASE_PATH}/gold_market_by_district_daily",
        partition_cols=["snapshot_date"]
    )

    write_gold_table(
        gold_market_property_type_df,
        f"{GOLD_BASE_PATH}/gold_market_by_property_type_daily",
        partition_cols=["snapshot_date"]
    )

    write_gold_table(
        gold_quality_df,
        f"{GOLD_BASE_PATH}/gold_data_quality_daily",
        partition_cols=["crawl_date"]
    )

    write_gold_table(
        removed_df,
        f"{GOLD_BASE_PATH}/gold_removed_listings",
        partition_cols=["snapshot_date"]
    )

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


if __name__ == "__main__":
    main()
