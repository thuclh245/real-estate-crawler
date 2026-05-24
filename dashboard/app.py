import pandas as pd
import streamlit as st

from dashboard.data_loaders import read_gold_table
from dashboard.pages.listings import render_listings
from dashboard.pages.market import render_market
from dashboard.pages.overview import render_overview
from dashboard.pages.pipeline_health import render_pipeline_health
from dashboard.pages.quality import render_quality
from dashboard.pages.snapshot import render_snapshot


st.set_page_config(
    page_title="Real Estate Lakehouse Dashboard",
    page_icon="🏠",
    layout="wide",
)


def load_gold_table_or_empty(table_name: str) -> tuple[pd.DataFrame, str | None]:
    try:
        return read_gold_table(table_name), None
    except FileNotFoundError as error:
        return pd.DataFrame(), str(error)
    except Exception as error:
        return pd.DataFrame(), f"Unexpected error while loading {table_name}: {error}"


def main() -> None:
    st.title("Real Estate Lakehouse Dashboard")
    st.caption("Streamlit giữ các view kỹ thuật/ops; market-facing BI sẽ chuyển dần sang Power BI ở V2.")

    table_names = [
        "gold_current_listings",
        "gold_listing_snapshots",
        "gold_market_by_district_daily",
        "gold_market_by_property_type_daily",
        "gold_data_quality_daily",
        "gold_removed_listings",
    ]

    loaded_tables: dict[str, pd.DataFrame] = {}
    missing_messages: list[str] = []
    for table_name in table_names:
        table_df, error = load_gold_table_or_empty(table_name)
        loaded_tables[table_name] = table_df
        if error:
            missing_messages.append(f"{table_name}: {error}")

    for message in missing_messages:
        st.warning(message)

    current_df = loaded_tables["gold_current_listings"]
    snapshot_df = loaded_tables["gold_listing_snapshots"]
    district_df = loaded_tables["gold_market_by_district_daily"]
    property_type_df = loaded_tables["gold_market_by_property_type_daily"]
    quality_df = loaded_tables["gold_data_quality_daily"]
    removed_df = loaded_tables["gold_removed_listings"]

    tab_overview, tab_quality, tab_health, tab_market, tab_listings, tab_snapshot = st.tabs(
        [
            "Overview",
            "Data Quality",
            "Pipeline Health",
            "Market (Legacy)",
            "Technical Listings Explorer",
            "Snapshot Tracking",
        ]
    )

    with tab_overview:
        render_overview(current_df, snapshot_df, quality_df)

    with tab_quality:
        render_quality(quality_df)

    with tab_health:
        render_pipeline_health()

    with tab_market:
        render_market(district_df, property_type_df)

    with tab_listings:
        render_listings(current_df)

    with tab_snapshot:
        render_snapshot(snapshot_df, removed_df)


if __name__ == "__main__":
    main()