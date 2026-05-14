from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


GOLD_DIR = Path("data/gold")


st.set_page_config(
    page_title="Real Estate Lakehouse Dashboard",
    page_icon="🏠",
    layout="wide",
)


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


def add_hive_partitions(df: pd.DataFrame, file_path: Path, table_path: Path) -> pd.DataFrame:
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
            return pd.concat([pd.read_csv(file_path) for file_path in csv_files], ignore_index=True)

    raise FileNotFoundError(f"Cannot read Gold table: {path}")


@st.cache_data(show_spinner=False)
def read_phase3_summary() -> dict:
    summary_path = GOLD_DIR / "phase3_summary.json"
    if not summary_path.exists():
        return {}
    return pd.read_json(summary_path, typ="series").to_dict()


def format_pct(value) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


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


def render_quality(quality_df: pd.DataFrame) -> None:
    st.subheader("Data Quality Monitoring")
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


def render_market(district_df: pd.DataFrame, property_type_df: pd.DataFrame) -> None:
    st.subheader("Market Analytics")
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
            fig = px.bar(unit_price, x="district_norm", y="median_unit_price_vnd_m2", title="Top Districts by Median Unit Price VND/m²")
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


def render_listings(current_df: pd.DataFrame) -> None:
    st.subheader("Listings Explorer")
    filtered = current_df.copy()

    col1, col2, col3 = st.columns(3)

    with col1:
        if "district_norm" in filtered.columns:
            selected = st.multiselect("District", sorted(filtered["district_norm"].dropna().astype(str).unique()), default=[])
            if selected:
                filtered = filtered[filtered["district_norm"].isin(selected)]

    with col2:
        if "property_type_group" in filtered.columns:
            selected = st.multiselect("Property Type", sorted(filtered["property_type_group"].dropna().astype(str).unique()), default=[])
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


def render_snapshot(snapshot_df: pd.DataFrame, removed_df: pd.DataFrame) -> None:
    st.subheader("Snapshot Tracking")
    st.write("Snapshot records:", len(snapshot_df))

    if "snapshot_status" in snapshot_df.columns:
        status_counts = snapshot_df.groupby(["snapshot_date", "snapshot_status"]).size().reset_index(name="count")
        fig = px.bar(status_counts, x="snapshot_date", y="count", color="snapshot_status", title="Snapshot Status by Date")
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


def main() -> None:
    st.title("Real Estate Lakehouse Dashboard")
    st.caption("Gold Layer Analytics for Batdongsan Real Estate Listings")

    try:
        current_df = read_gold_table("gold_current_listings")
        snapshot_df = read_gold_table("gold_listing_snapshots")
        district_df = read_gold_table("gold_market_by_district_daily")
        property_type_df = read_gold_table("gold_market_by_property_type_daily")
        quality_df = read_gold_table("gold_data_quality_daily")
        removed_df = read_gold_table("gold_removed_listings")
    except Exception as error:
        st.error(f"Cannot load Gold tables: {error}")
        st.stop()

    tab_overview, tab_quality, tab_market, tab_listings, tab_snapshot = st.tabs(
        [
            "Overview",
            "Data Quality",
            "Market",
            "Listings Explorer",
            "Snapshot Tracking",
        ]
    )

    with tab_overview:
        render_overview(current_df, snapshot_df, quality_df)

    with tab_quality:
        render_quality(quality_df)

    with tab_market:
        render_market(district_df, property_type_df)

    with tab_listings:
        render_listings(current_df)

    with tab_snapshot:
        render_snapshot(snapshot_df, removed_df)


if __name__ == "__main__":
    main()
