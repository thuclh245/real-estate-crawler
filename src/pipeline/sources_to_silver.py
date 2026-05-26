"""Run one or more crawl configs through Bronze and Silver outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from crawler.crawl_config import load_config
from crawler.orchestrator import CrawlDependencies, CrawlOrchestrator
from crawler.sources.nhatot.smoke_crawl import run_nhatot_smoke_crawl
from observability import (
    build_source_scorecard,
    load_silver_quality_summary,
    write_source_scorecard,
)
from transform.bronze_to_silver import run_bronze_to_silver


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def run_sources_to_silver(
    *,
    config_paths: list[str | Path],
    base_dir: str | Path = Path("data"),
    fetch_with_retry_fn: Callable | None = None,
    scorecard_output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run configured sources through crawl, Bronze, Silver, and scorecard checks."""
    base_path = Path(base_dir)
    scorecard_root = (
        Path(scorecard_output_dir)
        if scorecard_output_dir is not None
        else base_path / "logs"
    )
    runs: list[dict[str, Any]] = []

    for config_path in config_paths:
        config_file = Path(config_path)
        config = load_config(config_file)
        source_code = _source_code(config)
        crawl_summary = _run_source_crawl(
            config=config,
            config_path=config_file,
            base_dir=base_path,
            fetch_with_retry_fn=fetch_with_retry_fn,
        )
        source = str(crawl_summary["source"])
        crawl_date = str(crawl_summary["crawl_date"])
        crawl_id = str(crawl_summary["crawl_id"])
        bronze_dir = (
            base_path
            / "bronze"
            / f"source={source}"
            / f"crawl_date={crawl_date}"
            / f"crawl_id={crawl_id}"
        )
        silver_dir = (
            base_path
            / "silver"
            / f"source={source}"
            / f"crawl_date={crawl_date}"
            / f"crawl_id={crawl_id}"
        )

        parser_version = str(
            (config.get("crawl_settings") or {}).get("parser_version")
            or crawl_summary.get("parser_version")
            or ("nhatot_adapter_v0.1" if source_code == "nhatot" else "phase2_v1")
        )
        metadata_dir = bronze_dir / "metadata"
        if not metadata_dir.exists() and _continue_without_silver(config):
            scorecard = build_source_scorecard(
                crawl_summary=crawl_summary,
                silver_quality_summary={
                    "total_metadata_files": 0,
                    "total_records_parsed": 0,
                    "total_quarantined_records": 0,
                    "parse_success_rate": 0.0,
                },
                quality_config=config.get("quality") or {},
                artifact_paths=[str(bronze_dir / "crawl_log")],
            )
            scorecard_path = write_source_scorecard(scorecard, scorecard_root)
            runs.append(
                {
                    "config_path": str(config_file),
                    "source": source,
                    "crawl_date": crawl_date,
                    "crawl_id": crawl_id,
                    "bronze_dir": str(bronze_dir),
                    "silver_dir": str(silver_dir),
                    "parser_version": parser_version,
                    "status": "skipped_no_metadata",
                    "skip_reason": "metadata folder not found after crawl",
                    "silver_validation": {
                        "listings_path": None,
                        "row_count": 0,
                        "lineage_columns": [],
                    },
                    "source_scorecard_path": str(scorecard_path),
                    "source_scorecard": scorecard,
                }
            )
            continue

        run_bronze_to_silver(
            bronze_dir=str(bronze_dir),
            silver_dir=str(silver_dir),
            parser_version=parser_version,
        )

        validation = validate_silver_output(
            silver_dir=silver_dir,
            source_code=source,
            min_expected_records=int((config.get("quality") or {}).get("min_expected_records", 0)),
        )
        quality_summary_path = silver_dir / "data_quality_summary.json"
        scorecard = build_source_scorecard(
            crawl_summary=crawl_summary,
            silver_quality_summary=load_silver_quality_summary(quality_summary_path),
            quality_config=config.get("quality") or {},
            artifact_paths=[
                str(silver_dir / "listings.parquet"),
                str(quality_summary_path),
            ],
        )
        scorecard_path = write_source_scorecard(scorecard, scorecard_root)

        runs.append(
            {
                "config_path": str(config_file),
                "source": source,
                "crawl_date": crawl_date,
                "crawl_id": crawl_id,
                "bronze_dir": str(bronze_dir),
                "silver_dir": str(silver_dir),
                "parser_version": parser_version,
                "status": "success",
                "silver_validation": validation,
                "source_scorecard_path": str(scorecard_path),
                "source_scorecard": scorecard,
            }
        )

    return {
        "pipeline": "sources_to_silver",
        "base_dir": str(base_path),
        "source_names": sorted({run["source"] for run in runs}),
        "crawl_ids_created": [run["crawl_id"] for run in runs],
        "runs": runs,
    }


def validate_silver_output(
    *,
    silver_dir: Path,
    source_code: str,
    min_expected_records: int = 0,
) -> dict[str, Any]:
    """Validate required Silver artifact and lineage for one source run."""
    listings_path = silver_dir / "listings.parquet"
    if not listings_path.exists():
        raise FileNotFoundError(f"Missing Silver listings parquet: {listings_path}")

    df = pd.read_parquet(listings_path)
    row_count = int(df.shape[0])
    if row_count < min_expected_records:
        raise ValueError(
            f"Silver row count {row_count} below minimum {min_expected_records} for {source_code}"
        )

    lineage_columns = [column for column in ("source", "source_code") if column in df.columns]
    if not lineage_columns:
        raise ValueError(f"Silver output missing source lineage columns: {listings_path}")
    for column in lineage_columns:
        values = {str(value) for value in df[column].dropna().unique().tolist()}
        if values and values != {source_code}:
            raise ValueError(
                f"Silver {column} values {sorted(values)} do not match {source_code}"
            )

    return {
        "listings_path": str(listings_path),
        "row_count": row_count,
        "lineage_columns": lineage_columns,
    }


def _run_source_crawl(
    *,
    config: dict[str, Any],
    config_path: Path,
    base_dir: Path,
    fetch_with_retry_fn: Callable | None,
) -> dict[str, Any]:
    source_code = _source_code(config)
    if source_code == "nhatot":
        return run_nhatot_smoke_crawl(
            config_path=config_path,
            base_dir=base_dir,
            fetch_with_retry_fn=fetch_with_retry_fn,
        )

    dependencies = None
    if fetch_with_retry_fn is not None:
        dependencies = CrawlDependencies(fetch_with_retry_fn=fetch_with_retry_fn)
    return CrawlOrchestrator(
        config,
        base_dir=base_dir,
        dependencies=dependencies,
    ).run()


def _source_code(config: dict[str, Any]) -> str:
    return str(config.get("source_code") or config.get("source") or "unknown")


def _continue_without_silver(config: dict[str, Any]) -> bool:
    compatibility = config.get("compatibility") or {}
    return str(compatibility.get("failure_policy") or "") == "continue_without_silver"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run configured sources to Silver.")
    parser.add_argument(
        "--config",
        action="append",
        required=True,
        help="Source or legacy crawl config path. Repeat for multiple sources.",
    )
    parser.add_argument("--base-dir", default="data")
    parser.add_argument("--scorecard-output-dir", default=None)
    parser.add_argument("--summary-output", default=None)
    args = parser.parse_args()

    summary = run_sources_to_silver(
        config_paths=args.config,
        base_dir=args.base_dir,
        scorecard_output_dir=args.scorecard_output_dir,
    )
    if args.summary_output:
        summary_path = Path(args.summary_output)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
