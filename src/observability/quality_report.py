"""Data quality report generation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


QUALITY_METRIC_KEYS = (
    "parse_success_rate",
    "duplicate_rate",
    "missing_price_rate",
    "missing_area_rate",
    "missing_location_rate",
    "total_records",
    "total_current_listings",
)

COUNT_METRIC_KEYS = (
    "total_records",
    "total_current_listings",
)

DEFAULT_QUALITY_TOLERANCES = {
    "excellent_parse_success_drop": 0.02,
    "good_parse_success_drop": 0.05,
    "excellent_rate_increase": 0.05,
    "good_rate_increase": 0.10,
}

LOWER_IS_BETTER_RATE_METRICS = (
    "duplicate_rate",
    "missing_price_rate",
    "missing_area_rate",
    "missing_location_rate",
)


class DataQualityReport:
    """Generates data quality reports in markdown and JSON formats."""

    def classify_quality(
        self,
        parse_success_rate: float,
        duplicate_rate: float,
        baseline_metrics: dict[str, Any] | None = None,
        tolerances: dict[str, float] | None = None,
        current_metrics: dict[str, Any] | None = None,
    ) -> str:
        """Classify quality using static guardrails plus optional rolling baseline."""
        current = dict(current_metrics or {})
        current["parse_success_rate"] = parse_success_rate
        current["duplicate_rate"] = duplicate_rate

        if not baseline_metrics:
            return self._classify_with_static_guardrails(parse_success_rate, duplicate_rate)

        effective_tolerances = {
            **DEFAULT_QUALITY_TOLERANCES,
            **(tolerances or {}),
        }

        excellent_parse_floor = max(
            0.95,
            _safe_float(baseline_metrics.get("parse_success_rate"), 1.0)
            - effective_tolerances["excellent_parse_success_drop"],
        )
        good_parse_floor = max(
            0.90,
            _safe_float(baseline_metrics.get("parse_success_rate"), 1.0)
            - effective_tolerances["good_parse_success_drop"],
        )

        parse_success = _safe_float(parse_success_rate, 0.0)
        if parse_success >= excellent_parse_floor and self._rates_within_baseline(
            current,
            baseline_metrics,
            effective_tolerances["excellent_rate_increase"],
        ):
            return "excellent"

        if parse_success >= good_parse_floor and self._rates_within_baseline(
            current,
            baseline_metrics,
            effective_tolerances["good_rate_increase"],
        ):
            return "good"

        return "needs_attention"

    def compute_comparison(
        self,
        current_metrics: dict[str, Any],
        previous_metrics: list[dict[str, Any]] | dict[str, Any] | None,
        window_days: int = 7,
    ) -> dict[str, Any] | None:
        """Compute rolling baseline and deltas between current and baseline metrics."""
        history = _normalize_previous_metrics(previous_metrics)
        if not history:
            return None

        baseline_source = history[-window_days:] if window_days > 0 else history
        normalized_current = _normalize_metrics(current_metrics)
        baseline_metrics = _compute_average_metrics(baseline_source)
        if not baseline_metrics:
            return None

        deltas = {}
        percent_deltas = {}
        for key in QUALITY_METRIC_KEYS:
            current_value = _safe_float(normalized_current.get(key), None)
            baseline_value = _safe_float(baseline_metrics.get(key), None)
            if current_value is None or baseline_value is None:
                continue
            delta = current_value - baseline_value
            deltas[f"{key}_delta"] = delta
            if key in COUNT_METRIC_KEYS and baseline_value != 0:
                percent_deltas[f"{key}_pct_delta"] = delta / baseline_value

        return {
            "window_days": window_days,
            "history_count": len(baseline_source),
            "baseline_metrics": baseline_metrics,
            "deltas": deltas,
            "percent_deltas": percent_deltas,
        }

    def generate_markdown_report(
        self,
        metrics: dict[str, Any],
        comparison: dict[str, Any] | None,
        quality_level: str,
        run_date: str,
    ) -> str:
        """Generate markdown report content."""
        normalized_metrics = _normalize_metrics(metrics)
        lines = [
            f"# Data Quality Report - {run_date}",
            "",
            f"Quality level: `{quality_level}`",
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
        for key in QUALITY_METRIC_KEYS:
            lines.append(f"| {key} | {_format_value(normalized_metrics.get(key))} |")

        if comparison:
            baseline_metrics = comparison.get("baseline_metrics", {})
            deltas = comparison.get("deltas", {})
            percent_deltas = comparison.get("percent_deltas", {})
            lines.extend(
                [
                    "",
                    "## Rolling Baseline Comparison",
                    "",
                    f"Window days: {comparison.get('window_days')}",
                    f"History count: {comparison.get('history_count')}",
                    "",
                    "| Metric | Current | Baseline | Delta | Percent delta |",
                    "|---|---:|---:|---:|---:|",
                ]
            )
            for key in QUALITY_METRIC_KEYS:
                lines.append(
                    "| "
                    f"{key} | "
                    f"{_format_value(normalized_metrics.get(key))} | "
                    f"{_format_value(baseline_metrics.get(key))} | "
                    f"{_format_value(deltas.get(f'{key}_delta'))} | "
                    f"{_format_value(percent_deltas.get(f'{key}_pct_delta'))} |"
                )

        return "\n".join(lines) + "\n"

    def generate_json_report(
        self,
        metrics: dict[str, Any],
        comparison: dict[str, Any] | None,
        quality_level: str,
        run_date: str,
    ) -> dict[str, Any]:
        """Generate structured JSON report."""
        return {
            "report_date": run_date,
            "quality_level": quality_level,
            "metrics": _normalize_metrics(metrics),
            "comparison": comparison,
        }

    def write_reports(
        self,
        run_date: str,
        output_dir: Path | str,
        include_json: bool = False,
        metrics: dict[str, Any] | None = None,
        comparison: dict[str, Any] | None = None,
        quality_level: str | None = None,
    ) -> list[Path]:
        """Write report files and return their paths."""
        normalized_metrics = _normalize_metrics(metrics or {})
        if quality_level is None:
            quality_level = self.classify_quality(
                _safe_float(normalized_metrics.get("parse_success_rate"), 0.0),
                _safe_float(normalized_metrics.get("duplicate_rate"), 1.0),
                baseline_metrics=(comparison or {}).get("baseline_metrics") if comparison else None,
                current_metrics=normalized_metrics,
            )

        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = target_dir / f"data_quality_report_{run_date}.md"
        markdown_path.write_text(
            self.generate_markdown_report(
                normalized_metrics,
                comparison,
                quality_level,
                run_date,
            ),
            encoding="utf-8",
        )

        written_paths = [markdown_path]
        if include_json:
            json_path = target_dir / f"data_quality_report_{run_date}.json"
            json_path.write_text(
                json.dumps(
                    self.generate_json_report(
                        normalized_metrics,
                        comparison,
                        quality_level,
                        run_date,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            written_paths.append(json_path)

        return written_paths

    def _classify_with_static_guardrails(
        self,
        parse_success_rate: float,
        duplicate_rate: float,
    ) -> str:
        parse_success = _safe_float(parse_success_rate, 0.0)
        duplicate = _safe_float(duplicate_rate, 1.0)

        if parse_success >= 0.95 and duplicate < 0.1:
            return "excellent"
        if parse_success >= 0.9:
            return "good"
        return "needs_attention"

    def _rates_within_baseline(
        self,
        current_metrics: dict[str, Any],
        baseline_metrics: dict[str, Any],
        allowed_increase: float,
    ) -> bool:
        for metric in LOWER_IS_BETTER_RATE_METRICS:
            if metric not in current_metrics or metric not in baseline_metrics:
                continue
            current_value = _safe_float(current_metrics.get(metric), None)
            baseline_value = _safe_float(baseline_metrics.get(metric), None)
            if current_value is None or baseline_value is None:
                continue
            if current_value > baseline_value + allowed_increase:
                return False
        return True


def _safe_float(value: Any, default: float | None) -> float | None:
    if value is None or value == "":
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed):
        return default
    return parsed


def _normalize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metrics)
    if "total_records" not in normalized and "total_silver_records" in normalized:
        normalized["total_records"] = normalized["total_silver_records"]
    return {key: normalized.get(key) for key in QUALITY_METRIC_KEYS}


def _normalize_previous_metrics(
    previous_metrics: list[dict[str, Any]] | dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if previous_metrics is None:
        return []
    if isinstance(previous_metrics, list):
        return [item for item in previous_metrics if isinstance(item, dict)]
    if isinstance(previous_metrics, dict):
        return [previous_metrics]
    return []


def _compute_average_metrics(history: list[dict[str, Any]]) -> dict[str, float]:
    averages = {}
    for key in QUALITY_METRIC_KEYS:
        values = []
        for row in history:
            normalized_row = _normalize_metrics(row)
            value = _safe_float(normalized_row.get(key), None)
            if value is not None:
                values.append(value)
        if values:
            averages[key] = sum(values) / len(values)
    return averages


def _format_value(value: Any) -> str:
    parsed = _safe_float(value, None)
    if parsed is None:
        return "N/A"
    if parsed.is_integer():
        return str(int(parsed))
    return f"{parsed:.6g}"
