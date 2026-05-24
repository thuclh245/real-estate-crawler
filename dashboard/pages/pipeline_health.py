from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_loaders import PIPELINE_LOG_DIR, load_latest_production_summary, load_run_summaries
from dashboard.formatters import format_pct


def render_pipeline_health(log_dir: Path | str = PIPELINE_LOG_DIR) -> None:
    st.subheader("Pipeline Health")
    summaries_df = load_run_summaries(log_dir)

    if summaries_df.empty:
        st.info("Chưa có dữ liệu pipeline run")
        return

    sort_col = "run_date" if "run_date" in summaries_df.columns else None
    latest_production = load_latest_production_summary()
    latest = (
        pd.Series(latest_production)
        if latest_production
        else summaries_df.sort_values(sort_col).tail(1).iloc[0] if sort_col else summaries_df.tail(1).iloc[0]
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Parse Success Rate", format_pct(latest.get("parse_success_rate")))
    c2.metric("Duplicate Rate", format_pct(latest.get("duplicate_rate")))
    c3.metric("Missing Price Rate", format_pct(latest.get("missing_price_rate")))
    latest_total_records = latest.get("total_silver_records") or latest.get("silver_records_written") or 0
    c4.metric("Total Records", f"{int(latest_total_records):,}")

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
    st.dataframe(
        summaries_df.sort_values("run_date", ascending=False)[history_cols]
        if "run_date" in summaries_df.columns
        else summaries_df[history_cols],
        use_container_width=True,
    )
