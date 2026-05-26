"""Source-level onboarding quality gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceQualityGateDecision:
    """Result of evaluating one source scorecard against onboarding thresholds."""

    status: str
    failures: list[str]

    @property
    def passed(self) -> bool:
        return self.status == "pass"


DEFAULT_SOURCE_QUALITY_THRESHOLDS = {
    "min_expected_records": 1,
    "min_parse_success_rate": 0.9,
    "blocking_blocked_rate": 0.5,
    "max_missing_price_rate": 0.5,
    "max_missing_area_rate": 0.5,
    "max_missing_location_rate": 0.5,
    "max_duplicate_rate": 0.5,
    "max_quarantine_rate": 0.5,
}


def evaluate_source_quality_gate(
    metrics: dict[str, Any],
    quality_config: dict[str, Any] | None = None,
) -> SourceQualityGateDecision:
    """Evaluate source onboarding metrics without affecting publish eligibility."""
    thresholds = {
        **DEFAULT_SOURCE_QUALITY_THRESHOLDS,
        **(quality_config or {}),
    }
    failures: list[str] = []

    total_records = _safe_int(metrics.get("total_records"))
    min_expected_records = _safe_int(thresholds.get("min_expected_records"))
    if total_records < min_expected_records:
        failures.append(
            f"total_records {total_records} below minimum {min_expected_records}"
        )

    _check_min_rate(
        failures,
        metrics,
        thresholds,
        metric_key="parse_success_rate",
        threshold_key="min_parse_success_rate",
    )
    _check_max_rate(
        failures,
        metrics,
        thresholds,
        metric_key="blocked_rate",
        threshold_key="blocking_blocked_rate",
    )
    _check_max_rate(
        failures,
        metrics,
        thresholds,
        metric_key="missing_price_rate",
        threshold_key="max_missing_price_rate",
    )
    _check_max_rate(
        failures,
        metrics,
        thresholds,
        metric_key="missing_area_rate",
        threshold_key="max_missing_area_rate",
    )
    _check_max_rate(
        failures,
        metrics,
        thresholds,
        metric_key="missing_location_rate",
        threshold_key="max_missing_location_rate",
    )
    _check_max_rate(
        failures,
        metrics,
        thresholds,
        metric_key="duplicate_rate",
        threshold_key="max_duplicate_rate",
    )
    _check_max_rate(
        failures,
        metrics,
        thresholds,
        metric_key="quarantine_rate",
        threshold_key="max_quarantine_rate",
    )

    return SourceQualityGateDecision(
        status="pass" if not failures else "fail",
        failures=failures,
    )


def _check_min_rate(
    failures: list[str],
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    *,
    metric_key: str,
    threshold_key: str,
) -> None:
    value = _safe_float(metrics.get(metric_key))
    threshold = _safe_float(thresholds.get(threshold_key))
    if value < threshold:
        failures.append(f"{metric_key} {value:.6g} below minimum {threshold:.6g}")


def _check_max_rate(
    failures: list[str],
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    *,
    metric_key: str,
    threshold_key: str,
) -> None:
    value = _safe_float(metrics.get(metric_key))
    threshold = _safe_float(thresholds.get(threshold_key))
    if value > threshold:
        failures.append(f"{metric_key} {value:.6g} above maximum {threshold:.6g}")


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
