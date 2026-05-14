# Silver Layer Improvements — Summary of Changes

**Date**: 2026-05-12  
**Schema version**: v1.1  
**Files changed**: 5 source files + 1 new config

---

## 1. `src/crawler/parsing/normalizers.py`

### Changed
- Added `from datetime import datetime` import

### Added (5 new functions)

| Function | Purpose |
|----------|---------|
| `normalize_posted_date(date_str)` | Parse `dd/mm/yyyy`, `dd-mm-yyyy`, `yyyy-mm-dd` → ISO 8601 |
| `extract_project_from_location(location_raw, breadcrumb_raw)` | Extract project/tower name from Batdongsan breadcrumb (`"...tại <Project>"`) and location |
| `normalize_floor_count(text)` | Extract floor count from patterns like `Số tầng 5`, `5 tầng`, `Tầng 16` |
| `normalize_direction(text)` | Normalize direction (Đông/Tây/Nam/Bắc + compounds) — returns `None` if unrecognized |
| `normalize_legal_status(text)` | Normalize legal status: `have_certificate`, `pending_certificate`, `contract_only`, `other` |
| `normalize_furniture(text)` | Normalize furniture: `full`, `basic`, `empty`, `other` |

---

## 2. `src/crawler/parsing/batdongsan_parser.py`

### Major rewrite — 13 functions changed/added

| Change | Detail |
|--------|--------|
| **`extract_title()`** | Now uses `metadata.get("title")` (BS4-extracted clean title) instead of heuristic from raw_text |
| **`extract_description()`** (new) | Returns clean description from metadata (`description` field from `.re__section-body`), falls back to extracting "Thông tin mô tả" section from raw_text. Max 2000 chars (was raw_text[:3000] full of boilerplate) |
| **`extract_price_raw()`** | Now prioritizes `listing_card_price_raw` from metadata |
| **`extract_area_raw()`** | Now prioritizes `listing_card_area_raw` from metadata |
| **`extract_location_raw()`** | Now prioritizes `detail_address_raw`/`detail_location_raw` from metadata |
| **`extract_section()`** (new) | Generic helper to extract a named section from Batdongsan raw text, bounded by end markers |
| **`extract_bedroom_count()`** | Now searches only within "Đặc điểm bất động sản" section (fixes false matches from navigation text). Added value range validation (1–50) |
| **`extract_bathroom_count()`** | Added `Số phòng tắm[,\s]*vệ sinh\s*(\d+)` pattern (the actual Batdongsan format). Added `Số phòng tắm\s*\n?\s*(\d+)`. Added value range validation |
| **`extract_floor_count()`** (new) | Extracts floor count from "Đặc điểm" section |
| **`extract_direction()`** (new) | Extracts house/balcony direction from "Đặc điểm" section (only `Hướng ban công`/`Hướng nhà`/`Hướng cửa chính`, not bare `Hướng`) |
| **`extract_legal_status()`** (new) | Extracts legal status from "Đặc điểm" section |
| **`extract_furniture_status()`** (new) | Extracts furniture status from "Đặc điểm" section |
| **`extract_posted_date_raw()`** | Added `Ngày đăng\s*\n?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})` regex |
| **`extract_expired_date_raw()`** (new) | Extracts `Ngày hết hạn` from raw_text |
| **`extract_listing_type()`** (new) | Extracts `Loại tin` (Tin VIP Bạc/Vàng, Tin thường) |
| **`extract_seller_info()`** (new) | Extracts broker flag and phone number from text |
| **`compute_dedup_key()`** (new) | Computes Silver-level dedup_key using same algorithm as `silver_to_gold.py:add_dedup_key()` (priority: listing_id → listing_url → content_hash) |
| **`parse_listing()`** | Now calls all new extractors; outputs 71 columns (was 57); includes `silver_schema_version`, `dedup_key`, `dedup_method`, `direction`, `legal_status`, `furniture_status`, `is_broker`, `phone_raw`, `listing_type`, `expired_date_raw`, `posted_date` (parsed ISO), `expired_date` (parsed ISO) |
| **`normalize_location_simple()`** | Now extracts ward_raw, street_raw from location; calls `extract_project_from_location()` for project_raw |

---

## 3. `src/crawler/parsing/quality_checks.py`

### Added 5 new quality flags

| Flag | Condition |
|------|-----------|
| `is_invalid_unit_price` | `unit_price_vnd_m2 <= 0` |
| `is_outlier_unit_price` | `unit_price_vnd_m2 < 5M` or `> 500M` (VND/m² for Hanoi) |
| `is_inconsistent_price_area` | `price_vnd / area_m2` yields unrealistic unit price |
| `is_suspicious_bedroom_count` | `bedroom > 8` in apartment, or `> 20` in any type |
| `is_description_too_short` | Cleaned description < 30 characters |

### Changed
- `parse_status` now uses 16 quality flags (was 8)

---

## 4. `src/transform/bronze_to_silver.py`

### Changed

| Change | Detail |
|--------|--------|
| **`SILVER_DTYPES`** (new dict) | Explicit dtypes for all 71 columns — prevents NaN-vs-null Parquet schema issues |
| **`cast_dataframe()`** (new) | Enforces consistent pandas dtypes: `Int64` for nullable ints, `boolean` for bools, `float64` for floats, string cleanup |
| **Summary output** | Added `silver_schema_version`, `bedroom_count_null_rate`, `bathroom_count_null_rate`, `floor_count_null_rate`, `posted_date_null_rate`, `project_raw_null_rate`, `dedup_method_*_count` |
| **Quality flag rates** | Now tracks all 13 quality flags (was 8) |

---

## 5. `src/transform/silver_to_gold.py`

### Changed
- **`build_gold_data_quality_daily()`**: Dynamically adds aggregation columns for new quality flags if present in silver data (`is_outlier_unit_price`, `is_invalid_unit_price`, `is_suspicious_bedroom_count`, `is_description_too_short`, `is_inconsistent_price_area`)
- **`write_phase3_summary()`**: Dynamically includes new quality rates in summary JSON

---

## 6. `configs/team/scale_test_1000.yaml`

New config for large-scale testing: 8 districts × 4 categories = 32 targets, `max_pages_per_target: 2`, `max_listings_per_target: 50`, `request_delay_seconds: 2`.

---

## Before → After Comparison (75-record test)

| Metric | Before (v1, 30 records) | After (v1.1, 75 records) |
|--------|------------------------|--------------------------|
| `bathroom_count` null | **100%** | **20%** |
| `floor_count` populated | **0%** (None) | **35%** |
| `posted_date` populated | **0%** (None) | **100%** |
| `expired_date` populated | **0%** (None) | **100%** |
| `project_raw` populated | **0%** (None) | **100%** |
| `phone_raw` populated | **0%** (None) | **100%** |
| `dedup_key` present | **No** | **Yes** (100%) |
| `direction` populated | **0%** | **51%** |
| `legal_status` populated | **0%** | **81%** |
| `furniture_status` populated | **0%** | **69%** |
| `listing_type` populated | **0%** | **100%** |
| `description_raw` quality | **3000 chars of boilerplate** | **Clean description** (mean ~500 chars) |
| Quality flags (total) | 8 | **13** |
| Columns (total) | 57 | **71** |
| NaN/null Parquet issue | **Present** (`nan` in float cols) | **Fixed** (proper nulls) |
