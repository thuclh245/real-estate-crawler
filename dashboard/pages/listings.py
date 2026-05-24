import pandas as pd
import streamlit as st

from dashboard.formatters import numeric_series


def render_listings(current_df: pd.DataFrame) -> None:
    st.subheader("Technical Listings Explorer")

    if current_df.empty:
        st.info("Chưa có dữ liệu current listings")
        return

    filtered = current_df.copy()

    col1, col2, col3 = st.columns(3)

    with col1:
        if "district_norm" in filtered.columns:
            selected = st.multiselect("District", sorted(filtered["district_norm"].dropna().astype(str).unique()), default=[])
            if selected:
                filtered = filtered[filtered["district_norm"].isin(selected)]

    with col2:
        if "property_type_group" in filtered.columns:
            selected = st.multiselect(
                "Property Type",
                sorted(filtered["property_type_group"].dropna().astype(str).unique()),
                default=[],
            )
            if selected:
                filtered = filtered[filtered["property_type_group"].isin(selected)]

    with col3:
        if "price_unit" in filtered.columns:
            price_mode = st.selectbox("Price Mode", ["All", "Listed Price", "Negotiable"])
            if price_mode == "Listed Price":
                filtered = filtered[filtered["price_unit"] != "negotiable"]
            elif price_mode == "Negotiable":
                filtered = filtered[filtered["price_unit"] == "negotiable"]

    enrich_col1, enrich_col2, enrich_col3, enrich_col4 = st.columns(4)

    with enrich_col1:
        if "has_legal_info" in filtered.columns:
            legal_mode = st.selectbox("Legal Info", ["All", "Has Legal Info", "No Legal Info"])
            if legal_mode == "Has Legal Info":
                filtered = filtered[filtered["has_legal_info"] == True]
            elif legal_mode == "No Legal Info":
                filtered = filtered[filtered["has_legal_info"] != True]

    with enrich_col2:
        if "is_business_suitable" in filtered.columns:
            business_mode = st.selectbox("Business Suitable", ["All", "Yes", "No"])
            if business_mode == "Yes":
                filtered = filtered[filtered["is_business_suitable"] == True]
            elif business_mode == "No":
                filtered = filtered[filtered["is_business_suitable"] != True]

    with enrich_col3:
        if "has_car_access" in filtered.columns:
            car_mode = st.selectbox("Car Access", ["All", "Yes", "No"])
            if car_mode == "Yes":
                filtered = filtered[filtered["has_car_access"] == True]
            elif car_mode == "No":
                filtered = filtered[filtered["has_car_access"] != True]

    with enrich_col4:
        if "furniture_level" in filtered.columns:
            selected = st.multiselect(
                "Furniture",
                sorted(filtered["furniture_level"].dropna().astype(str).unique()),
                default=[],
            )
            if selected:
                filtered = filtered[filtered["furniture_level"].isin(selected)]

    price_values = numeric_series(filtered, "price_vnd")
    if not price_values.empty and price_values.notna().any() and "price_vnd" in filtered.columns:
        min_price, max_price = float(price_values.min()), float(price_values.max())
        selected_range = st.slider(
            "Price range",
            min_value=min_price,
            max_value=max_price,
            value=(min_price, max_price),
            format="%.0f",
        )
        filtered = filtered[(numeric_series(filtered, "price_vnd").between(*selected_range)) | (filtered["price_vnd"].isna())]

    st.write(f"Showing {len(filtered):,} listings")

    display_cols = [
        "snapshot_date",
        "listing_id",
        "title_raw",
        "price_raw",
        "price_vnd",
        "area_m2",
        "unit_price_vnd_m2",
        "district_norm",
        "property_type_group",
        "has_legal_info",
        "legal_status_raw",
        "has_red_pink_book",
        "furniture_level",
        "frontage_width",
        "project_name",
        "is_business_suitable",
        "has_urban_area_flag",
        "has_security_flag",
        "has_educated_community_flag",
        "has_high_intellect_flag",
        "has_residential_area_flag",
        "has_subdivision_flag",
        "direction",
        "is_price_negotiable",
        "has_car_access",
        "car_access_type",
        "building_name",
        "snapshot_status",
        "is_info_changed",
        "changed_fields",
        "listing_url",
    ]
    display_cols = [col for col in display_cols if col in filtered.columns]
    st.dataframe(filtered[display_cols], use_container_width=True)
