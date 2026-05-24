"""Current parsing package for bronze -> silver feature extraction.

Use this package instead of ``crawler.parsing``. The old package remains as a
compatibility shim for existing scripts and dashboard imports.
"""

from .contracts import BronzeListingMetadata, GoldListingRecord, SilverListingRecord
from .sources.batdongsan.feature_extractor import FEATURE_OUTPUT_KEYS, extract_features
from .sources.batdongsan.feature_patterns import FEATURE_PATTERNS
from .sources.batdongsan.feature_text_utils import build_search_text, normalize_text
from .sources.batdongsan.silver_parser import parse_listing

__all__ = [
    "BronzeListingMetadata",
    "FEATURE_OUTPUT_KEYS",
    "FEATURE_PATTERNS",
    "GoldListingRecord",
    "SilverListingRecord",
    "build_search_text",
    "extract_features",
    "normalize_text",
    "parse_listing",
]
