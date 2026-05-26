from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
import yaml

from crawler.crawl_config import expand_targets
from crawler.sources.nhatot.adapter import (
    CATEGORY_MAPPING,
    DISTRICT_MAPPING,
    transaction_param,
)


API_URL = "https://gateway.chotot.com/v1/public/ad-listing"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Chotot/4.5.0"
    ),
    "Accept": "application/json, text/plain, */*",
    "X-Chotot-Platform": "IOS",
    "X-Chotot-Region": "VN",
}


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"Invalid config file: {path}")
    return config


def build_params(target: dict[str, Any], *, page: int, limit: int) -> dict[str, Any]:
    category_slug = target.get("category")
    location_slug = target.get("location_slug")
    cg_id = CATEGORY_MAPPING.get(category_slug)
    area_id = DISTRICT_MAPPING.get(location_slug)
    if not cg_id:
        raise ValueError(f"Unsupported Nhatot category: {category_slug}")
    if not area_id:
        raise ValueError(f"Unsupported Nhatot location_slug: {location_slug}")

    params: dict[str, Any] = {
        "cg": cg_id,
        "region": 12,
        "area": area_id,
        "page": page,
        "limit": limit,
    }
    st = transaction_param(target)
    if st:
        params["st"] = st
    return params


def fetch_target_total(
    target: dict[str, Any],
    *,
    timeout_seconds: float,
    request_limit: int,
) -> dict[str, Any]:
    params = build_params(target, page=1, limit=request_limit)
    response = requests.get(
        API_URL,
        params=params,
        headers=DEFAULT_HEADERS,
        timeout=timeout_seconds,
    )
    row: dict[str, Any] = {
        "category": target.get("category"),
        "category_label": target.get("category_label"),
        "property_type_group": target.get("property_type_group"),
        "location_slug": target.get("location_slug"),
        "location_path": target.get("location_path"),
        "location_label": target.get("location_label"),
        "api_url": f"{API_URL}?{urlencode(params)}",
        "http_status": response.status_code,
        "total": None,
        "returned_ads": 0,
        "estimated_pages_at_20": None,
        "sample_listing_ids": "",
        "sample_subjects": "",
        "error_message": None,
    }

    if response.status_code != 200:
        row["error_message"] = response.text[:300]
        return row

    payload = response.json()
    ads = payload.get("ads") or []
    total = payload.get("total")
    row["total"] = int(total) if total is not None else len(ads)
    row["returned_ads"] = len(ads)
    row["estimated_pages_at_20"] = (
        math.ceil(int(row["total"]) / 20) if row["total"] is not None else None
    )
    row["sample_listing_ids"] = ",".join(
        str(ad.get("list_id") or ad.get("ad_id") or "")
        for ad in ads[:3]
        if isinstance(ad, dict)
    )
    row["sample_subjects"] = " | ".join(
        str(ad.get("subject") or "")[:80] for ad in ads[:3] if isinstance(ad, dict)
    )
    return row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Nhatot API total listing counts for each configured target."
    )
    parser.add_argument("--config", default="configs/sources/nhatot.yaml")
    parser.add_argument("--output-json", default="data/reports/nhatot_api_totals.json")
    parser.add_argument("--output-csv", default="data/reports/nhatot_api_totals.csv")
    parser.add_argument("--timeout-seconds", type=float, default=20)
    parser.add_argument("--request-limit", type=int, default=3)
    args = parser.parse_args()

    config = load_config(Path(args.config))
    rows = []
    for target in expand_targets(config):
        try:
            rows.append(
                fetch_target_total(
                    target,
                    timeout_seconds=args.timeout_seconds,
                    request_limit=args.request_limit,
                )
            )
        except Exception as exc:
            rows.append(
                {
                    "category": target.get("category"),
                    "category_label": target.get("category_label"),
                    "property_type_group": target.get("property_type_group"),
                    "location_slug": target.get("location_slug"),
                    "location_path": target.get("location_path"),
                    "location_label": target.get("location_label"),
                    "api_url": None,
                    "http_status": None,
                    "total": None,
                    "returned_ads": 0,
                    "estimated_pages_at_20": None,
                    "sample_listing_ids": "",
                    "sample_subjects": "",
                    "error_message": str(exc),
                }
            )

    total_records = sum(int(row["total"] or 0) for row in rows)
    summary = {
        "config": args.config,
        "target_count": len(rows),
        "total_records_reported_by_api": total_records,
        "rows": rows,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(Path(args.output_csv), rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"JSON written to: {output_json}")
    print(f"CSV written to: {Path(args.output_csv)}")


if __name__ == "__main__":
    main()
