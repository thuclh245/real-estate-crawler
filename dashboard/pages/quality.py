import pandas as pd
import plotly.express as px
import streamlit as st


def render_quality(quality_df: pd.DataFrame) -> None:
    st.subheader("Data Quality Monitoring")

    if quality_df.empty:
        st.info("Chưa có dữ liệu data quality")
        return

    st.dataframe(quality_df, use_container_width=True)

    metric_cols = [
        "parse_success_rate",
        "missing_price_rate",
        "missing_area_rate",
        "missing_location_rate",
        "duplicate_rate",
        "negotiable_price_rate",
    ]
    available = [col for col in metric_cols if col in quality_df.columns]

    if "crawl_date" in quality_df.columns and available:
        quality_long = quality_df.melt(
            id_vars=["crawl_date"],
            value_vars=available,
            var_name="metric",
            value_name="value",
        )
        fig = px.line(
            quality_long,
            x="crawl_date",
            y="value",
            color="metric",
            markers=True,
            title="Data Quality Rates by Crawl Date",
        )
        st.plotly_chart(fig, use_container_width=True)
