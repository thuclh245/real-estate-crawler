from __future__ import annotations

import warnings

warnings.warn(
    "crawler.parsing.feature_extractors is deprecated; use parsing.sources.batdongsan.feature_extractor",
    DeprecationWarning,
    stacklevel=2,
)

from parsing.sources.batdongsan.feature_extractor import *  # noqa: F401,F403
