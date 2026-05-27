import re

from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    """Convert HTML into readable text for Bronze debugging and future parsing."""
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_listing_id(url: str) -> str | None:
    match = re.search(r"pr(\d+)", url)
    if match:
        return match.group(1)
    return None


def extract_phase1_stub_fields(_detail_text: str, listing_url: str) -> dict:
    """Keep extraction minimal in Phase 1; deep parsing is deferred to Phase 3."""
    return {
        "listing_id": extract_listing_id(listing_url),
        "title_raw": None,
        "price_raw": None,
        "area_raw": None,
    }
