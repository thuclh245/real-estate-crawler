import asyncio
import random
import time

import requests


REQUEST_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def is_retryable_http_status(http_status: int | None) -> bool:
    return http_status in {0, 403, 408, 425, 429, 500, 502, 503, 504}


def retry_sleep_seconds(base_delay_seconds: float, attempt: int) -> float:
    delay = max(float(base_delay_seconds), 0)
    if delay == 0:
        return 0
    jitter = random.uniform(0, min(delay * 0.25, 10))
    return delay * (attempt + 1) + jitter


def fetch_with_retry(
    url: str,
    mode: str,
    max_retries: int,
    retry_delay_seconds: float,
) -> tuple[int | None, str, str | None, int, str | None]:
    last_status = None
    last_html = ""
    last_final_url = url
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            status, html, final_url = fetch_html(url, mode=mode)
            if is_retryable_http_status(status) and attempt < max_retries:
                last_status = status
                last_html = html or ""
                last_final_url = final_url or url
                last_error = f"HTTP {status}"
                time.sleep(retry_sleep_seconds(retry_delay_seconds, attempt))
                continue
            return status, html or "", final_url or url, attempt, None
        except Exception as exc:
            last_error = str(exc)
            if attempt < max_retries:
                time.sleep(retry_sleep_seconds(retry_delay_seconds, attempt))
                continue
            return last_status, last_html, last_final_url, attempt, last_error

    return last_status, last_html, last_final_url, max_retries, last_error


def fetch_html_requests(url: str) -> tuple[int, str, str]:
    headers = {
        "User-Agent": random.choice(REQUEST_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }
    response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    return response.status_code, response.text, response.url


async def fetch_html_crawl4ai_async(url: str) -> tuple[int, str, str]:
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as exc:
        raise RuntimeError("crawl4ai is not installed in current environment") from exc

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)

    html = (
        getattr(result, "html", None)
        or getattr(result, "cleaned_html", None)
        or getattr(result, "markdown", None)
        or ""
    )
    status_code = getattr(result, "status_code", None)
    if status_code is None:
        status_code = 200 if html else 0

    final_url = (
        getattr(result, "url", None)
        or getattr(result, "final_url", None)
        or getattr(result, "response_url", None)
        or url
    )

    return int(status_code), html, final_url


def fetch_html_crawl4ai(url: str) -> tuple[int, str, str]:
    return asyncio.run(fetch_html_crawl4ai_async(url))


def fetch_html(url: str, mode: str = "requests") -> tuple[int, str, str]:
    mode = (mode or "requests").lower().strip()

    if mode == "requests":
        return fetch_html_requests(url)
    if mode == "crawl4ai":
        return fetch_html_crawl4ai(url)

    raise ValueError(f"Unsupported fetch mode: {mode}")
