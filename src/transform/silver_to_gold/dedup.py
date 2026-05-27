from __future__ import annotations

from pyspark.sql import Window
from pyspark.sql import functions as F

from .schema_utils import ensure_columns


def add_dedup_key(df):
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
        normalized_url = F.lower(
            F.regexp_extract(F.col("listing_url").cast("string"), r"^[^?#]+", 0)
        )
        normalized_url = F.regexp_replace(normalized_url, r"/+$", "")
        url_key = F.when(
            F.length(F.trim(F.col("listing_url").cast("string"))) > 0,
            F.concat_ws("::", source_col, normalized_url),
        )

    fallback_string_parts = [source_col]

    if "title_raw" in df.columns:
        fallback_string_parts.append(
            F.lower(F.trim(F.coalesce(F.col("title_raw").cast("string"), F.lit(""))))
        )
    else:
        fallback_string_parts.append(F.lit(""))

    if "district_norm" in df.columns:
        fallback_string_parts.append(
            F.lower(F.trim(F.coalesce(F.col("district_norm").cast("string"), F.lit(""))))
        )
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
        dedup_method_expr = F.when(id_key.isNotNull(), F.lit("listing_id")).otherwise(
            F.lit("content_hash")
        )
    elif url_key is not None:
        dedup_method_expr = F.when(url_key.isNotNull(), F.lit("listing_url")).otherwise(
            F.lit("content_hash")
        )
    else:
        dedup_method_expr = F.lit("content_hash")

    if "dedup_key" not in df.columns:
        return df.withColumn("dedup_key", dedup_key_expr).withColumn(
            "dedup_method", dedup_method_expr
        )

    existing_key_col = "__existing_dedup_key"
    had_existing_key_col = "__had_existing_dedup_key"
    df = df.withColumn(existing_key_col, F.trim(F.col("dedup_key").cast("string")))
    df = df.withColumn(had_existing_key_col, F.length(F.col(existing_key_col)) > 0)
    df = df.withColumn(
        "dedup_key",
        F.when(F.col(had_existing_key_col), F.col(existing_key_col)).otherwise(dedup_key_expr),
    )

    if "dedup_method" in df.columns:
        existing_method = F.trim(F.col("dedup_method").cast("string"))
        has_existing_method = F.length(existing_method) > 0
        dedup_method = (
            F.when(has_existing_method, existing_method)
            .when(F.col(had_existing_key_col), F.lit("preexisting"))
            .otherwise(dedup_method_expr)
        )
    else:
        dedup_method = F.when(F.col(had_existing_key_col), F.lit("preexisting")).otherwise(
            dedup_method_expr
        )

    return df.withColumn("dedup_method", dedup_method).drop(existing_key_col, had_existing_key_col)


def add_duplicate_flags(df):
    if "dedup_key" not in df.columns:
        df = add_dedup_key(df)

    duplicate_group = df.groupBy("crawl_date", "dedup_key").agg(
        F.count("*").alias("duplicate_group_size")
    )
    df = df.join(duplicate_group, on=["crawl_date", "dedup_key"], how="left")
    return df.withColumn("is_duplicate_in_snapshot", F.col("duplicate_group_size") > 1)


def dedup_daily(df):
    df = ensure_columns(
        df,
        {
            "processed_at": None,
            "crawl_id": None,
            "listing_url": None,
            "parse_status": None,
            "price_vnd": None,
            "price_unit": None,
            "area_m2": None,
            "district_norm": None,
            "location_raw": None,
        },
    )

    df = df.withColumn(
        "quality_score",
        F.lit(0)
        + F.when(F.col("parse_status") == "success", 10).otherwise(0)
        + F.when(F.col("price_vnd").isNotNull(), 5).otherwise(0)
        + F.when(F.col("price_unit") == "negotiable", 3).otherwise(0)
        + F.when(F.col("area_m2").isNotNull(), 5).otherwise(0)
        + F.when(F.col("district_norm").isNotNull(), 3).otherwise(0)
        + F.when(F.col("location_raw").isNotNull(), 2).otherwise(0),
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
