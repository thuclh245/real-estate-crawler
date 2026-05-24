from __future__ import annotations

from functools import reduce
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from .schema_utils import cast_void_columns_to_string
from .spark_session import log_step


def read_silver(spark: SparkSession, silver_base_path: str):
    silver_path = Path(silver_base_path)
    log_step(f"Reading silver data from base path: {silver_path}")

    parquet_files = list(silver_path.glob("source=*/crawl_date=*/crawl_id=*/listings.parquet"))
    log_step(f"Found {len(parquet_files)} parquet file(s) in crawl_id-partitioned layout")

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
    dataframes = []
    for path in paths:
        df_part = spark.read.parquet(path)
        df_part = cast_void_columns_to_string(df_part)
        dataframes.append(df_part)

    df = reduce(
        lambda left, right: left.unionByName(right, allowMissingColumns=True),
        dataframes,
    )
    log_step(f"Initial columns: {', '.join(df.columns)}")

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
