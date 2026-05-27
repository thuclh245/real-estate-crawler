def is_blocked_page(
    http_status: int,
    html: str,
    listing_urls_found: int | None = None,
) -> bool:
    return (
        detect_block_reason(
            http_status,
            html,
            listing_urls_found=listing_urls_found,
        )
        is not None
    )


def detect_block_reason(
    http_status: int | None,
    html: str,
    listing_urls_found: int | None = None,
) -> str | None:
    html_lower = (html or "").lower()

    if http_status == 403:
        return "http_403"
    if http_status == 429:
        return "http_429"

    block_signals = [
        ("cloudflare_turnstile", "challenges.cloudflare.com/turnstile"),
        ("cloudflare_challenge", "<title>just a moment"),
        ("cloudflare_challenge", "cf-browser-verification"),
        ("cloudflare_challenge", "/cdn-cgi/challenge-platform"),
        ("cloudflare_challenge", "__cf_chl"),
        ("cloudflare_challenge", "cf-chl-"),
        ("cloudflare_challenge", "attention required! | cloudflare"),
        ("captcha", "g-recaptcha"),
        ("captcha", "h-captcha"),
    ]

    block_reason = next(
        (reason for reason, signal in block_signals if signal in html_lower),
        None,
    )
    if block_reason is None:
        return None

    # If listing URLs are already extracted from a listing page, treat content as usable.
    if listing_urls_found is not None and listing_urls_found > 0:
        return None

    return block_reason


def block_error_message(block_reason: str | None) -> str | None:
    if not block_reason:
        return None
    if block_reason == "cloudflare_turnstile":
        return "Blocked by Cloudflare Turnstile anti-bot protection"
    if block_reason == "cloudflare_challenge":
        return "Blocked by Cloudflare anti-bot protection"
    if block_reason == "captcha":
        return "Blocked by CAPTCHA anti-bot protection"
    return "Blocked by anti-bot protection"


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
