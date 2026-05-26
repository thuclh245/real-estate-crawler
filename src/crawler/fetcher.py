import asyncio
import random
import time
from urllib.parse import parse_qs, urlsplit

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
    # 1. Intercept cache for Nhatot detail pages to completely bypass detail network calls
    try:
        from crawler.sources.nhatot.adapter import IN_MEMORY_AD_CACHE
        if url in IN_MEMORY_AD_CACHE:
            return 200, IN_MEMORY_AD_CACHE[url], url, 0, None
    except ImportError:
        pass

    # 2. Intercept Nhatot web seed listing pages and translate them to API endpoints on the fly
    if "nhatot.com" in url and "detail-mock" not in url and ".htm" not in url:
        try:
            from crawler.sources.nhatot.adapter import DISTRICT_MAPPING, CATEGORY_MAPPING
            page = 1
            parsed = urlsplit(url)
            query_page = parse_qs(parsed.query).get("page", [None])[-1]
            if query_page:
                try:
                    page = int(query_page)
                except (TypeError, ValueError):
                    pass
            elif "/p" in parsed.path:
                try:
                    page = int(parsed.path.rsplit("/p", 1)[-1])
                except (TypeError, ValueError):
                    pass

            cg_id = 1000
            for cat, cid in CATEGORY_MAPPING.items():
                if cat in url:
                    cg_id = cid
                    break

            area_id = None
            for dist, aid in DISTRICT_MAPPING.items():
                if dist in url:
                    area_id = aid
                    break

            if area_id:
                transaction_query = "&st=s" if "mua-ban" in url else ""
                api_url = f"https://gateway.chotot.com/v1/public/ad-listing?cg={cg_id}&region=12&area={area_id}&page={page}&limit=20{transaction_query}"
                # Fetch API JSON, but return the original web URL as final_url for orchestrator compatibility
                status, html, _ = fetch_html(api_url, mode=mode)
                return status, html, url, 0, None
        except Exception as e:
            print(f"[fetcher] Error translating Nhatot web URL to API: {e}")
            pass

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
    
    # Inject high-performance mobile headers for Chotot/Nhatot gateway API compatibility
    if "chotot.com" in url or "nhatot.com" in url:
        headers["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Chotot/4.5.0"
        headers["X-Chotot-Platform"] = "IOS"
        headers["X-Chotot-Region"] = "VN"
        headers["Accept"] = "application/json, text/plain, */*"

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
