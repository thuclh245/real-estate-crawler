from parsing.normalizers import clean_text


def parse_detail_page_location_fields(html: str) -> dict:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "lxml")
    title = (
        clean_text(
            soup.select_one(".re__pr-title, .js__pr-title").get_text(" ", strip=True)
        )
        if soup.select_one(".re__pr-title, .js__pr-title")
        else None
    )
    address = (
        clean_text(soup.select_one(".re__address-line-1").get_text(" ", strip=True))
        if soup.select_one(".re__address-line-1")
        else None
    )
    breadcrumb = (
        clean_text(
            soup.select_one(".re__breadcrumb, .js__breadcrumb").get_text(
                " ", strip=True
            )
        )
        if soup.select_one(".re__breadcrumb, .js__breadcrumb")
        else None
    )
    description = (
        clean_text(soup.select_one(".re__section-body").get_text(" ", strip=True))
        if soup.select_one(".re__section-body")
        else None
    )

    return {
        "detail_title": title,
        "detail_address_raw": address,
        "breadcrumb_raw": breadcrumb,
        "breadcrumb_location_raw": breadcrumb,
        "detail_description": description,
    }
