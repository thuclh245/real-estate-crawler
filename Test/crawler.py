# import argparse
# import asyncio
# from pathlib import Path

# try:
#     from crawl4ai import AsyncWebCrawler
# except ImportError:  # pragma: no cover
#     AsyncWebCrawler = None

# from crawler_runner import collect_listing_links, fetch_details_incremental
# from crawler_settings import DEFAULT_CONFIG_PATH
# from crawler_storage import append_rows, load_config, load_existing_links


# def _resolve_runtime_options(args, config):
#     """Resolve runtime options from CLI first, then config values."""
#     start_url = args.start_url or config.get("start_url")
#     if not start_url:
#         raise ValueError(
#             "Missing start_url. Set it in crawler_config.json or pass --start-url."
#         )

#     max_pages = args.max_pages if args.max_pages is not None else int(config.get("max_pages", 50))
#     max_items = args.max_items if args.max_items is not None else int(config.get("max_items", 1000))
#     page_delay_min = (
#         args.page_delay_min
#         if args.page_delay_min is not None
#         else float(config.get("page_delay_min", 1.0))
#     )
#     page_delay_max = (
#         args.page_delay_max
#         if args.page_delay_max is not None
#         else float(config.get("page_delay_max", 2.0))
#     )
#     detail_delay_min = (
#         args.detail_delay_min
#         if args.detail_delay_min is not None
#         else float(config.get("detail_delay_min", 0.6))
#     )
#     detail_delay_max = (
#         args.detail_delay_max
#         if args.detail_delay_max is not None
#         else float(config.get("detail_delay_max", 1.4))
#     )
#     save_every = args.save_every if args.save_every is not None else int(config.get("save_every", 1))

#     return {
#         "start_url": start_url,
#         "max_pages": max_pages,
#         "max_items": max_items,
#         "page_delay_min": page_delay_min,
#         "page_delay_max": page_delay_max,
#         "detail_delay_min": detail_delay_min,
#         "detail_delay_max": detail_delay_max,
#         "save_every": max(1, save_every),
#     }


# async def main(args):
#     """Run crawler pipeline: collect links, crawl details, and append rows."""
#     if AsyncWebCrawler is None:
#         raise RuntimeError(
#             "crawl4ai is not installed. Install it before running this script."
#         )

#     config_path = Path(args.config)
#     config = load_config(config_path)
#     options = _resolve_runtime_options(args, config)

#     output_file = Path(args.output)
#     existing_links = load_existing_links(output_file) if args.resume else set()

#     print(f"Resume mode={args.resume}. Existing links in file={len(existing_links)}")
#     print(f"Using start URL: {options['start_url']}")

#     async with AsyncWebCrawler() as crawler:
#         links = await collect_listing_links(
#             crawler=crawler,
#             start_url=options["start_url"],
#             max_pages=options["max_pages"],
#             max_items=options["max_items"],
#             page_delay_min=options["page_delay_min"],
#             page_delay_max=options["page_delay_max"],
#         )

#         links = [x for x in links if x not in existing_links]
#         if not links:
#             print("No new links to crawl.")
#             return

#         print(f"Crawling {len(links)} detail pages...")
#         success_count, fail_count = await fetch_details_incremental(
#             crawler=crawler,
#             links=links,
#             detail_delay_min=options["detail_delay_min"],
#             detail_delay_max=options["detail_delay_max"],
#             on_batch=lambda batch: append_rows(batch, output_file),
#             save_every=options["save_every"],
#         )
#         print(
#             f"Done. Saved {success_count} rows incrementally, failed {fail_count} -> {output_file}"
#         )


# if __name__ == "__main__":
#     """CLI entrypoint for batdongsan crawler."""
#     parser = argparse.ArgumentParser(
#         description="Crawl batdongsan.com.vn listings with pagination and resume support."
#     )
#     parser.add_argument(
#         "--config",
#         type=str,
#         default=str(DEFAULT_CONFIG_PATH),
#         help="Path to JSON config file containing start_url.",
#     )
#     parser.add_argument(
#         "--start-url",
#         type=str,
#         default=None,
#         help="Listing URL root (e.g., nha-dat-ban-ha-noi, nha-dat-ban-da-nang, nha-dat-ban).",
#     )
#     parser.add_argument(
#         "--max-pages",
#         type=int,
#         default=None,
#         help="Maximum listing pages to scan. Increase gradually for large runs.",
#     )
#     parser.add_argument(
#         "--max-items",
#         type=int,
#         default=None,
#         help="Maximum detail listings to crawl in this run.",
#     )
#     parser.add_argument(
#         "--output",
#         type=str,
#         default=str(Path(__file__).resolve().parent / "output" / "listings_crawl4ai.csv"),
#         help="Output CSV path.",
#     )
#     parser.add_argument(
#         "--resume",
#         action="store_true",
#         help="Skip listing URLs already existing in output file.",
#     )
#     parser.add_argument("--page-delay-min", type=float, default=None)
#     parser.add_argument("--page-delay-max", type=float, default=None)
#     parser.add_argument("--detail-delay-min", type=float, default=None)
#     parser.add_argument("--detail-delay-max", type=float, default=None)
#     parser.add_argument(
#         "--save-every",
#         type=int,
#         default=None,
#         help="Persist rows every N successful detail pages (default from config or 1).",
#     )
#     cli_args = parser.parse_args()

#     asyncio.run(main(cli_args))
