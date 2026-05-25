import json
from pathlib import Path

import pandas as pd
import streamlit as st

GOLD_DIR = Path("data/gold")
PIPELINE_LOG_DIR = Path("data/logs/daily_pipeline")
PIPELINE_RUN_DIR = Path("data/logs/pipeline_runs")
QUARANTINE_DIR = Path("data/quarantine")


def find_table_path(table_name: str) -> Path:
    candidates = [
        GOLD_DIR / table_name,
        GOLD_DIR / f"{table_name}_csv_sample",
        GOLD_DIR / f"{table_name}_csv",
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(f"Cannot find Gold table: {table_name}")


def add_hive_partitions(
    df: pd.DataFrame, file_path: Path, table_path: Path
) -> pd.DataFrame:
    relative_parts = file_path.relative_to(table_path).parts[:-1]
    for part in relative_parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key not in df.columns:
            df[key] = None if value == "__HIVE_DEFAULT_PARTITION__" else value
    return df


@st.cache_data(show_spinner=False)
def read_gold_table(table_name: str) -> pd.DataFrame:
    path = find_table_path(table_name)

    if path.is_file():
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        if path.suffix == ".csv":
            return pd.read_csv(path)

    if path.is_dir():
        parquet_files = sorted(path.rglob("*.parquet"))
        csv_files = sorted(path.rglob("*.csv"))

        if parquet_files:
            frames = []
            for file_path in parquet_files:
                df = pd.read_parquet(file_path)
                frames.append(add_hive_partitions(df, file_path, path))
            return pd.concat(frames, ignore_index=True, sort=False)

        if csv_files:
            return pd.concat(
                [pd.read_csv(file_path) for file_path in csv_files], ignore_index=True
            )

    raise FileNotFoundError(f"Cannot read Gold table: {path}")


@st.cache_data(show_spinner=False)
def read_phase3_summary() -> dict:
    summary_path = GOLD_DIR / "phase3_summary.json"
    if not summary_path.exists():
        return {}
    return json.loads(summary_path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_run_summaries(log_dir: Path | str = PIPELINE_LOG_DIR) -> pd.DataFrame:
    """Load daily_run_summary.json files into a DataFrame."""
    base_dir = Path(log_dir)
    if not base_dir.exists():
        return pd.DataFrame()

    rows = []
    for summary_path in sorted(base_dir.glob("run_date=*/daily_run_summary.json")):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"[WARN] Skipping invalid run summary {summary_path}: {error}")
            continue

        payload["_summary_path"] = str(summary_path)
        rows.append(payload)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_production_run_summaries(run_dir: Path | str = PIPELINE_RUN_DIR) -> pd.DataFrame:
    """Load valid v2 production-oriented run summaries."""
    base_dir = Path(run_dir)
    if not base_dir.exists():
        return pd.DataFrame()

    rows = []
    for summary_path in sorted(base_dir.glob("run_id=*/run_summary.json")):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"[WARN] Skipping invalid production summary {summary_path}: {error}")
            continue

        payload["_summary_path"] = str(summary_path)
        rows.append(payload)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _resolve_summary_path(summary_path: str | Path, run_dir: Path) -> Path:
    candidate = Path(summary_path)
    if candidate.is_absolute():
        return candidate

    candidates = [
        run_dir / candidate,
        run_dir.parent / candidate,
        run_dir.parent.parent / candidate,
        run_dir.parent.parent.parent / candidate,
    ]
    for path in candidates:
        if path.exists():
            return path

    return run_dir / candidate


@st.cache_data(show_spinner=False)
def load_latest_production_summary(run_dir: Path | str = PIPELINE_RUN_DIR) -> dict:
    """Load latest published production summary from pointer or filtered fallback."""
    base_dir = Path(run_dir)
    pointer_path = base_dir / "latest_production.json"
    if pointer_path.exists():
        try:
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            summary_path = _resolve_summary_path(pointer["summary_path"], base_dir)
            if summary_path.exists():
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                if _is_published_production_payload(payload):
                    return payload
        except (KeyError, OSError, json.JSONDecodeError):
            pass

    summaries_df = load_production_run_summaries(base_dir)
    if summaries_df.empty:
        return {}

    required_cols = {"run_class", "pipeline_status", "publish_status"}
    if not required_cols.issubset(summaries_df.columns):
        return {}

    eligible = summaries_df[
        (summaries_df["run_class"] == "production")
        & (summaries_df["pipeline_status"] == "success")
        & (summaries_df["publish_status"] == "published")
    ].copy()
    if eligible.empty:
        return {}

    sort_cols = [col for col in ("run_date", "end_time", "run_id") if col in eligible.columns]
    if sort_cols:
        eligible = eligible.sort_values(sort_cols)
    return eligible.tail(1).iloc[0].dropna().to_dict()


@st.cache_data(show_spinner=False)
def load_quarantine_counts(base_dir: Path | str = QUARANTINE_DIR) -> pd.DataFrame:
    """Count quarantine JSONL records by stage, source, date, and run id."""
    root = Path(base_dir)
    if not root.exists():
        return pd.DataFrame(
            columns=[
                "rejection_stage",
                "source_code",
                "run_date",
                "run_id",
                "quarantine_count",
            ]
        )

    counts: dict[tuple[str, str, str, str], int] = {}
    for jsonl_path in sorted(root.glob("*/source=*/date=*/quarantine_*.jsonl")):
        stage = jsonl_path.parts[-4]
        source_code = jsonl_path.parts[-3].split("=", 1)[-1]
        run_date = jsonl_path.parts[-2].split("=", 1)[-1]
        run_id = jsonl_path.stem.removeprefix("quarantine_")
        key = (stage, source_code, run_date, run_id)
        counts[key] = counts.get(key, 0) + _count_jsonl_records(jsonl_path)

    rows = [
        {
            "rejection_stage": stage,
            "source_code": source_code,
            "run_date": run_date,
            "run_id": run_id,
            "quarantine_count": count,
        }
        for (stage, source_code, run_date, run_id), count in counts.items()
    ]
    return pd.DataFrame(rows)


def _is_published_production_payload(payload: dict) -> bool:
    return (
        payload.get("run_class") == "production"
        and payload.get("pipeline_status") == "success"
        and payload.get("publish_status") == "published"
    )


def _count_jsonl_records(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0
