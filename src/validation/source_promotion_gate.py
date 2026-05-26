"""Promotion gate for bringing an onboarded source into production scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourcePromotionDecision:
    """Decision for source promotion readiness."""

    status: str
    block_reasons: list[str]

    @property
    def passed(self) -> bool:
        return self.status == "pass"


LEGAL_ACCESS_REQUIRED_TRUE_FIELDS = (
    "terms_reviewed",
    "robots_checked",
    "personal_contact_handling_documented",
    "approved_fetch_mode_documented",
    "no_captcha_bypass_required",
)


def evaluate_source_promotion_gate(
    *,
    source_config: dict[str, Any],
    scorecard: dict[str, Any],
    warehouse_summary: dict[str, Any] | None = None,
) -> SourcePromotionDecision:
    """Evaluate whether a source is ready to be enabled for production ingestion."""
    block_reasons: list[str] = []
    source_code = str(source_config.get("source_code") or "")
    scorecard_source_code = str(scorecard.get("source_code") or "")

    if not source_code:
        block_reasons.append("source_config missing source_code")
    if source_code and scorecard_source_code and source_code != scorecard_source_code:
        block_reasons.append(
            f"scorecard source_code {scorecard_source_code} does not match {source_code}"
        )

    if source_config.get("is_active") is not True:
        block_reasons.append("source config is_active is not true")

    compatibility = source_config.get("compatibility") or {}
    if compatibility.get("production_enabled") is not True:
        block_reasons.append("compatibility.production_enabled is not true")

    promotion = source_config.get("promotion") or {}
    legal_access_review = promotion.get("legal_access_review") or {}
    for field_name in LEGAL_ACCESS_REQUIRED_TRUE_FIELDS:
        if legal_access_review.get(field_name) is not True:
            block_reasons.append(f"legal_access_review.{field_name} is not true")
    if legal_access_review.get("prohibited_login_required") is True:
        block_reasons.append("legal_access_review.prohibited_login_required is true")

    if scorecard.get("gate_status") != "pass":
        block_reasons.append("source scorecard gate_status is not pass")
    if _safe_int(scorecard.get("total_records")) < _safe_int(
        (source_config.get("quality") or {}).get("min_expected_records")
    ):
        block_reasons.append("source scorecard total_records is below configured minimum")

    if warehouse_summary is not None:
        source_codes = warehouse_summary.get("source_codes") or []
        if source_code and source_code not in source_codes:
            block_reasons.append("warehouse summary does not include source_code")
        table_counts = warehouse_summary.get("table_row_counts") or {}
        if _safe_int(table_counts.get("fact_listing_snapshot")) <= 0:
            block_reasons.append("warehouse fact_listing_snapshot has no rows")
        if _safe_int(table_counts.get("fact_data_quality_daily")) <= 0:
            block_reasons.append("warehouse fact_data_quality_daily has no rows")

    return SourcePromotionDecision(
        status="pass" if not block_reasons else "blocked",
        block_reasons=block_reasons,
    )


def _safe_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
