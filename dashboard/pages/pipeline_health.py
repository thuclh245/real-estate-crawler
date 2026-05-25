from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_loaders import (
    PIPELINE_LOG_DIR,
    PIPELINE_RUN_DIR,
    QUARANTINE_DIR,
    load_latest_production_summary,
    load_production_run_summaries,
    load_quarantine_counts,
    load_run_summaries,
)
from dashboard.formatters import format_pct


def render_pipeline_health(
    log_dir: Path | str = PIPELINE_LOG_DIR,
    run_dir: Path | str = PIPELINE_RUN_DIR,
    quarantine_dir: Path | str = QUARANTINE_DIR,
) -> None:
    st.subheader("Pipeline Health")
    summaries_df = load_run_summaries(log_dir)
    production_df = load_production_run_summaries(run_dir)
    quarantine_df = load_quarantine_counts(quarantine_dir)

    if summaries_df.empty and production_df.empty:
        st.info("Chua co du lieu pipeline run")
        return

    sort_col = "run_date" if "run_date" in summaries_df.columns else None
    latest_production = load_latest_production_summary(run_dir)
    latest = (
        pd.Series(latest_production)
        if latest_production
        else (
            summaries_df.sort_values(sort_col).tail(1).iloc[0]
            if sort_col and not summaries_df.empty
            else summaries_df.tail(1).iloc[0]
        )
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Parse Success Rate", format_pct(latest.get("parse_success_rate")))
    c2.metric("Duplicate Rate", format_pct(latest.get("duplicate_rate")))
    c3.metric("Missing Price Rate", format_pct(latest.get("missing_price_rate")))
    latest_total_records = (
        latest.get("total_silver_records") or latest.get("silver_records_written") or 0
    )
    c4.metric("Total Records", f"{int(latest_total_records):,}")
    latest_quarantine_count = latest.get("silver_quarantine_count") or _quarantine_count_for_run(
        quarantine_df,
        latest.get("run_id"),
    )
    c5.metric("Quarantine Records", f"{int(latest_quarantine_count):,}")

    status_payload = {
        "run_id": latest.get("run_id"),
        "run_date": latest.get("run_date"),
        "run_class": latest.get("run_class"),
        "pipeline_mode": latest.get("pipeline_mode"),
        "pipeline_status": latest.get("pipeline_status"),
        "validation_status": latest.get("validation_status"),
        "publish_status": latest.get("publish_status"),
        "publish_block_reason": latest.get("publish_block_reason"),
    }
    st.dataframe(pd.DataFrame([status_payload]), use_container_width=True)

    trend_metrics = [
        "parse_success_rate",
        "duplicate_rate",
        "missing_price_rate",
    ]
    available = [col for col in trend_metrics if col in summaries_df.columns]
    if "run_date" in summaries_df.columns and available:
        trend_df = summaries_df[["run_date", *available]].copy()
        for col in available:
            trend_df[col] = pd.to_numeric(trend_df[col], errors="coerce")
        trend_long = trend_df.melt(
            id_vars=["run_date"],
            value_vars=available,
            var_name="metric",
            value_name="value",
        )
        fig = px.line(
            trend_long,
            x="run_date",
            y="value",
            color="metric",
            markers=True,
            title="Pipeline Quality Trend",
        )
        st.plotly_chart(fig, use_container_width=True)

    snapshot_rows = []
    for _, row in summaries_df.iterrows():
        snapshot_dates = row.get("snapshot_dates")
        if not isinstance(snapshot_dates, list):
            continue
        for snapshot_date in snapshot_dates:
            snapshot_rows.append(
                {
                    "run_date": row.get("run_date"),
                    "snapshot_date": snapshot_date,
                    "total_silver_records": row.get("total_silver_records"),
                }
            )
    if snapshot_rows:
        snapshot_count_df = pd.DataFrame(snapshot_rows)
        fig = px.bar(
            snapshot_count_df,
            x="snapshot_date",
            y="total_silver_records",
            color="run_date",
            title="Record Count by Snapshot Date",
        )
        st.plotly_chart(fig, use_container_width=True)

    if not production_df.empty:
        source_rows = _build_source_scorecards(production_df, quarantine_df)
        if source_rows:
            st.dataframe(pd.DataFrame(source_rows), use_container_width=True)

        production_cols = [
            "run_date",
            "run_id",
            "pipeline_mode",
            "run_class",
            "pipeline_status",
            "validation_status",
            "publish_status",
            "publish_block_reason",
            "source_names",
            "silver_records_written",
            "silver_quarantine_count",
            "duration_seconds",
            "error_message",
        ]
        production_cols = [col for col in production_cols if col in production_df.columns]
        sort_cols = [col for col in ("run_date", "end_time", "run_id") if col in production_df.columns]
        display_df = (
            production_df.sort_values(sort_cols, ascending=False)
            if sort_cols
            else production_df
        )
        st.dataframe(display_df[production_cols], use_container_width=True)

    if not quarantine_df.empty:
        quarantine_display = quarantine_df.sort_values(
            ["run_date", "source_code", "rejection_stage"],
            ascending=False,
        )
        st.dataframe(quarantine_display, use_container_width=True)

    history_cols = [
        "run_date",
        "run_id",
        "pipeline_mode",
        "pipeline_status",
        "validation_status",
        "gcs_sync_status",
        "total_silver_records",
        "total_current_listings",
        "duplicate_rate",
        "parse_success_rate",
        "missing_price_rate",
        "duration_seconds",
        "error_message",
    ]
    history_cols = [col for col in history_cols if col in summaries_df.columns]
    if history_cols:
        st.dataframe(
            (
                summaries_df.sort_values("run_date", ascending=False)[history_cols]
                if "run_date" in summaries_df.columns
                else summaries_df[history_cols]
            ),
            use_container_width=True,
        )


def _quarantine_count_for_run(quarantine_df: pd.DataFrame, run_id: str | None) -> int:
    if quarantine_df.empty or not run_id or "run_id" not in quarantine_df.columns:
        return 0
    rows = quarantine_df[quarantine_df["run_id"] == run_id]
    if rows.empty:
        return 0
    return int(pd.to_numeric(rows["quarantine_count"], errors="coerce").fillna(0).sum())


def _build_source_scorecards(
    production_df: pd.DataFrame,
    quarantine_df: pd.DataFrame,
) -> list[dict]:
    if "source_names" not in production_df.columns:
        return []

    rows = []
    for _, run in production_df.iterrows():
        source_names = run.get("source_names")
        if not isinstance(source_names, list):
            source_names = [source_names] if source_names else []
        for source_name in source_names:
            rows.append(
                {
                    "source_code": source_name,
                    "run_id": run.get("run_id"),
                    "run_date": run.get("run_date"),
                    "publish_status": run.get("publish_status"),
                    "silver_records_written": run.get("silver_records_written"),
                    "silver_quarantine_count": run.get("silver_quarantine_count")
                    or _quarantine_count_for_run(quarantine_df, run.get("run_id")),
                    "parse_success_rate": run.get("parse_success_rate"),
                    "missing_price_rate": run.get("missing_price_rate"),
                }
            )
    return rows
