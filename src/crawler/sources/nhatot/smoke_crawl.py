from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import yaml

from crawler.orchestrator import CrawlDependencies, CrawlOrchestrator
from crawler.sources.nhatot import NhatotAdapter


DEFAULT_CONFIG_PATH = Path("configs/sources/nhatot.yaml")


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def _base_url_from_source_config(source_config: dict) -> str:
    if source_config.get("base_url"):
        return str(source_config["base_url"])

    domain = str(source_config.get("source_domain") or "").strip()
    if not domain:
        raise ValueError("Nhatot source config must define source_domain or base_url")
    if domain == "nhatot.com":
        return "https://www.nhatot.com"
    return f"https://{domain}"


def load_source_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"Invalid source config: {path}")
    return config


def build_smoke_crawl_config(source_config: dict) -> dict:
    source_code = source_config.get("source_code")
    if source_code != "nhatot":
        raise ValueError(f"Expected source_code=nhatot, got {source_code!r}")

    crawl = source_config.get("crawl") or {}
    api = source_config.get("api") or {}
    targets = source_config.get("targets") or []
    if not targets:
        raise ValueError("Nhatot source config must define at least one smoke target")

    return {
        "source": "nhatot",
        "source_domain": source_config.get("source_domain"),
        "base_url": _base_url_from_source_config(source_config),
        "crawl_settings": {
            "fetch_mode": source_config.get("fetch_mode", "crawl4ai"),
            "max_pages_per_target": int(crawl.get("max_pages_per_target", 1)),
            "max_listings_per_target": int(crawl.get("max_listings_per_target", 5)),
            "request_delay_seconds": float(crawl.get("request_delay_seconds", 1.5)),
            "concurrency": int(crawl.get("concurrency", 1)),
            "stop_on_block": True,
            "stop_on_fetch_error": True,
            "max_retries": int(crawl.get("max_retries", 1)),
            "retry_delay_seconds": float(crawl.get("retry_delay_seconds", 10)),
            "crawler_version": "nhatot_smoke_v0.1",
            "parser_version": "nhatot_adapter_v0.1",
            "daily_listing_cap": int(api.get("daily_listing_cap", 0) or 0),
        },
        "targets": targets,
    }


def run_nhatot_smoke_crawl(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    base_dir: str | Path = Path("data"),
    fetch_with_retry_fn: Callable | None = None,
) -> dict:
    source_config = load_source_config(config_path)
    crawl_config = build_smoke_crawl_config(source_config)
    dependencies = CrawlDependencies(source_adapter=NhatotAdapter())
    if fetch_with_retry_fn is not None:
        dependencies.fetch_with_retry_fn = fetch_with_retry_fn

    return CrawlOrchestrator(
        crawl_config,
        base_dir=base_dir,
        dependencies=dependencies,
    ).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a controlled Nhatot Bronze smoke crawl.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--base-dir", default="data")
    args = parser.parse_args()

    summary = run_nhatot_smoke_crawl(
        config_path=args.config,
        base_dir=args.base_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
