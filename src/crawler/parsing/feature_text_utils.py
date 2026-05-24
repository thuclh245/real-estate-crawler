from __future__ import annotations

import warnings

warnings.warn(
    "crawler.parsing.feature_text_utils is deprecated; use parsing.sources.batdongsan.feature_text_utils",
    DeprecationWarning,
    stacklevel=2,
)

from parsing.sources.batdongsan.feature_text_utils import *  # noqa: F401,F403
