import pandas as pd
import plotly.express as px
import streamlit as st


def render_market(district_df: pd.DataFrame, property_type_df: pd.DataFrame) -> None:
    st.subheader("Market Analytics")
    st.caption("Legacy / business-facing preview; V2 BI pages should move here later.")

    if district_df.empty and property_type_df.empty:
        st.info("Chưa có dữ liệu market")
        return

    market_tab_district, market_tab_type = st.tabs(["By District", "By Property Type"])

    with market_tab_district:
        district_view = district_df.copy()
        if "district_norm" in district_view.columns:
            selected = st.multiselect(
                "Select districts",
                options=sorted(district_view["district_norm"].dropna().astype(str).unique()),
                default=[],
            )
            if selected:
                district_view = district_view[district_view["district_norm"].isin(selected)]

        st.dataframe(district_view, use_container_width=True)

        if {"district_norm", "listing_count"}.issubset(district_view.columns):
            top_count = (
                district_view.groupby("district_norm", as_index=False)["listing_count"]
                .sum()
                .sort_values("listing_count", ascending=False)
                .head(20)
            )
            fig = px.bar(top_count, x="district_norm", y="listing_count", title="Top Districts by Listing Count")
            st.plotly_chart(fig, use_container_width=True)

        if {"district_norm", "median_unit_price_vnd_m2"}.issubset(district_view.columns):
            unit_price = (
                district_view.dropna(subset=["median_unit_price_vnd_m2"])
                .groupby("district_norm", as_index=False)["median_unit_price_vnd_m2"]
                .median()
                .sort_values("median_unit_price_vnd_m2", ascending=False)
                .head(20)
            )
            fig = px.bar(
                unit_price,
                x="district_norm",
                y="median_unit_price_vnd_m2",
                title="Top Districts by Median Unit Price VND/m²",
            )
            st.plotly_chart(fig, use_container_width=True)

    with market_tab_type:
        st.dataframe(property_type_df, use_container_width=True)

        if {"property_type_group", "listing_count"}.issubset(property_type_df.columns):
            fig = px.bar(
                property_type_df.sort_values("listing_count", ascending=False),
                x="property_type_group",
                y="listing_count",
                title="Listing Count by Property Type",
            )
            st.plotly_chart(fig, use_container_width=True)

        if {"property_type_group", "median_unit_price_vnd_m2"}.issubset(property_type_df.columns):
            fig = px.bar(
                property_type_df.sort_values("median_unit_price_vnd_m2", ascending=False),
                x="property_type_group",
                y="median_unit_price_vnd_m2",
                title="Median Unit Price VND/m² by Property Type",
            )
            st.plotly_chart(fig, use_container_width=True)
