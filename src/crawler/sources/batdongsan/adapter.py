from crawler.crawl_config import expand_targets, get_target_location_path
from crawler.detail_page_parser import parse_detail_page_location_fields
from crawler.list_page_parser import extract_listing_entries_from_listing_page
from crawler.url_builder import build_seed_url


class BatdongsanAdapter:
    source_code = "batdongsan"

    def build_seed_urls(self, config: dict) -> list[str]:
        base_url = config["base_url"]
        settings = config.get("crawl_settings", {})
        max_pages = settings.get("max_pages_per_target", 2)
        urls: list[str] = []

        for target in expand_targets(config):
            seed_url_override = target.get("seed_url")
            if seed_url_override:
                urls.extend(
                    seed_url_override if page_number == 1 else f"{seed_url_override}/p{page_number}"
                    for page_number in range(1, max_pages + 1)
                )
                continue

            urls.extend(
                build_seed_url(
                    base_url,
                    target["category"],
                    get_target_location_path(target),
                    page_number,
                )
                for page_number in range(1, max_pages + 1)
            )

        return urls

    def parse_list_page(self, html: str) -> list[dict]:
        return extract_listing_entries_from_listing_page(html)

    def parse_detail_page(self, html: str) -> dict:
        return parse_detail_page_location_fields(html)
