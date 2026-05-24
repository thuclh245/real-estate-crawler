from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir(base_dir: Path | str | None = None) -> Path:
    return Path(base_dir) if base_dir is not None else repo_root() / "data"


def bronze_dir(base_dir: Path | str | None = None) -> Path:
    return data_dir(base_dir) / "bronze"


def silver_dir(base_dir: Path | str | None = None) -> Path:
    return data_dir(base_dir) / "silver"


def gold_dir(base_dir: Path | str | None = None) -> Path:
    return data_dir(base_dir) / "gold"


def logs_dir(base_dir: Path | str | None = None) -> Path:
    return data_dir(base_dir) / "logs"


def quarantine_dir(base_dir: Path | str | None = None) -> Path:
    return data_dir(base_dir) / "quarantine"


def bronze_source_dir(
    source: str = "batdongsan", base_dir: Path | str | None = None
) -> Path:
    return bronze_dir(base_dir) / f"source={source}"


def default_pipeline_logs_dir() -> Path:
    return logs_dir() / "pipeline_runs"


def default_daily_logs_dir() -> Path:
    return logs_dir() / "daily_pipeline"


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
