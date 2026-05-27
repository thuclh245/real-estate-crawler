"""Stage 1 pipeline preflight checks."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

repo_root = Path(__file__).resolve().parents[2]
src_root = repo_root / "src"
if src_root.exists() and str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from common.paths import bronze_dir, gold_dir, logs_dir, silver_dir

EXIT_PASS = 0
EXIT_HARD_FAILURE = 1
EXIT_SOFT_WARNING = 2


def run_preflight(
    *,
    run_id: str,
    config_paths: list[str] | None = None,
    require_spark: bool = False,
    output_dir: Path | str = Path("data/logs/preflight"),
) -> tuple[int, dict[str, Any], Path]:
    checks = [
        _check("python_interpreter", True, sys.executable),
        _check(
            "python_version",
            sys.version_info >= (3, 11),
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
        _check("pythonpath_src", _src_importable(), "src import path available"),
        _check(
            "required_yaml",
            importlib.util.find_spec("yaml") is not None,
            "PyYAML import",
        ),
        _check(
            "required_pandas",
            importlib.util.find_spec("pandas") is not None,
            "pandas import",
        ),
        _check("log_path_writable", _path_writable(logs_dir()), str(logs_dir())),
        _check("bronze_path_writable", _path_writable(bronze_dir()), str(bronze_dir())),
        _check("silver_path_writable", _path_writable(silver_dir()), str(silver_dir())),
        _check("gold_path_writable", _path_writable(gold_dir()), str(gold_dir())),
    ]

    for config_path in config_paths or []:
        checks.append(
            _check(
                "config_source_valid",
                Path(config_path).exists(),
                config_path,
            )
        )

    if require_spark:
        checks.extend(
            [
                _check("java_runtime", shutil.which("java") is not None, "java executable"),
                _check(
                    "pyspark_import",
                    importlib.util.find_spec("pyspark") is not None,
                    "pyspark import",
                ),
            ]
        )

    exit_code = _exit_code(checks)
    payload = {
        "run_id": run_id,
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "exit_code": exit_code,
        "checks": checks,
        "overall": "pass" if exit_code == EXIT_PASS else "failed",
    }
    output_path = Path(output_dir) / f"run_id={run_id}" / "preflight.json"
    _atomic_write_json(output_path, payload)
    return exit_code, payload, output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pipeline preflight checks.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", action="append", default=[])
    parser.add_argument("--require-spark", action="store_true")
    parser.add_argument("--output-dir", default="data/logs/preflight")
    args = parser.parse_args()

    exit_code, payload, output_path = run_preflight(
        run_id=args.run_id,
        config_paths=args.config,
        require_spark=args.require_spark,
        output_dir=args.output_dir,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Preflight written to: {output_path}")
    raise SystemExit(exit_code)


def _src_importable() -> bool:
    repo_root = Path(__file__).resolve().parents[2]
    src_path = repo_root / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    if str(Path("src").resolve()) in sys.path:
        return True
    return importlib.util.find_spec("observability") is not None


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "detail": detail,
    }


def _exit_code(checks: list[dict[str, str]]) -> int:
    return EXIT_HARD_FAILURE if any(check["status"] == "fail" for check in checks) else EXIT_PASS


def _path_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".preflight_{os.getpid()}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    main()
