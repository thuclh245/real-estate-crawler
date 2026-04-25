# 03 - Agent Tasks for Phase 1 Crawler Implementation

Use this document as a step-by-step task list for a code agent.

## Task 1 - Harden `crawl_id`

### Problem

Current `crawl_id` may be fixed like:

```text
batdongsan_20260425_001
```

This causes ambiguity and overwrite risk for multiple runs on the same date.

### Required change

Create unique `crawl_id` per run:

```python
from datetime import datetime

crawl_id = f"batdongsan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
```

### Also update file names

```text
crawl_log_<crawl_id>.jsonl
crawl_summary_<crawl_id>.json
```

### Acceptance

Run crawler twice on same day. It must create two separate summary/log files.

---

## Task 2 - Clean `parser.py`

### Problem

`parser.py` should not contain duplicate `extract_basic_fields()` functions.

### Required Phase 1 version

Keep only:

```python
from bs4 import BeautifulSoup
import re


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_listing_id(url: str) -> str | None:
    match = re.search(r"pr(\d+)", url or "")
    return match.group(1) if match else None
```

### Acceptance

No duplicate function names. Phase 1 does not parse price/area/title officially.

---

## Task 3 - Ensure fetch adapter architecture

### Required interface

`src/fetcher.py` should expose:

```python
FetchResult
fetch_html(url: str, mode: str) -> FetchResult
```

`FetchResult` should include:

```text
status_code
html
markdown
success
error_message
fetch_mode
```

### Required modes

```text
requests
crawl4ai
```

### Acceptance

Changing `crawl_settings.fetch_mode` in YAML switches fetcher without changing crawler logic.

---

## Task 4 - Preserve block detection safely

### Required behavior

- HTTP 403/429 is blocked.
- CAPTCHA/challenge page is blocked.
- Cloudflare script alone is not enough if listing URLs were extracted successfully.

### Acceptance

If Craw4AI returns HTML containing listing URLs but also Cloudflare scripts, crawler must not mark it as blocked.

---

## Task 5 - Write per-listing metadata file

For each successful detail page, write:

```text
data/bronze/source=batdongsan/crawl_date=YYYY-MM-DD/metadata/listing_id=<id>.json
```

Metadata must include:

```text
fetch_mode
metadata_path
listing_business_type
property_type_group
raw_html_path
raw_text_path
crawl_category
crawl_city
crawl_district
crawl_id
```

### Acceptance

If `success_count = 15`, then `metadata_file_count = 15` for the current run.

---

## Task 6 - Count only current-run files

### Problem

Counting all files in `crawl_date` folder can accumulate previous runs.

### Required behavior

Maintain arrays during current run:

```python
current_run_raw_html_paths = []
current_run_metadata_paths = []
current_run_listing_urls = []
```

At summary time:

```text
raw_html_file_count = len(current_run_raw_html_paths)
metadata_file_count = len(current_run_metadata_paths)
duplicate_url_count = len(urls) - len(set(urls))
avg_html_size = average size of files written in current run
```

### Acceptance

Metrics reflect current run only, not cumulative daily folder.

---

## Task 7 - Scale test gradually

After all patches:

```text
Run 1: 15 listing
Run 2: 50-60 listing
Run 3: 100 listing
Run 4: 100-300 listing/day
```

Do not jump directly to thousands of listings.

### Acceptance

For test scale 50-100:

```text
success_count > 0
blocked_count low or 0
failed_count acceptable
raw_html_file_count == success_count
metadata_file_count == success_count
duplicate_url_count measured
```
