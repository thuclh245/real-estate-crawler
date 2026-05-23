from pathlib import Path


def data_root(base_dir: Path | str = Path("data")) -> Path:
    return Path(base_dir)


def bronze_base(base_dir: Path | str = Path("data")) -> Path:
    return data_root(base_dir) / "bronze"


def silver_base(base_dir: Path | str = Path("data")) -> Path:
    return data_root(base_dir) / "silver"


def gold_base(base_dir: Path | str = Path("data")) -> Path:
    return data_root(base_dir) / "gold"


def logs_base(base_dir: Path | str = Path("data")) -> Path:
    return data_root(base_dir) / "logs"


def quarantine_base(base_dir: Path | str = Path("data")) -> Path:
    return data_root(base_dir) / "quarantine"


def bronze_partition_path(
    *,
    source: str,
    crawl_date: str,
    crawl_id: str,
    base_dir: Path | str = Path("data"),
) -> Path:
    return (
        bronze_base(base_dir)
        / f"source={source}"
        / f"crawl_date={crawl_date}"
        / f"crawl_id={crawl_id}"
    )
