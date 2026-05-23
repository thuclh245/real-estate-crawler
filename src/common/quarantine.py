"""JSONL quarantine helpers for Stage 1 production hardening."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from common.storage import append_jsonl


REQUIRED_QUARANTINE_FIELDS = (
    "quarantine_id",
    "run_id",
    "source_code",
    "input_path",
    "record_identity",
    "rejection_stage",
    "rejection_reason",
    "error_message",
    "parser_version",
    "captured_at",
    "raw_reference_path",
)


def build_quarantine_record(
    *,
    run_id: str,
    source_code: str,
    rejection_stage: str,
    rejection_reason: str,
    input_path: str | None = None,
    record_identity: str | None = None,
    error_message: str | None = None,
    parser_version: str | None = None,
    raw_reference_path: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "quarantine_id": uuid4().hex,
        "run_id": run_id,
        "source_code": source_code,
        "input_path": input_path,
        "record_identity": record_identity,
        "rejection_stage": rejection_stage,
        "rejection_reason": rejection_reason,
        "error_message": error_message,
        "parser_version": parser_version,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw_reference_path": raw_reference_path,
    }
    if extra:
        record["extra"] = extra
    return record


def quarantine_path(
    *,
    rejection_stage: str,
    source_code: str,
    run_date: str,
    run_id: str,
    base_dir: Path | str = Path("data/quarantine"),
) -> Path:
    return (
        Path(base_dir)
        / rejection_stage
        / f"source={source_code}"
        / f"date={run_date}"
        / f"quarantine_{run_id}.jsonl"
    )


def append_quarantine_record(
    record: dict[str, Any],
    *,
    run_date: str,
    base_dir: Path | str = Path("data/quarantine"),
) -> Path:
    missing = [field for field in REQUIRED_QUARANTINE_FIELDS if field not in record]
    if missing:
        raise ValueError(f"quarantine record missing fields: {missing}")
    path = quarantine_path(
        rejection_stage=str(record["rejection_stage"]),
        source_code=str(record["source_code"]),
        run_date=run_date,
        run_id=str(record["run_id"]),
        base_dir=base_dir,
    )
    append_jsonl(path, record)
    return path
