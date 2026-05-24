def is_blocked_page(
    http_status: int,
    html: str,
    listing_urls_found: int | None = None,
) -> bool:
    html_lower = (html or "").lower()

    if http_status in [403, 429]:
        return True

    block_signals = [
        "<title>just a moment",
        "cf-browser-verification",
        "/cdn-cgi/challenge-platform",
        "__cf_chl",
        "cf-chl-",
        "attention required! | cloudflare",
        "g-recaptcha",
        "h-captcha",
    ]

    has_block_signal = any(signal in html_lower for signal in block_signals)
    if not has_block_signal:
        return False

    # If listing URLs are already extracted from a listing page, treat content as usable.
    if listing_urls_found is not None and listing_urls_found > 0:
        return False

    return True


def increment_http_counters(summary: dict, http_status: int | None) -> None:
    if http_status == 403:
        summary["http_403_count"] += 1
    elif http_status == 429:
        summary["http_429_count"] += 1


def classify_failure_status(
    http_status: int | None,
    error_message: str | None = None,
) -> str:
    error_lower = (error_message or "").lower()
    if http_status in {403, 429}:
        return "blocked"
    if http_status is not None:
        return "failed_http"
    if "timeout" in error_lower or "timed out" in error_lower:
        return "failed_timeout"
    return "failed_fetch"
