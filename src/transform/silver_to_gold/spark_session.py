from __future__ import annotations

from pathlib import Path

from pyspark.sql import SparkSession


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
