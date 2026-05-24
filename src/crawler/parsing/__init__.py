from __future__ import annotations

import warnings

warnings.warn(
    "crawler.parsing is deprecated; use parsing.*",
    DeprecationWarning,
    stacklevel=2,
)

from parsing import FEATURE_OUTPUT_KEYS, FEATURE_PATTERNS, build_search_text, extract_features, normalize_text


__all__ = [
    "FEATURE_OUTPUT_KEYS",
    "FEATURE_PATTERNS",
    "build_search_text",
    "extract_features",
    "normalize_text",
]
