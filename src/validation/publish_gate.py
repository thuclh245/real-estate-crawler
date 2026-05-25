"""Stage 1 publish decision helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_THRESHOLD_CONFIG_PATH = REPO_ROOT / "configs" / "validation_thresholds.yaml"


@dataclass(frozen=True)
class PublishDecision:
    status: str
    block_reason: str | None = None


@dataclass(frozen=True)
class PublishThresholds:
    min_silver_records: int = 1


def evaluate_publish_gate(
    *,
    pipeline_mode: str,
    run_class: str,
    pipeline_status: str,
    validation_status: str,
    silver_records_written: int,
    warnings: list[str] | None = None,
    thresholds: PublishThresholds | None = None,
) -> PublishDecision:
    """Evaluate the small Stage 1 generated -> validated -> publish gate."""
    active_thresholds = thresholds or load_publish_thresholds(
        pipeline_mode=pipeline_mode,
        run_class=run_class,
    )

    if run_class != "production" or pipeline_mode != "full":
        return PublishDecision("skipped")
    if pipeline_status != "success":
        return PublishDecision("blocked", f"pipeline_status={pipeline_status}")
    if validation_status not in {"pass", "passed"}:
        return PublishDecision("blocked", f"validation_status={validation_status}")
    if silver_records_written <= 0:
        return PublishDecision("blocked", "full production run has zero silver records")
    if silver_records_written < active_thresholds.min_silver_records:
        return PublishDecision(
            "blocked",
            (
                "silver_records_written="
                f"{silver_records_written} below minimum "
                f"{active_thresholds.min_silver_records} for "
                f"run_class={run_class}, pipeline_mode={pipeline_mode}"
            ),
        )
    if warnings:
        return PublishDecision("validated_with_warnings", "; ".join(warnings))
    return PublishDecision("published")


def load_publish_thresholds(
    *,
    pipeline_mode: str,
    run_class: str,
    config_path: Path | str = DEFAULT_THRESHOLD_CONFIG_PATH,
) -> PublishThresholds:
    """Load Stage 1 publish thresholds, falling back to zero-record protection."""
    path = Path(config_path)
    if not path.exists():
        return PublishThresholds()

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    publish_gate = payload.get("publish_gate", {})
    selected = _select_threshold_config(
        publish_gate,
        pipeline_mode=pipeline_mode,
        run_class=run_class,
    )
    return PublishThresholds(
        min_silver_records=_to_int(
            selected.get("min_silver_records"),
            default=PublishThresholds().min_silver_records,
        )
    )


def _select_threshold_config(
    publish_gate: dict[str, Any],
    *,
    pipeline_mode: str,
    run_class: str,
) -> dict[str, Any]:
    defaults = publish_gate.get("defaults", {})
    modes = publish_gate.get("modes", {})
    mode_config = modes.get(pipeline_mode, {})
    class_config = mode_config.get(run_class, {})
    return {**defaults, **mode_config, **class_config}


def _to_int(value: Any, *, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
