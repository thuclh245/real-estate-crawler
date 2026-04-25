# 07 - Snapshot and Deduplication Contract

## Purpose

Track listing lifecycle over daily snapshots.

## Main concepts

A listing can be:

```text
new
existing
changed price
changed content
removed/expired
technical duplicate
possible duplicate
```

## Snapshot key

Preferred:

```text
snapshot_date + source + listing_id
```

Fallback:

```text
normalized_url_hash
content_hash
```

## Dedup rules

### Rule 1 - Same listing_id in same day

```text
same source + same crawl_date + same listing_id
```

Keep best record by:

```text
crawl_status ok
quality_score highest
scraped_at latest
```

### Rule 2 - Same normalized URL

Mark:

```text
duplicate_flag = true
duplicate_reason = same_url
```

### Rule 3 - Similar content

Possible duplicate when:

```text
same title_normalized
same area_m2
same district
same price_value_vnd
```

Mark:

```text
possible_duplicate_flag = true
duplicate_reason = similar_content
```

## Lifecycle fields

```text
first_seen_at
last_seen_at
is_active
days_observed
is_new_listing
is_removed_listing
price_changed_flag
content_changed_flag
duplicate_flag
duplicate_reason
```

## Removed listing logic

A listing is considered removed if it was seen before but not seen in the last N snapshots.

Recommended:

```text
N = 2 or 3 daily crawls
```

## Acceptance tests

```text
[ ] Same listing_id duplicate is detected.
[ ] Same URL duplicate is detected.
[ ] first_seen_at and last_seen_at are computed.
[ ] is_new_listing is true on first snapshot only.
[ ] price_changed_flag is true when price differs from previous snapshot.
[ ] is_active is computable.
[ ] removed listing logic is documented and testable.
```
