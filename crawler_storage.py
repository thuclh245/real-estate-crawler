import csv
import json
from pathlib import Path

from crawler_settings import OUTPUT_COLUMNS


def load_existing_links(output_file: Path) -> set[str]:
    """Load existing listing URLs from CSV for resume mode."""
    existing = set()
    if not output_file.exists():
        return existing

    with output_file.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("listing_url")
            if url:
                existing.add(url)
    return existing


def append_rows(rows: list[dict], output_file: Path) -> None:
    """Append parsed listing rows to CSV, creating header when file is empty."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output_file.exists() or output_file.stat().st_size == 0

    with output_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def load_config(config_path: Path) -> dict:
    """Read JSON config file and return an object config or empty dict."""
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}
