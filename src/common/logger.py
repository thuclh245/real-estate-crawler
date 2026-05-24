from __future__ import annotations

import json
import logging
from logging import Logger
from pathlib import Path
from typing import Any

from .paths import logs_dir


def get_logger(name: str, level: int = logging.INFO) -> Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def jsonl_log_path(run_id: str, base_dir: Path | str | None = None) -> Path:
    root = Path(base_dir) if base_dir is not None else logs_dir()
    return root / "pipeline_runs" / f"run_id={run_id}" / "events.jsonl"


def append_jsonl_log(path: Path | str, event: dict[str, Any]) -> Path:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return log_path


import json
from pathlib import Path


def append_jsonl(path: str | Path, record: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
