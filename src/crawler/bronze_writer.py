import json
import os
from pathlib import Path
from typing import Any

from common.paths import bronze_partition_path
from common.storage import append_jsonl


def build_bronze_root(
    *,
    source: str,
    crawl_date: str,
    crawl_id: str,
    base_dir: Path | str = Path("data"),
) -> Path:
    return bronze_partition_path(
        source=source,
        crawl_date=crawl_date,
        crawl_id=crawl_id,
        base_dir=base_dir,
    )


def build_listing_paths(
    *,
    listing_id: str,
    source: str,
    crawl_date: str,
    crawl_id: str,
    base_dir: Path | str = Path("data"),
) -> dict[str, Path]:
    bronze_root = build_bronze_root(
        source=source,
        crawl_date=crawl_date,
        crawl_id=crawl_id,
        base_dir=base_dir,
    )
    return {
        "bronze_root": bronze_root,
        "raw_html": bronze_root / "raw_html" / f"listing_id={listing_id}.html",
        "raw_text": bronze_root / "raw_text" / f"listing_id={listing_id}.txt",
        "raw_json": bronze_root / "raw_json" / f"listing_id={listing_id}.json",
        "metadata": bronze_root / "metadata" / f"listing_id={listing_id}.json",
        "crawl_log": bronze_root / "crawl_log" / f"crawl_log_{crawl_id}.jsonl",
    }


def write_raw_html(
    *,
    html: str,
    listing_id: str,
    source: str,
    crawl_date: str,
    crawl_id: str,
    base_dir: Path | str = Path("data"),
) -> Path:
    path = build_listing_paths(
        listing_id=listing_id,
        source=source,
        crawl_date=crawl_date,
        crawl_id=crawl_id,
        base_dir=base_dir,
    )["raw_html"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html or "", encoding="utf-8")
    return path


def write_metadata_json(
    *,
    metadata: dict[str, Any],
    listing_id: str,
    source: str,
    crawl_date: str,
    crawl_id: str,
    base_dir: Path | str = Path("data"),
) -> Path:
    path = build_listing_paths(
        listing_id=listing_id,
        source=source,
        crawl_date=crawl_date,
        crawl_id=crawl_id,
        base_dir=base_dir,
    )["metadata"]
    _atomic_write_json(path, metadata)
    return path


def append_crawl_log(
    *,
    record: dict[str, Any],
    source: str,
    crawl_date: str,
    crawl_id: str,
    base_dir: Path | str = Path("data"),
) -> Path:
    path = build_listing_paths(
        listing_id="log",
        source=source,
        crawl_date=crawl_date,
        crawl_id=crawl_id,
        base_dir=base_dir,
    )["crawl_log"]
    append_jsonl(path, record)
    return path


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
