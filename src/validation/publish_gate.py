"""Stage 1 publish decision helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublishDecision:
    status: str
    block_reason: str | None = None


def evaluate_publish_gate(
    *,
    pipeline_mode: str,
    run_class: str,
    pipeline_status: str,
    validation_status: str,
    silver_records_written: int,
    warnings: list[str] | None = None,
) -> PublishDecision:
    """Evaluate the small Stage 1 generated -> validated -> publish gate."""
    if run_class != "production" or pipeline_mode != "full":
        return PublishDecision("skipped")
    if pipeline_status != "success":
        return PublishDecision("blocked", f"pipeline_status={pipeline_status}")
    if validation_status not in {"pass", "passed"}:
        return PublishDecision("blocked", f"validation_status={validation_status}")
    if silver_records_written <= 0:
        return PublishDecision("blocked", "full production run has zero silver records")
    if warnings:
        return PublishDecision("validated_with_warnings", "; ".join(warnings))
    return PublishDecision("published")
