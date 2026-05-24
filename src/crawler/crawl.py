import argparse
import sys

from crawler.crawl_config import load_config
from crawler.orchestrator import CrawlOrchestrator


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def run_crawl(config_path: str) -> None:
    config = load_config(config_path)
    CrawlOrchestrator(config).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Batdongsan Bronze crawler.")
    parser.add_argument(
        "--config",
        default="configs/crawl_targets.yaml",
        help="Path to crawl target YAML config.",
    )
    args = parser.parse_args()
    run_crawl(args.config)
