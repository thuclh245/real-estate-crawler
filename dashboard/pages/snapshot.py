import pandas as pd
import plotly.express as px
import streamlit as st


def render_snapshot(snapshot_df: pd.DataFrame, removed_df: pd.DataFrame) -> None:
    st.subheader("Snapshot Tracking")

    if snapshot_df.empty and removed_df.empty:
        st.info("Chưa có dữ liệu snapshot")
        return

    st.write("Snapshot records:", len(snapshot_df))

    if "snapshot_status" in snapshot_df.columns:
        status_counts = (
            snapshot_df.groupby(["snapshot_date", "snapshot_status"])
            .size()
            .reset_index(name="count")
        )
        fig = px.bar(
            status_counts,
            x="snapshot_date",
            y="count",
            color="snapshot_status",
            title="Snapshot Status by Date",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(status_counts, use_container_width=True)

    if "is_price_changed" in snapshot_df.columns:
        changed_df = snapshot_df[snapshot_df["is_price_changed"] == True]
        st.subheader("Price Changed Listings")
        st.write(f"Price changed records: {len(changed_df):,}")
        cols = [
            "snapshot_date",
            "dedup_key",
            "listing_id",
            "title_raw",
            "previous_price_vnd",
            "current_price_vnd",
            "price_change_vnd",
            "price_change_pct",
            "district_norm",
            "property_type_group",
        ]
        cols = [col for col in cols if col in changed_df.columns]
        st.dataframe(changed_df[cols], use_container_width=True)

    if "is_info_changed" in snapshot_df.columns:
        info_changed_df = snapshot_df[snapshot_df["is_info_changed"] == True]
        st.subheader("Info Changed Listings")
        st.write(f"Info changed records: {len(info_changed_df):,}")
        cols = [
            "snapshot_date",
            "dedup_key",
            "listing_id",
            "title_raw",
            "changed_fields",
            "district_norm",
            "property_type_group",
            "listing_url",
        ]
        cols = [col for col in cols if col in info_changed_df.columns]
        st.dataframe(info_changed_df[cols], use_container_width=True)

    st.subheader("Removed Listings")
    st.write(f"Removed listing records: {len(removed_df):,}")
    st.dataframe(removed_df, use_container_width=True)
