from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pyspark.sql import functions as F

from .schema_utils import cast_void_columns_to_string
from .spark_session import log_step


def write_gold_table(df, output_path: str, partition_cols=None):
    writer = df.write.mode("overwrite")
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)

    writer.parquet(output_path)

    sample_path = output_path + "_csv_sample"
    sample_df = cast_void_columns_to_string(df.limit(1000)).coalesce(1)
    sample_df.write.mode("overwrite").option("header", True).csv(sample_path)


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
            duplicate_record_count / total_silver_records if total_silver_records else 0.0
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
    output_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log_step(f"Phase 3 summary written to: {output_file}")
