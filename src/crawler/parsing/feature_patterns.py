from __future__ import annotations

import warnings

warnings.warn(
    "crawler.parsing.feature_patterns is deprecated; use parsing.sources.batdongsan.feature_patterns",
    DeprecationWarning,
    stacklevel=2,
)

from parsing.sources.batdongsan.feature_patterns import *  # noqa: F401,F403
