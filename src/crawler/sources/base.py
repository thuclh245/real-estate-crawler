from typing import Protocol


class SourceAdapter(Protocol):
    source_code: str

    def build_seed_urls(self, config: dict) -> list[str]: ...

    def parse_list_page(self, html: str) -> list[dict]: ...

    def parse_detail_page(self, html: str) -> dict: ...
