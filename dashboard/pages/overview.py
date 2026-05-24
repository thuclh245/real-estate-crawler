import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_loaders import read_phase3_summary
from dashboard.formatters import format_pct


def render_overview(current_df: pd.DataFrame, snapshot_df: pd.DataFrame, quality_df: pd.DataFrame) -> None:
    st.subheader("Pipeline Overview")

    summary = read_phase3_summary()
    latest_quality = quality_df.sort_values("crawl_date").tail(1).iloc[0] if not quality_df.empty else {}

    total_current = int(summary.get("total_current_listings", len(current_df)))
    total_records = int(summary.get("total_silver_records", latest_quality.get("total_records", 0)))
    duplicate_rate = summary.get("duplicate_rate", latest_quality.get("duplicate_rate", None))
    parse_success_rate = summary.get("parse_success_rate", latest_quality.get("parse_success_rate", None))
    missing_price_rate = summary.get("missing_price_rate", latest_quality.get("missing_price_rate", None))
    missing_area_rate = summary.get("missing_area_rate", latest_quality.get("missing_area_rate", None))
    missing_location_rate = summary.get("missing_location_rate", latest_quality.get("missing_location_rate", None))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Listings", f"{total_current:,}")
    c2.metric("Silver Records", f"{total_records:,}")
    c3.metric("Duplicate Rate", format_pct(duplicate_rate))
    c4.metric("Parse Success Rate", format_pct(parse_success_rate))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Missing Price Rate", format_pct(missing_price_rate))
    c6.metric("Missing Area Rate", format_pct(missing_area_rate))
    c7.metric("Missing Location Rate", format_pct(missing_location_rate))
    c8.metric("Snapshot Dates", snapshot_df["snapshot_date"].nunique() if "snapshot_date" in snapshot_df.columns else 0)

    left, right = st.columns(2)

    with left:
        if "snapshot_status" in snapshot_df.columns:
            status_counts = snapshot_df["snapshot_status"].fillna("unknown").value_counts().reset_index()
            status_counts.columns = ["snapshot_status", "count"]
            fig = px.pie(status_counts, names="snapshot_status", values="count", title="Snapshot Status Distribution")
            st.plotly_chart(fig, use_container_width=True)

    with right:
        if "property_type_group" in current_df.columns:
            property_counts = current_df["property_type_group"].fillna("unknown").value_counts().reset_index()
            property_counts.columns = ["property_type_group", "count"]
            fig = px.bar(property_counts, x="property_type_group", y="count", title="Listings by Property Type")
            st.plotly_chart(fig, use_container_width=True)
