"""Source-level scorecard generation for onboarding smoke runs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from validation.source_quality_gate import evaluate_source_quality_gate

SOURCE_SCORECARD_SCHEMA_VERSION = "source_scorecard_v1"


def build_source_scorecard(
    *,
    crawl_summary: dict[str, Any],
    silver_quality_summary: dict[str, Any] | None = None,
    quality_config: dict[str, Any] | None = None,
    quarantine_count: int | float | None = None,
    artifact_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Build a normalized source scorecard from crawl and Silver quality artifacts."""
    silver_quality_summary = silver_quality_summary or {}
    source_code = str(
        crawl_summary.get("source")
        or crawl_summary.get("source_code")
        or silver_quality_summary.get("source")
        or silver_quality_summary.get("source_code")
        or "unknown"
    )
    total_records = _first_int(
        silver_quality_summary,
        ("total_records", "total_records_parsed", "total_silver_records"),
        default=_safe_int(crawl_summary.get("success_count")),
    )
    total_metadata_files = _first_int(
        silver_quality_summary,
        ("total_metadata_files",),
        default=total_records,
    )
    quarantined = (
        _safe_int(quarantine_count)
        if quarantine_count is not None
        else _first_int(
            silver_quality_summary,
            ("total_quarantined_records", "quarantine_count"),
            default=0,
        )
    )
    blocked_count = _first_int(
        crawl_summary,
        ("blocked_count", "http_403_count", "http_429_count"),
        default=0,
    )
    requested_count = _first_int(
        crawl_summary,
        ("detail_pages_requested", "listing_pages_requested", "requested_count"),
        default=_safe_int(crawl_summary.get("success_count"))
        + _safe_int(crawl_summary.get("failed_count"))
        + blocked_count,
    )

    metrics = {
        "total_records": total_records,
        "parse_success_rate": _first_float(
            silver_quality_summary,
            ("parse_success_rate",),
            default=1.0 if total_metadata_files and total_records == total_metadata_files else 0.0,
        ),
        "quarantine_count": quarantined,
        "quarantine_rate": _rate(quarantined, total_metadata_files or total_records),
        "missing_price_rate": _first_float(
            silver_quality_summary,
            ("missing_price_rate", "is_missing_price_rate"),
            default=0.0,
        ),
        "missing_area_rate": _first_float(
            silver_quality_summary,
            ("missing_area_rate", "is_missing_area_rate"),
            default=0.0,
        ),
        "missing_location_rate": _first_float(
            silver_quality_summary,
            ("missing_location_rate", "is_missing_location_rate"),
            default=0.0,
        ),
        "duplicate_rate": _first_float(
            silver_quality_summary,
            ("duplicate_rate",),
            default=0.0,
        ),
        "success_count": _safe_int(crawl_summary.get("success_count")),
        "failed_count": _safe_int(crawl_summary.get("failed_count")),
        "blocked_count": blocked_count,
        "blocked_rate": _rate(blocked_count, requested_count),
    }
    gate_decision = evaluate_source_quality_gate(metrics, quality_config)

    return {
        "scorecard_schema_version": SOURCE_SCORECARD_SCHEMA_VERSION,
        "source_code": source_code,
        "crawl_date": str(
            crawl_summary.get("crawl_date")
            or silver_quality_summary.get("crawl_date")
            or ""
        ),
        "crawl_id": str(crawl_summary.get("crawl_id") or ""),
        "run_id": str(
            crawl_summary.get("run_id")
            or crawl_summary.get("crawl_id")
            or ""
        ),
        **metrics,
        "gate_status": gate_decision.status,
        "gate_failures": gate_decision.failures,
        "artifact_paths": list(artifact_paths or []),
    }


def write_source_scorecard(
    scorecard: dict[str, Any],
    output_dir: Path | str,
) -> Path:
    """Write a source scorecard JSON artifact atomically."""
    source_code = str(scorecard.get("source_code") or "unknown")
    crawl_date = str(scorecard.get("crawl_date") or "unknown")
    crawl_id = str(scorecard.get("crawl_id") or "unknown")
    output_path = (
        Path(output_dir)
        / "source_scorecards"
        / f"source={source_code}"
        / f"crawl_date={crawl_date}"
        / f"crawl_id={crawl_id}"
        / "source_scorecard.json"
    )
    _atomic_write_json(output_path, scorecard)
    return output_path


def load_silver_quality_summary(path: Path | str) -> dict[str, Any]:
    """Load Silver data_quality_summary.json."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _first_int(
    payload: dict[str, Any],
    keys: tuple[str, ...],
    *,
    default: int = 0,
) -> int:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return _safe_int(payload[key])
    return default


def _first_float(
    payload: dict[str, Any],
    keys: tuple[str, ...],
    *,
    default: float = 0.0,
) -> float:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return _safe_float(payload[key])
    return default


def _rate(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _safe_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
