"""Multi-source onboarding acceptance evidence pack."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SOURCE_ACCEPTANCE_SCHEMA_VERSION = "source_acceptance_v1"


def build_source_acceptance_pack(
    *,
    source_code: str,
    source_config: dict[str, Any],
    scorecard: dict[str, Any],
    promotion_decision: Any,
    warehouse_summary: dict[str, Any] | None = None,
    artifact_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Build a compact acceptance evidence payload for one onboarded source."""
    warehouse_summary = warehouse_summary or {}
    table_counts = warehouse_summary.get("table_row_counts") or {}
    warehouse_source_codes = warehouse_summary.get("source_codes") or []
    promotion_status = str(getattr(promotion_decision, "status", "unknown"))
    promotion_block_reasons = list(
        getattr(promotion_decision, "block_reasons", [])
        or getattr(promotion_decision, "failures", [])
        or []
    )

    checklist = {
        "source_config_exists": source_config.get("source_code") == source_code,
        "source_lineage_preserved": scorecard.get("source_code") == source_code,
        "source_scorecard_passed": scorecard.get("gate_status") == "pass",
        "silver_records_present": _safe_int(scorecard.get("total_records")) > 0,
        "warehouse_source_present": source_code in warehouse_source_codes,
        "warehouse_snapshot_fact_present": _safe_int(table_counts.get("fact_listing_snapshot")) > 0,
        "warehouse_quality_fact_present": _safe_int(table_counts.get("fact_data_quality_daily"))
        > 0,
        "production_scope_is_silver_only": (source_config.get("compatibility") or {}).get(
            "production_scope"
        )
        == "silver_only",
    }
    technical_keys = [
        "source_config_exists",
        "source_lineage_preserved",
        "source_scorecard_passed",
        "silver_records_present",
        "warehouse_source_present",
        "warehouse_snapshot_fact_present",
        "warehouse_quality_fact_present",
    ]
    technical_ready = all(checklist[key] for key in technical_keys)

    return {
        "acceptance_schema_version": SOURCE_ACCEPTANCE_SCHEMA_VERSION,
        "acceptance_scope": "multi_source_onboarding",
        "source_code": source_code,
        "technical_readiness_status": "pass" if technical_ready else "fail",
        "promotion_status": promotion_status,
        "source_acceptance_status": (
            "pass" if technical_ready and promotion_status == "pass" else "blocked"
        ),
        "checklist": checklist,
        "promotion_block_reasons": promotion_block_reasons,
        "scorecard_summary": {
            "crawl_date": scorecard.get("crawl_date"),
            "crawl_id": scorecard.get("crawl_id"),
            "total_records": scorecard.get("total_records"),
            "parse_success_rate": scorecard.get("parse_success_rate"),
            "blocked_rate": scorecard.get("blocked_rate"),
            "gate_status": scorecard.get("gate_status"),
        },
        "warehouse_summary": {
            "source_codes": warehouse_source_codes,
            "table_row_counts": table_counts,
        },
        "artifact_paths": list(artifact_paths or []),
    }


def write_source_acceptance_pack(
    acceptance_pack: dict[str, Any],
    output_dir: Path | str,
) -> Path:
    """Write source acceptance evidence JSON atomically."""
    source_code = str(acceptance_pack.get("source_code") or "unknown")
    output_path = (
        Path(output_dir) / "source_acceptance" / f"source={source_code}" / "source_acceptance.json"
    )
    _atomic_write_json(output_path, acceptance_pack)
    return output_path


def _safe_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
