"""Daily pipeline run summary generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from common.paths import default_daily_logs_dir, default_pipeline_logs_dir
from validation.publish_gate import evaluate_publish_gate

SUMMARY_SCHEMA_VERSION = "daily_run_summary_v1"
PRODUCTION_SUMMARY_SCHEMA_VERSION = "production_run_summary_v2"

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
    "warnings",
    "errors",
    "artifact_paths",
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

PRODUCTION_SUMMARY_FIELDS = (
    "summary_schema_version",
    "run_id",
    "run_date",
    "pipeline_mode",
    "run_class",
    "pipeline_status",
    "validation_status",
    "publish_status",
    "publish_block_reason",
    "source_names",
    "crawl_ids_created",
    "crawl_configs",
    "warnings",
    "errors",
    "artifact_paths",
    "bronze_records_written",
    "silver_records_written",
    "silver_quarantine_count",
    "gold_snapshot_records",
    "warehouse_fact_records",
    "total_current_listings",
    "duplicate_record_count",
    "duplicate_rate",
    "parse_success_rate",
    "missing_price_rate",
    "missing_area_rate",
    "missing_location_rate",
    "snapshot_dates",
    "start_time",
    "end_time",
    "duration_seconds",
    "error_message",
    "input_silver_partitions",
    "published_outputs",
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
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        artifact_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a stable daily run summary from pipeline state and metrics."""
        metrics = gold_summary or {}
        normalized_status = (
            "failed" if pipeline_status == "failed" or error_message else pipeline_status
        )
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
            "warnings": _to_list(warnings),
            "errors": _to_list(errors),
            "artifact_paths": _to_list(artifact_paths),
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
        output_dir: Path | str = default_daily_logs_dir(),
    ) -> Path:
        """Write summary JSON to disk and print the written path."""
        run_date = summary.get("run_date")
        if not run_date:
            raise ValueError("summary must contain run_date")

        output_path = Path(output_dir) / f"run_date={run_date}" / "daily_run_summary.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Daily run summary written to: {output_path}")
        return output_path


class ProductionRunSummary:
    """Generates v2 production-oriented run summaries and latest-run pointers."""

    def generate_summary(
        self,
        run_id: str,
        run_date: str,
        pipeline_status: str,
        validation_status: str,
        start_time: str,
        end_time: str,
        duration_seconds: int | float,
        pipeline_mode: str = "full",
        run_class: str | None = None,
        source_names: list[str] | None = None,
        crawl_ids_created: list[str] | None = None,
        crawl_configs: list[str] | None = None,
        gold_summary: dict[str, Any] | None = None,
        publish_status: str | None = None,
        publish_block_reason: str | None = None,
        published_outputs: list[str] | None = None,
        input_silver_partitions: list[str] | None = None,
        bronze_records_written: int | float | None = None,
        silver_records_written: int | float | None = None,
        silver_quarantine_count: int | float | None = None,
        gold_snapshot_records: int | float | None = None,
        warehouse_fact_records: int | float | None = None,
        error_message: str | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        artifact_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a v2 summary while accepting current Gold summary metrics."""
        metrics = gold_summary or {}
        normalized_mode = str(pipeline_mode)
        normalized_run_class = run_class or _default_run_class(normalized_mode)
        normalized_status = (
            "failed" if pipeline_status == "failed" or error_message else str(pipeline_status)
        )
        total_silver_records = (
            _to_int(silver_records_written)
            if silver_records_written is not None
            else _metric_int(metrics, "total_silver_records")
        )

        if publish_status is None:
            publish_status, publish_block_reason = _default_publish_state(
                pipeline_mode=normalized_mode,
                run_class=normalized_run_class,
                pipeline_status=normalized_status,
                validation_status=str(validation_status),
                silver_records_written=total_silver_records,
                publish_block_reason=publish_block_reason,
            )

        summary = {
            "summary_schema_version": PRODUCTION_SUMMARY_SCHEMA_VERSION,
            "run_id": str(run_id),
            "run_date": str(run_date),
            "pipeline_mode": normalized_mode,
            "run_class": normalized_run_class,
            "pipeline_status": normalized_status,
            "validation_status": str(validation_status),
            "publish_status": str(publish_status),
            "publish_block_reason": publish_block_reason,
            "source_names": _to_list(source_names),
            "crawl_ids_created": _to_list(crawl_ids_created),
            "crawl_configs": _to_list(crawl_configs),
            "warnings": _to_list(warnings),
            "errors": _to_list(errors),
            "artifact_paths": _to_list(artifact_paths),
            "bronze_records_written": _to_int(bronze_records_written),
            "silver_records_written": total_silver_records,
            "silver_quarantine_count": _to_int(silver_quarantine_count),
            "gold_snapshot_records": _to_int(gold_snapshot_records),
            "warehouse_fact_records": _to_int(warehouse_fact_records),
            "total_current_listings": _metric_int(metrics, "total_current_listings"),
            "duplicate_record_count": _metric_int(metrics, "duplicate_record_count"),
            "duplicate_rate": _metric_float(metrics, "duplicate_rate"),
            "parse_success_rate": _metric_float(metrics, "parse_success_rate"),
            "missing_price_rate": _metric_float(metrics, "missing_price_rate"),
            "missing_area_rate": _metric_float(metrics, "missing_area_rate"),
            "missing_location_rate": _metric_float(metrics, "missing_location_rate"),
            "snapshot_dates": _to_list(metrics.get("snapshot_dates")),
            "start_time": str(start_time),
            "end_time": str(end_time),
            "duration_seconds": _to_int(duration_seconds),
            "error_message": error_message,
            "input_silver_partitions": _to_list(input_silver_partitions),
            "published_outputs": _to_list(published_outputs),
        }
        return {field: summary[field] for field in PRODUCTION_SUMMARY_FIELDS}

    def write_summary(
        self,
        summary: dict[str, Any],
        output_dir: Path | str = default_pipeline_logs_dir(),
    ) -> Path:
        """Atomically write a v2 run summary and update the production pointer."""
        run_id = summary.get("run_id")
        if not run_id:
            raise ValueError("summary must contain run_id")

        output_root = Path(output_dir)
        output_path = output_root / f"run_id={run_id}" / "run_summary.json"
        _atomic_write_json(output_path, summary)
        print(f"Production run summary written to: {output_path}")

        if is_published_production_summary(summary):
            self.write_latest_production_pointer(summary, output_path, output_root)
        return output_path

    def write_latest_production_pointer(
        self,
        summary: dict[str, Any],
        summary_path: Path,
        output_dir: Path | str = default_pipeline_logs_dir(),
    ) -> Path:
        pointer_path = Path(output_dir) / "latest_production.json"
        pointer = {
            "run_id": summary["run_id"],
            "run_date": summary["run_date"],
            "summary_path": str(summary_path),
        }
        _atomic_write_json(pointer_path, pointer)
        print(f"Latest production pointer written to: {pointer_path}")
        return pointer_path


def is_published_production_summary(summary: dict[str, Any]) -> bool:
    """Return true when a summary is eligible for latest production selection."""
    return (
        summary.get("run_class") == "production"
        and summary.get("pipeline_status") == "success"
        and summary.get("publish_status") == "published"
    )


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


def _default_run_class(pipeline_mode: str) -> str:
    if pipeline_mode == "full":
        return "production"
    if pipeline_mode == "smoke":
        return "smoke"
    if pipeline_mode in {"backfill", "reparse"}:
        return "manual"
    return "test"


def _default_publish_state(
    pipeline_mode: str,
    run_class: str,
    pipeline_status: str,
    validation_status: str,
    silver_records_written: int,
    publish_block_reason: str | None,
) -> tuple[str, str | None]:
    decision = evaluate_publish_gate(
        pipeline_mode=pipeline_mode,
        run_class=run_class,
        pipeline_status=pipeline_status,
        validation_status=validation_status,
        silver_records_written=silver_records_written,
    )
    return decision.status, publish_block_reason or decision.block_reason


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
