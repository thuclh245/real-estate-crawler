import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRONZE_ROOT = REPO_ROOT / "data" / "bronze" / "source=batdongsan"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def find_summary(crawl_date: str | None, crawl_id: str | None) -> Path:
    date_dirs = (
        [BRONZE_ROOT / f"crawl_date={crawl_date}"]
        if crawl_date
        else sorted(BRONZE_ROOT.glob("crawl_date=*"))
    )
    candidates = []
    for date_dir in date_dirs:
        if crawl_id:
            paths = [
                date_dir
                / f"crawl_id={crawl_id}"
                / "crawl_log"
                / f"crawl_summary_{crawl_id}.json",
                date_dir / "crawl_log" / f"crawl_summary_{crawl_id}.json",
            ]
            for path in paths:
                if path.exists():
                    return path
            continue
        candidates.extend(date_dir.glob("crawl_id=*/crawl_log/crawl_summary_*.json"))
        candidates.extend((date_dir / "crawl_log").glob("crawl_summary_*.json"))

    if not candidates:
        target = f"crawl_id={crawl_id}" if crawl_id else "latest crawl summary"
        raise FileNotFoundError(f"Could not find {target} under {BRONZE_ROOT}")

    return max(candidates, key=lambda path: path.stat().st_mtime)


def file_stats(paths: list[Path]) -> dict:
    sizes = [path.stat().st_size for path in paths if path.exists()]
    if not sizes:
        return {"count": 0, "avg_size": 0, "min_size": 0, "max_size": 0}
    return {
        "count": len(sizes),
        "avg_size": sum(sizes) / len(sizes),
        "min_size": min(sizes),
        "max_size": max(sizes),
    }


def collect_run_paths(records: list[dict], field: str) -> list[Path]:
    paths = []
    seen = set()
    for record in records:
        value = record.get(field)
        if not value or value in seen:
            continue
        seen.add(value)
        paths.append(Path(value))
    return paths


def audit(summary_path: Path) -> dict:
    summary = load_json(summary_path)
    crawl_id = summary["crawl_id"]
    crawl_date = summary["crawl_date"]
    crawl_log_path = summary_path.parent / f"crawl_log_{crawl_id}.jsonl"
    records = load_jsonl(crawl_log_path)

    raw_html_paths = collect_run_paths(records, "raw_html_path")
    raw_text_paths = collect_run_paths(records, "raw_text_path")
    raw_json_paths = collect_run_paths(records, "raw_json_path")
    metadata_paths = collect_run_paths(records, "metadata_path")

    sample_listing_urls = [
        record["listing_url"]
        for record in records
        if record.get("type") == "detail_page" and record.get("listing_url")
    ][:5]

    return {
        "summary_path": str(summary_path),
        "crawl_log_path": str(crawl_log_path),
        "crawl_id": crawl_id,
        "crawl_date": crawl_date,
        "success_count": summary.get("success_count", 0),
        "failed_count": summary.get("failed_count", 0),
        "blocked_count": summary.get("blocked_count", 0),
        "duplicate_url_count": summary.get("duplicate_url_count", 0),
        "crawl_success_rate": summary.get("crawl_success_rate", 0),
        "summary_raw_html_file_count": summary.get("raw_html_file_count", 0),
        "summary_metadata_file_count": summary.get("metadata_file_count", 0),
        "raw_html": file_stats(raw_html_paths),
        "raw_text": file_stats(raw_text_paths),
        "raw_json": file_stats(raw_json_paths),
        "metadata": file_stats(metadata_paths),
        "sample_listing_urls": sample_listing_urls,
    }


def print_report(report: dict) -> None:
    print("Bronze audit")
    print("=" * 60)
    for key in [
        "crawl_id",
        "crawl_date",
        "success_count",
        "failed_count",
        "blocked_count",
        "duplicate_url_count",
        "crawl_success_rate",
    ]:
        print(f"{key}: {report[key]}")

    print()
    print("Files from crawl log")
    print("-" * 60)
    print(f"raw_html_file_count: {report['raw_html']['count']}")
    print(f"raw_text_file_count: {report['raw_text']['count']}")
    print(f"raw_json_file_count: {report['raw_json']['count']}")
    print(f"metadata_file_count: {report['metadata']['count']}")
    print(f"avg_html_size: {report['raw_html']['avg_size']:.2f}")
    print(f"min_html_size: {report['raw_html']['min_size']}")
    print(f"max_html_size: {report['raw_html']['max_size']}")

    print()
    print("Summary counts")
    print("-" * 60)
    print(f"summary_raw_html_file_count: {report['summary_raw_html_file_count']}")
    print(f"summary_metadata_file_count: {report['summary_metadata_file_count']}")

    print()
    print("Sample listing URLs")
    print("-" * 60)
    for url in report["sample_listing_urls"]:
        print(url)

    print()
    print("Sources")
    print("-" * 60)
    print(f"summary_path: {report['summary_path']}")
    print(f"crawl_log_path: {report['crawl_log_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Bronze output for a Batdongsan crawl run."
    )
    parser.add_argument(
        "--crawl-date", help="Crawl date in YYYY-MM-DD format. Defaults to latest date."
    )
    parser.add_argument(
        "--crawl-id", help="Specific crawl_id to audit. Defaults to latest summary."
    )
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON."
    )
    args = parser.parse_args()

    summary_path = find_summary(args.crawl_date, args.crawl_id)
    report = audit(summary_path)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
