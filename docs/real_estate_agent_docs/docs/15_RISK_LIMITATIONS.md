# 15 - Risks and Limitations

## Main risks

### Website changes structure

Impact:

```text
parser breaks
crawler misses fields
HTML layout changes
```

Mitigation:

```text
store raw HTML in Bronze
separate ingestion from parser
track parser_version
log parse errors
```

### Anti-bot / access restrictions

Impact:

```text
HTTP 403/429
blocked pages
reduced live crawl volume
```

Mitigation:

```text
fetch_mode crawl4ai where appropriate
rate limiting
low concurrency
stop_on_block
no bypass attempts
offline raw ingestion if needed
```

### Missing and noisy data

Impact:

```text
analytics unstable
ML unreliable
```

Mitigation:

```text
quality flags
missing rates
is_valid_for_* columns
only use clean subset for price analytics and ML
```

### Location not exact

Impact:

```text
cannot guarantee exact house address or GPS
```

Mitigation:

```text
normalize only city/district/ward/street/project
store location_confidence
use crawl_context fallback
state limitation clearly in report
```

### Scope too wide

Impact:

```text
project unfinished
```

Mitigation:

```text
Hanoi main analysis
Vietnam as scale test
ML optional
rent data optional later
```

## Report limitations section

Use this wording:

```text
The project analyzes real estate listing data, not actual transaction data. Listing information may be incomplete or noisy because sellers may hide exact addresses, prices may be negotiable, and descriptions are user-generated. Therefore, the system does not claim exact property-level geolocation or production-grade valuation accuracy. The project focuses on building a reproducible data lakehouse pipeline with data quality monitoring and market analytics.
```
