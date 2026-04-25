def build_seed_url(
    base_url: str, 
    category: str, 
    district: str, 
    page_number: int = 1) -> str:
    """
    Build listing page URL from category and district.

    Example:
    category = ban-nha-rieng
    district = cau-giay
    page_number = 1

    Output:
    https://batdongsan.com.vn/ban-nha-rieng-cau-giay
    """
    url = f"{base_url}/{category}-{district}"

    if page_number > 1:
        url = f"{url}/p{page_number}"

    return url