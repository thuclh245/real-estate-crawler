# Implementation Plan: Feature Extraction Regex

## Overview

Implement a regex/rule-based feature extraction module under the existing `src/crawler/parsing/` package that extracts 16 structured attribute groups into 22 stable Silver columns from Vietnamese real estate listing text. The module integrates into the Bronze-to-Silver pipeline between `parse_listing()` and `apply_quality_flags()`. Implementation proceeds bottom-up: text utilities first, then pattern definitions, then individual extractors, then the orchestrator, and finally pipeline integration.

## Tasks

- [ ] 1. Set up module structure and text utilities
  - [ ] 1.1 Add feature extraction files under `src/crawler/parsing/` and implement `feature_text_utils.py`
    - Reuse the existing `src/crawler/parsing/__init__.py` package rather than creating a new top-level `src/parsing/` package
    - Implement `normalize_text()` in `src/crawler/parsing/feature_text_utils.py`: lowercase → NFD decomposition + remove combining marks → đ/Đ→d → symbol normalization (m²→m2, m³→m3) → whitespace collapse/trim
    - Implement `build_search_text()` in `src/crawler/parsing/feature_text_utils.py`: concatenate title_raw, description_raw, location_raw, property_type_raw, project_raw; skip null/NaN/empty/whitespace fields; return (normalized, raw) tuple
    - Handle edge cases: None input returns "", NaN from pandas treated as null
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 1.2 Write property tests for text normalization
    - **Property 1: Text normalization produces valid ASCII output**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    - Use Hypothesis to generate arbitrary Vietnamese text strings
    - Assert output has no combining marks, no đ/Đ, all lowercase, no consecutive whitespace, no leading/trailing whitespace, no newlines

  - [ ]* 1.3 Write property tests for search text construction
    - **Property 2: Search text construction preserves content and normalization relationship**
    - **Validates: Requirements 2.1, 2.2, 2.4, 2.5, 1.8**
    - Use Hypothesis to generate Listing_Row dicts with random null/non-null fields
    - Assert normalized == normalize_text(raw), non-null fields appear in raw, no double-space separators

  - [ ]* 1.4 Write unit tests for text utilities
    - Create `tests/test_text_utils.py`
    - Test specific Vietnamese normalization cases: m²→m2, Đ→d, "Hà Nội"→"ha noi"
    - Test None/empty/whitespace inputs
    - Test build_search_text with various null field combinations
    - _Requirements: 1.1–1.9, 2.1–2.5_

- [ ] 2. Implement pattern registry
  - [ ] 2.1 Create `src/crawler/parsing/feature_patterns.py` with all pre-compiled regex patterns
    - Define `FEATURE_PATTERNS` dictionary with pattern groups for all 16 features
    - Legal status patterns: keywords list, red/pink book subset
    - Floor count patterns: standard formats, "tret lau" compound format
    - Seller type patterns: negation-prefixed, owner keywords, broker keywords
    - Furniture level patterns: full, basic, raw, mentioned (multi-word before single-word)
    - Frontage width patterns: "mat tien Xm", "mt Xm", "nong Xm", reverse formats; exclude m2/m²
    - Bathroom count patterns: number-first and label-first formats
    - Project name patterns: "du an X", "chung cu X", "khu do thi X" (for raw accented text)
    - Bedroom count patterns: "X phong ngu", "X pn", combo "XN" format
    - Business suitability patterns: word-boundary matching for short keywords (kd, shop, spa, cafe)
    - Location context patterns: urban area, residential area, security, high intellect, subdivision
    - Direction patterns: "huong" prefix required before direction values
    - Negotiable price patterns: keywords with negation check (within 3 words)
    - Car access patterns: grouped by sub-category (enter, park, pass)
    - Building name patterns: "toa/tòa/toà/thap/tháp/block/tower" followed by name token (raw text)
    - All patterns pre-compiled as module-level constants using `re.compile()`
    - _Requirements: 3.1, 4.1, 5.1, 5.2, 6.1–6.5, 7.1, 8.1, 9.1, 10.1, 11.1, 11.3, 12.1–12.5, 13.1–13.2, 14.1, 15.1–15.2, 16.1, 19.3_

  - [ ]* 2.2 Write smoke tests for pattern compilation and matching
    - Create `tests/test_feature_patterns.py`
    - Verify all patterns compile without error
    - Test each pattern group matches at least one expected keyword
    - Test word-boundary patterns don't match substrings
    - _Requirements: 19.3_

- [ ] 3. Implement individual feature extractors
  - [ ] 3.1 Implement `extract_legal_status()` in `src/crawler/parsing/feature_extractors.py`
    - Return dict with has_legal_info, legal_status_raw (max 100 chars), has_red_pink_book
    - Match first keyword in text order for legal_status_raw
    - Set has_red_pink_book=True for "so do", "so hong", "so rieng"
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 3.2 Write property tests for legal status extraction
    - **Property 3: Legal keyword detection consistency**
    - **Property 4: Red/pink book detection is a subset of legal detection**
    - **Validates: Requirements 3.1, 3.2, 3.4, 3.5**

  - [ ] 3.3 Implement `extract_floor_count()` in `src/crawler/parsing/feature_extractors.py`
    - Handle standard patterns and "A tret B lau" compound format (1 + B)
    - Validate range [1, 50], return None if outside
    - Return first match in text order
    - _Requirements: 4.1, 4.2, 4.4, 4.5, 4.6, 4.7_

  - [ ] 3.4 Implement `extract_seller_type()` in `src/crawler/parsing/feature_extractors.py`
    - Match negation-prefixed patterns first to prevent false broker classification
    - Priority: negation→owner, owner keywords→"owner", broker keywords→"broker", else None
    - Owner takes priority if both found after negation resolution
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 3.5 Implement `extract_furniture_level()` in `src/crawler/parsing/feature_extractors.py`
    - Evaluate in priority order: full > basic > raw > mentioned > None
    - Multi-word patterns matched before single-word to prevent substring conflicts
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ] 3.6 Implement `extract_frontage_width()` in `src/crawler/parsing/feature_extractors.py`
    - Handle comma as decimal separator (4,5 → 4.5)
    - Exclude matches where "m" is followed by "2" or "²"
    - Validate range [1.0, 100.0], return first match
    - _Requirements: 7.1, 7.3, 7.4, 7.5, 7.6_

  - [ ] 3.7 Implement `extract_bathroom_count()` and `extract_bedroom_count()` in `src/crawler/parsing/feature_extractors.py`
    - Bathroom: number-first and label-first formats, validate [1, 20]
    - Bedroom: standard patterns and combo "XN" format, validate [1, 30]
    - Both respect existing non-null values from Listing_Row
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 3.8 Write property tests for numeric extraction range validation
    - **Property 5: Numeric extraction respects validation ranges**
    - **Validates: Requirements 4.4, 4.5, 7.3, 7.4, 8.2, 8.3, 10.2, 10.3**
    - Generate random numbers in and outside valid ranges, verify correct acceptance/rejection

  - [ ]* 3.9 Write property tests for seller type and furniture level
    - **Property 6: Seller type priority and negation handling**
    - **Property 7: Furniture level priority ordering**
    - **Validates: Requirements 5.1–5.5, 6.1–6.5, 6.7**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement remaining extractors
  - [ ] 5.1 Implement `extract_project_name()` in `src/crawler/parsing/feature_extractors.py`
    - Operate on raw accented text, not normalized
    - Capture up to 10 words after keyword, stop at punctuation
    - Truncate to 100 chars at last complete word
    - Prefer existing project_raw if non-null
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ] 5.2 Implement `extract_business_suitability()` in `src/crawler/parsing/feature_extractors.py`
    - Match keywords from canonical list
    - Use word-boundary matching for short keywords (kd, shop, spa, cafe)
    - Return True/False
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ] 5.3 Implement `extract_location_context()` in `src/crawler/parsing/feature_extractors.py`
    - Return dict with 6 boolean flags: urban_area, residential_area, security, educated_community, high_intellect, subdivision
    - Set `has_educated_community_flag` as a schema-compatible alias for the high-intellect/educated-community signal
    - Match keyword sets for each flag independently
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [ ] 5.4 Implement `extract_direction()` in `src/crawler/parsing/feature_extractors.py`
    - Require "huong" prefix before direction value
    - Normalize to 8 standard values: dong, tay, nam, bac, dong_nam, tay_bac, dong_bac, tay_nam
    - Return first match, None if no valid prefix+direction found
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [ ] 5.5 Implement `extract_negotiable_price()` in `src/crawler/parsing/feature_extractors.py`
    - Match negotiable keywords
    - Check for negation modifiers within 3 preceding words
    - Return False if negated, True if keyword found without negation
    - _Requirements: 14.1, 14.2, 14.3_

  - [ ] 5.6 Implement `extract_car_access()` in `src/crawler/parsing/feature_extractors.py`
    - Return dict with has_car_access (bool) and car_access_type (enter/park/pass/None)
    - Categorize by keyword sub-group, first match determines type
    - _Requirements: 15.1, 15.2, 15.4, 15.5_

  - [ ] 5.7 Implement `extract_building_name()` in `src/crawler/parsing/feature_extractors.py`
    - Operate on raw accented text
    - Match "toa/tòa/toà/thap/tháp/block/tower" + name token
    - Capture up to 50 chars, trim whitespace, first match
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [ ]* 5.8 Write property tests for remaining extractors
    - **Property 8: Frontage extraction does not match area values**
    - **Property 12: Business keyword word-boundary matching**
    - **Property 13: Direction extraction requires "huong" prefix**
    - **Property 14: Negotiable price negation handling**
    - **Property 15: Car access type categorization consistency**
    - **Property 17: "Tret B lau" floor count calculation**
    - **Validates: Requirements 7.5, 11.3, 13.1, 13.4, 14.1–14.3, 15.1–15.2, 4.2**

- [ ] 6. Implement orchestrator and pipeline integration
  - [ ] 6.1 Implement `FEATURE_OUTPUT_KEYS` and `extract_features()` orchestrator in `src/crawler/parsing/feature_extractors.py`
    - Define ordered `FEATURE_OUTPUT_KEYS` with exactly the 22 output keys from Requirement 18
    - Initialize result dictionaries from `FEATURE_OUTPUT_KEYS` so skipped, empty, and failed extractors still return a stable schema
    - Build search text (normalized + raw) from listing_row
    - Determine property_type_group, build skip set from PROPERTY_TYPE_SKIP_MAP
    - Loop through extractors, skip per property type rules
    - Wrap each extractor call in try/except, log warnings via `src/common/logger.py`
    - Return complete 22-key dictionary with null for skipped/failed features
    - Handle null/empty input: return all-null dictionary
    - Pass existing bedroom_count/bathroom_count/project_raw to relevant extractors
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 18.1, 18.3, 18.4, 18.5_

  - [ ] 6.2 Update `src/crawler/parsing/__init__.py` with final public API exports
    - Export: extract_features, normalize_text, FEATURE_PATTERNS, FEATURE_OUTPUT_KEYS
    - Ensure individual extract_* functions importable from feature_extractors.py
    - _Requirements: 19.2, 19.4, 19.5_

  - [ ]* 6.3 Write property tests for orchestrator
    - **Property 9: Property-type-aware skip rules**
    - **Property 10: Existing value preservation**
    - **Property 11: Output dictionary structure invariant**
    - **Property 16: Fault isolation — extractor exceptions do not crash pipeline**
    - **Validates: Requirements 4.3, 7.2, 15.3, 17.1–17.5, 8.5, 9.4, 10.4, 18.1, 18.3, 18.5**
    - Create `tests/test_orchestrator.py`

  - [ ]* 6.4 Write unit tests for individual extractors
    - Create `tests/test_feature_extractors.py`
    - Test each extractor with specific Vietnamese text examples
    - Test edge cases: empty string, no match, multiple matches
    - Test keyword variants for each feature
    - _Requirements: 3.1–18.5_

- [ ] 7. Integrate with Bronze-to-Silver pipeline
  - [ ] 7.1 Modify `src/transform/bronze_to_silver.py` to call `extract_features()`
    - Import `extract_features` from `crawler.parsing`
    - After `record = parse_listing(...)`, call `features = extract_features(record)`
    - Merge features into record: `record.update(features)`
    - Then pass to `apply_quality_flags(record)`
    - Update `src/crawler/parsing/quality_checks.py` so `is_price_negotiable` is OR-combined from `price_unit == "negotiable"` and the existing regex-derived `record["is_price_negotiable"]`, preventing quality flags from overwriting extractor output
    - _Requirements: 14.4, 18.4_

  - [ ]* 7.2 Write integration tests
    - Create `tests/test_integration.py`
    - Test end-to-end: mock listing → parse_listing → extract_features → verify enriched output
    - Verify all 22 feature keys present in output
    - Test performance: 100+ listings average < 50ms each
    - _Requirements: 18.2, 18.4_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The module uses Python's `re` module with pre-compiled patterns for performance
- All extractors are pure functions testable in isolation
- Use `hypothesis` library for property-based testing

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "2.2"] },
    { "id": 2, "tasks": ["3.1", "3.3", "3.4", "3.5", "3.6", "3.7"] },
    { "id": 3, "tasks": ["3.2", "3.8", "3.9", "5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7"] },
    { "id": 4, "tasks": ["5.8", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4"] },
    { "id": 6, "tasks": ["7.1"] },
    { "id": 7, "tasks": ["7.2"] }
  ]
}
```
