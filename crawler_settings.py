from pathlib import Path

BASE_URL = "https://batdongsan.com.vn"
DEFAULT_LISTING_URL = "https://batdongsan.com.vn/nha-dat-ban"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name("crawler_config.json")
OUTPUT_COLUMNS = [
    "source",
    "scraped_at",
    "title",
    "description",
    "price",
    "price_raw",
    "city",
    "district",
    "ward",
    "address",
    "property_size",
    "property_size_raw",
    "property_type",
    "bedrooms",
    "bathrooms",
    "amenities",
    "currency",
    "listing_id",
    "crawl_status",
    "listing_url",
]
