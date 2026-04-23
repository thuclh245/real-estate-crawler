import asyncio
import random

from crawler_extractors import extract_listing_links, listing_page_url, parse_detail


async def collect_listing_links(
    crawler, start_url: str, max_pages: int, max_items: int, page_delay_min: float, page_delay_max: float
) -> list[str]:
    """Scan listing pages and collect unique detail URLs up to max_items."""
    collected = []
    seen = set()

    for page in range(1, max_pages + 1):
        if max_items and len(collected) >= max_items:
            break

        page_url = listing_page_url(start_url, page)
        result = await crawler.arun(url=page_url)
        if not getattr(result, "success", False):
            print(f"[PAGE {page}] FAIL {page_url}")
            continue

        links = extract_listing_links(getattr(result, "html", ""))
        new_links = [x for x in links if x not in seen]

        for link in new_links:
            seen.add(link)
            collected.append(link)
            if max_items and len(collected) >= max_items:
                break

        print(f"[PAGE {page}] found={len(links)} new={len(new_links)} total={len(collected)}")

        if not new_links:
            print(f"[PAGE {page}] no new listing links, stopping pagination.")
            break

        await asyncio.sleep(random.uniform(page_delay_min, page_delay_max))

    return collected


async def fetch_details(crawler, links: list[str], detail_delay_min: float, detail_delay_max: float) -> list[dict]:
    """Crawl detail pages and parse extracted fields for each successful URL."""
    rows = []

    for idx, link in enumerate(links, 1):
        result = await crawler.arun(url=link)
        if not getattr(result, "success", False):
            print(f"[{idx}/{len(links)}] FAIL {link}")
            continue

        rows.append(parse_detail(getattr(result, "html", ""), link))
        print(f"[{idx}/{len(links)}] OK   {link}")
        await asyncio.sleep(random.uniform(detail_delay_min, detail_delay_max))

    return rows


async def fetch_details_incremental(
    crawler,
    links: list[str],
    detail_delay_min: float,
    detail_delay_max: float,
    on_batch,
    save_every: int = 1,
) -> tuple[int, int]:
    """Crawl details and persist successful rows incrementally using on_batch callback."""
    success_count = 0
    fail_count = 0
    batch = []

    for idx, link in enumerate(links, 1):
        result = await crawler.arun(url=link)
        if not getattr(result, "success", False):
            fail_count += 1
            print(f"[{idx}/{len(links)}] FAIL {link}")
            continue

        row = parse_detail(getattr(result, "html", ""), link)
        batch.append(row)
        success_count += 1
        print(f"[{idx}/{len(links)}] OK   {link}")

        if len(batch) >= max(1, save_every):
            on_batch(batch)
            batch = []

        await asyncio.sleep(random.uniform(detail_delay_min, detail_delay_max))

    if batch:
        on_batch(batch)

    return success_count, fail_count
