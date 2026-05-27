def build_seed_url(
    base_url: str, category_slug: str, location_path: str, page_number: int = 1
) -> str:
    """
    Build listing page URL from category and full Batdongsan location path.

    Example:
    category_slug = ban-nha-rieng
    location_path = phuong-cau-giay-tp-ha-noi
    page_number = 1

    Output:
    https://batdongsan.com.vn/ban-nha-rieng-phuong-cau-giay-tp-ha-noi
    """
    url = f"{base_url.rstrip('/')}/{category_slug}-{location_path}"

    if page_number > 1:
        url = f"{url}/p{page_number}"

    return url
