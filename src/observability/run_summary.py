"""Daily pipeline run summary generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUMMARY_SCHEMA_VERSION = "daily_run_summary_v1"

REQUIRED_SUMMARY_FIELDS = (
    "run_id",
    "run_date",
    "pipeline_status",
    "validation_status",
    "gcs_sync_status",
    "total_silver_records",
    "total_current_listings",
    "duplicate_rate",
    "parse_success_rate",
    "missing_price_rate",
    "snapshot_dates",
    "start_time",
    "end_time",
    "duration_seconds",
)

SUMMARY_FIELDS = (
    "summary_schema_version",
    "run_id",
    "run_date",
    "pipeline_mode",
    "pipeline_status",
    "validation_status",
    "gcs_sync_status",
    "error_message",
    "start_time",
    "end_time",
    "duration_seconds",
    "crawl_configs",
    "crawl_ids_created",
    "total_silver_records",
    "total_current_listings",
    "duplicate_record_count",
    "duplicate_rate",
    "parse_success_rate",
    "missing_price_rate",
    "missing_area_rate",
    "missing_location_rate",
    "snapshot_dates",
)


class DailyRunSummary:
    """Generates and writes daily_run_summary.json files."""

    def generate_summary(
        self,
        run_id: str,
        run_date: str,
        pipeline_status: str,
        validation_status: str,
        gcs_sync_status: str,
        start_time: str,
        end_time: str,
        duration_seconds: int | float,
        error_message: str | None = None,
        gold_summary: dict[str, Any] | None = None,
        crawl_configs: list[str] | None = None,
        crawl_ids_created: list[str] | None = None,
        pipeline_mode: str = "full",
    ) -> dict[str, Any]:
        """Generate a stable daily run summary from pipeline state and metrics."""
        metrics = gold_summary or {}
        normalized_status = "failed" if pipeline_status == "failed" or error_message else pipeline_status
        normalized_error = error_message
        if normalized_status == "failed" and not normalized_error:
            normalized_error = "Pipeline failed"

        summary = {
            "summary_schema_version": SUMMARY_SCHEMA_VERSION,
            "run_id": str(run_id),
            "run_date": str(run_date),
            "pipeline_mode": str(pipeline_mode),
            "pipeline_status": str(normalized_status),
            "validation_status": str(validation_status),
            "gcs_sync_status": str(gcs_sync_status),
            "error_message": normalized_error,
            "start_time": str(start_time),
            "end_time": str(end_time),
            "duration_seconds": _to_int(duration_seconds),
            "crawl_configs": _to_list(crawl_configs),
            "crawl_ids_created": _to_list(crawl_ids_created),
            "total_silver_records": _metric_int(metrics, "total_silver_records"),
            "total_current_listings": _metric_int(metrics, "total_current_listings"),
            "duplicate_record_count": _metric_int(metrics, "duplicate_record_count"),
            "duplicate_rate": _metric_float(metrics, "duplicate_rate"),
            "parse_success_rate": _metric_float(metrics, "parse_success_rate"),
            "missing_price_rate": _metric_float(metrics, "missing_price_rate"),
            "missing_area_rate": _metric_float(metrics, "missing_area_rate"),
            "missing_location_rate": _metric_float(metrics, "missing_location_rate"),
            "snapshot_dates": _to_list(metrics.get("snapshot_dates")),
        }

        return {field: summary[field] for field in SUMMARY_FIELDS}

    def write_summary(
        self,
        summary: dict[str, Any],
        output_dir: Path | str = Path("data/logs/daily_pipeline"),
    ) -> Path:
        """Write summary JSON to disk and print the written path."""
        run_date = summary.get("run_date")
        if not run_date:
            raise ValueError("summary must contain run_date")

        output_path = (
            Path(output_dir)
            / f"run_date={run_date}"
            / "daily_run_summary.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Daily run summary written to: {output_path}")
        return output_path


def _metric_int(metrics: dict[str, Any], key: str) -> int:
    return _to_int(metrics.get(key, 0))


def _metric_float(metrics: dict[str, Any], key: str) -> float:
    return _to_float(metrics.get(key, 0.0))


def _to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
