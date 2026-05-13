# Requirements Document

## Introduction

This document specifies requirements for a regex/rule-based feature extraction module that parses raw Vietnamese text from batdongsan.com.vn property listings to extract 16 structured attributes. The module normalizes Vietnamese text, applies property-type-aware logic, and outputs enriched structured data for each listing. It integrates into the existing Bronze-to-Silver transformation pipeline.

## Glossary

- **Feature_Extractor**: The module responsible for extracting structured attributes from raw listing text using regex patterns and rule-based logic
- **Text_Normalizer**: The utility component that normalizes Vietnamese text by removing accents, lowercasing, and handling special characters
- **Pattern_Registry**: The configuration component that stores all regex pattern definitions for each feature
- **Listing_Row**: A single property listing record containing raw text fields (title_raw, description_raw, location_raw, property_type_raw, project_raw) and existing structured fields
- **Search_Text**: The combined normalized text built from title + description + location + property_type + project fields for pattern matching
- **Property_Type_Group**: The classification of a listing into one of: house, apartment, villa_townhouse, land
- **Legal_Status**: Information about the legal documentation of a property (e.g., sổ đỏ, sổ hồng, hợp đồng mua bán)
- **Red_Book**: Vietnamese "sổ đỏ" — a land use rights certificate
- **Pink_Book**: Vietnamese "sổ hồng" — a house/apartment ownership certificate
- **Frontage_Width**: The width of the property face along the road (mặt tiền), measured in meters
- **Floor_Count**: The number of floors/stories in a building
- **Seller_Type**: Classification of the listing poster as either owner (chính chủ) or broker (môi giới)
- **Furniture_Level**: Classification of furniture status: full, basic, raw, or mentioned
- **Car_Access**: Whether the property has road access wide enough for cars (ô tô đỗ cửa, ô tô tránh)
- **Business_Suitability**: Whether the listing mentions suitability for business use (kinh doanh)
- **Location_Context_Flag**: Indicators of neighborhood quality such as KĐT (urban area), an ninh (security), dân trí (educated community)
- **Negotiable_Price**: Whether the listing indicates the price is negotiable (thương lượng, có thương lượng)
- **Building_Name**: The name of a specific building or tower within an apartment complex

## Requirements

### Requirement 1: Text Normalization

**User Story:** As a data engineer, I want to normalize Vietnamese text before pattern matching, so that regex patterns can match consistently regardless of accent variations and formatting differences.

#### Acceptance Criteria

1. WHEN raw Vietnamese text is provided, THE Text_Normalizer SHALL remove all Vietnamese diacritical marks (accents) using Unicode NFD decomposition and removal of combining marks (category Mn), and produce ASCII-equivalent output
2. WHEN raw Vietnamese text is provided, THE Text_Normalizer SHALL convert the Vietnamese letter đ/Đ to d
3. WHEN raw text is provided, THE Text_Normalizer SHALL convert all characters to lowercase
4. WHEN raw text contains multiple consecutive whitespace characters, THE Text_Normalizer SHALL collapse them into a single space and trim leading/trailing whitespace
5. WHEN raw text contains newline characters, THE Text_Normalizer SHALL replace them with a single space
6. WHEN raw text contains special Unicode symbols (m², m³), THE Text_Normalizer SHALL convert them to their ASCII equivalents (m2, m3)
7. IF the input text is null or empty, THEN THE Text_Normalizer SHALL return an empty string without raising an exception
8. THE Text_Normalizer SHALL preserve the original raw text in the Listing_Row so that project name extraction (Requirement 9) and building name extraction (Requirement 16) can operate on accented text
9. THE Text_Normalizer SHALL apply operations in the following order: lowercase, NFD decomposition and mark removal, đ→d conversion, symbol normalization, whitespace collapsing and trimming

### Requirement 2: Search Text Construction

**User Story:** As a data engineer, I want to build a combined search text from multiple listing fields, so that patterns can match across title, description, and metadata.

#### Acceptance Criteria

1. WHEN a Listing_Row is provided, THE Feature_Extractor SHALL concatenate title_raw, description_raw, location_raw, property_type_raw, and project_raw fields in that order, separated by a single space character, to form the Search_Text
2. IF any field in the Listing_Row is null, NaN, empty string, or contains only whitespace characters, THEN THE Feature_Extractor SHALL skip that field during concatenation without inserting extra separators
3. IF all five fields in the Listing_Row are null, NaN, empty, or whitespace-only, THEN THE Feature_Extractor SHALL produce an empty string as the Search_Text
4. WHEN the Search_Text is constructed, THE Text_Normalizer SHALL normalize the combined text before passing it to pattern-matching extractors
5. THE Feature_Extractor SHALL also retain a raw (non-normalized) version of the combined text for extractors that require accented Vietnamese text

### Requirement 3: Legal Status Extraction

**User Story:** As a data analyst, I want to extract legal documentation status from listings, so that I can assess the legal risk of properties.

#### Acceptance Criteria

1. WHEN the Search_Text contains any legal status keyword from the set (phap ly, so do, so hong, so rieng, so chung, da co so, hop dong mua ban, hdmb, giay to hop le, chua co so, vi bang, giay tay, cong chung, sang ten, quy hoach, tranh chap), THE Feature_Extractor SHALL set has_legal_info to true
2. WHEN the Search_Text contains legal status keywords, THE Feature_Extractor SHALL extract the first matching keyword phrase as the legal_status_raw value, limited to 100 characters
3. WHEN the Search_Text contains multiple distinct legal status keywords, THE Feature_Extractor SHALL extract the first match found in text order as legal_status_raw
4. WHEN the Search_Text contains "so do", "so hong", or "so rieng" patterns, THE Feature_Extractor SHALL set has_red_pink_book to true
5. IF the Search_Text does not contain any legal status keywords, THEN THE Feature_Extractor SHALL set has_legal_info to false, legal_status_raw to null, and has_red_pink_book to false

### Requirement 4: Floor Count Extraction

**User Story:** As a data analyst, I want to extract the number of floors from house and villa listings, so that I can analyze building characteristics.

#### Acceptance Criteria

1. WHEN the Search_Text contains floor count patterns ("so tang: X tang", "xay dung: X tang", "ket cau X tang", "nha X tang", "X tang", "X lau", "XT" abbreviation), THE Feature_Extractor SHALL extract the numeric floor count as an integer value
2. WHEN the Search_Text contains the compound format "A tret B lau", THE Feature_Extractor SHALL calculate the total floor count as 1 + B (where "tret" represents the ground floor counted as 1)
3. WHILE the Property_Type_Group is "apartment", THE Feature_Extractor SHALL skip floor count extraction and return null
4. WHEN a floor count is extracted, THE Feature_Extractor SHALL validate that the value is between 1 and 50 inclusive
5. IF the extracted floor count is outside the range 1 to 50, THEN THE Feature_Extractor SHALL discard the value and return null
6. WHEN multiple floor count patterns match within the same Search_Text, THE Feature_Extractor SHALL return the value from the first match in text order
7. IF the Search_Text does not contain any floor count patterns, THEN THE Feature_Extractor SHALL return null

### Requirement 5: Seller Type Extraction

**User Story:** As a data analyst, I want to identify whether a listing is posted by the owner or a broker, so that I can segment listings by seller type.

#### Acceptance Criteria

1. WHEN the Search_Text contains owner keywords (chinh chu, chu nha, chu can ban, chu gui, ban truc tiep, mien moi gioi, khong qua moi gioi, khong tiep mg), THE Feature_Extractor SHALL set seller_type to "owner"
2. WHEN the Search_Text contains broker keywords (moi gioi, mg, sale, nhan ky gui, van phong nha dat, cong ty bds), THE Feature_Extractor SHALL set seller_type to "broker"
3. WHEN the Search_Text contains a negation-prefixed broker keyword (khong tiep moi gioi, mien moi gioi, khong qua moi gioi), THE Feature_Extractor SHALL classify that match as an owner signal and SHALL NOT treat the embedded broker keyword as a broker match
4. IF the Search_Text contains both owner and broker keywords after negation-pattern resolution, THEN THE Feature_Extractor SHALL set seller_type to "owner" (owner takes priority)
5. IF the Search_Text does not contain any seller type keywords, THEN THE Feature_Extractor SHALL set seller_type to null
6. WHEN matching seller type keywords, THE Feature_Extractor SHALL match negation-prefixed patterns before individual broker keywords to prevent false broker classification

### Requirement 6: Furniture Level Extraction

**User Story:** As a data analyst, I want to classify the furniture status of listings, so that I can analyze property value relative to furnishing.

#### Acceptance Criteria

1. WHEN the Search_Text contains full furniture keywords (full noi that, full do, noi that day du, day du noi that, noi that cao cap, noi that dep, noi that xin, de lai toan bo noi that, du do vao o ngay), THE Feature_Extractor SHALL set furniture_level to "full"
2. WHEN the Search_Text contains basic furniture keywords (noi that co ban, do co ban, ban giao co ban), THE Feature_Extractor SHALL set furniture_level to "basic"
3. WHEN the Search_Text contains raw/unfurnished keywords (nha tho, ban giao tho, tho hoan thien, can tho, chua co noi that), THE Feature_Extractor SHALL set furniture_level to "raw"
4. WHEN the Search_Text contains finished handover keywords (ban giao hoan thien, hoan thien co ban) and does not match full or basic patterns, THE Feature_Extractor SHALL set furniture_level to "basic"
5. WHEN the Search_Text contains individual furniture item keywords (dieu hoa, nong lanh, tu bep, giuong, sofa, tivi, tu lanh, may giat, bep tu) or the generic term "noi that" without matching full, basic, or raw patterns, THE Feature_Extractor SHALL set furniture_level to "mentioned"
6. IF the Search_Text does not contain any furniture-related keywords from criteria 1 through 5, THEN THE Feature_Extractor SHALL set furniture_level to null
7. THE Feature_Extractor SHALL evaluate furniture patterns in priority order: full, basic, raw, mentioned — where a higher-priority match takes precedence regardless of position in text, and multi-word patterns SHALL be matched before single-word patterns to prevent substring conflicts (e.g., "chua co noi that" matches raw before "noi that" matches mentioned)

### Requirement 7: Frontage Width Extraction

**User Story:** As a data analyst, I want to extract the frontage width of properties, so that I can analyze road-facing dimensions.

#### Acceptance Criteria

1. WHEN the Search_Text contains frontage patterns ("mat tien X m", "mt Xm", "nong Xm", "chieu ngang Xm", "ngang Xm") or reverse frontage patterns ("Xm mat tien", "Xm ngang"), THE Feature_Extractor SHALL extract the numeric frontage width value in meters, where X may use a comma as decimal separator (e.g., "4,5" interpreted as 4.5)
2. WHILE the Property_Type_Group is "apartment", THE Feature_Extractor SHALL skip frontage extraction and return null
3. WHEN a frontage width is extracted, THE Feature_Extractor SHALL validate that the value is between 1.0 and 100.0 meters inclusive
4. IF the extracted frontage width is outside the range 1.0 to 100.0, THEN THE Feature_Extractor SHALL discard the value and return null
5. WHEN matching frontage patterns, THE Feature_Extractor SHALL only match "m" not followed by "2" or "²" to avoid matching area values (e.g., "50 m2" SHALL NOT be extracted as frontage)
6. IF the Search_Text contains multiple frontage pattern matches, THEN THE Feature_Extractor SHALL return the first matched value in text order

### Requirement 8: Bathroom Count Extraction

**User Story:** As a data analyst, I want to extract the number of bathrooms from listings, so that I can enrich the structured data beyond what the existing parser captures.

#### Acceptance Criteria

1. WHEN the Search_Text contains bathroom count patterns in number-first format ("X phong tam", "X wc", "X vs", "X ve sinh", "X nha ve sinh", "X toilet") or label-first format ("wc: X", "vs: X", "ve sinh: X", "so phong tam... X phong"), THE Feature_Extractor SHALL extract the integer bathroom count where X is a 1-to-2-digit integer
2. WHEN a bathroom count is extracted, THE Feature_Extractor SHALL validate that the value is between 1 and 20 inclusive
3. IF the extracted bathroom count is outside the range 1 to 20, THEN THE Feature_Extractor SHALL discard the value and return null
4. IF the Search_Text does not match any bathroom count pattern, THEN THE Feature_Extractor SHALL set bathroom_count to null
5. WHEN the Listing_Row already has a non-null bathroom_count from the existing parser, THE Feature_Extractor SHALL use the existing value and skip regex extraction

### Requirement 9: Project/Complex Name Extraction

**User Story:** As a data analyst, I want to extract the project or residential complex name from listings, so that I can group listings by development project.

#### Acceptance Criteria

1. WHEN the raw (accented) text contains project name patterns (e.g., "dự án X", "chung cư X", "khu đô thị X"), THE Feature_Extractor SHALL extract the project name string by capturing up to 10 consecutive words following the keyword, stopping at sentence-ending punctuation (period, comma, semicolon, newline, or dash)
2. THE Feature_Extractor SHALL run project name extraction on the raw accented text rather than the normalized text to preserve proper names and Vietnamese accents
3. WHEN a project name is extracted, THE Feature_Extractor SHALL trim leading/trailing whitespace and truncate the extracted name to a maximum of 100 characters, cutting at the last complete word within the limit
4. WHEN the Listing_Row already has a non-null project_raw field, THE Feature_Extractor SHALL prefer the existing value over the regex-extracted value
5. IF the raw text does not contain any project name patterns, THEN THE Feature_Extractor SHALL set project_name to null
6. WHEN the raw text contains a "tòa X" pattern, THE Feature_Extractor SHALL treat it as a building name (handled by Requirement 16) and NOT extract it as a project name

### Requirement 10: Bedroom Count Extraction

**User Story:** As a data analyst, I want to extract the number of bedrooms from listings, so that I can enrich the structured data.

#### Acceptance Criteria

1. WHEN the Search_Text contains bedroom count patterns ("X phong ngu", "X pn", "X ngu", "so phong ngu: X phong", or combo format "XN" followed by other room codes such as "2N1K", "3N2VS"), THE Feature_Extractor SHALL extract the numeric bedroom count
2. WHEN a bedroom count is extracted, THE Feature_Extractor SHALL validate that the value is between 1 and 30 inclusive
3. IF the extracted bedroom count is outside the range 1 to 30, THEN THE Feature_Extractor SHALL discard the value and return null
4. WHEN the Listing_Row already has a non-null bedroom_count from the existing parser, THE Feature_Extractor SHALL prefer the existing value over the regex-extracted value
5. IF the Search_Text contains multiple bedroom count matches with different values, THEN THE Feature_Extractor SHALL use the first match found in text order

### Requirement 11: Business Suitability Extraction

**User Story:** As a data analyst, I want to identify listings suitable for business use, so that I can filter commercial-potential properties.

#### Acceptance Criteria

1. WHEN the Search_Text contains any business suitability keyword from the canonical list (kinh doanh, kd, mat pho, mat duong, mat tien kinh doanh, vua o vua kinh doanh, buon ban, mo cua hang, mo van phong, cho thue kinh doanh, dong tien, shophouse, nha pho thuong mai, shop, spa, cafe, nha hang, mat bang, van phong), THE Feature_Extractor SHALL set is_business_suitable to true
2. IF the Search_Text does not contain any keyword from the canonical business suitability list, THEN THE Feature_Extractor SHALL set is_business_suitable to false
3. WHEN matching short keywords (kd, shop, spa, cafe), THE Feature_Extractor SHALL match on word boundaries only to prevent false positives from partial substring matches within unrelated words

### Requirement 12: Location Context Flags Extraction

**User Story:** As a data analyst, I want to identify neighborhood quality indicators from listings, so that I can assess location desirability.

#### Acceptance Criteria

1. WHEN the Search_Text contains urban area keywords (kdt, khu do thi, khu do thi moi, urban, city, residence, garden, park), THE Feature_Extractor SHALL set has_urban_area_flag to true
2. WHEN the Search_Text contains residential area keywords (khu dan cu, kdc, dan cu dong duc, dong dan cu, khu dan sinh), THE Feature_Extractor SHALL set has_residential_area_flag to true
3. WHEN the Search_Text contains security keywords (an ninh, an ninh tot, bao ve 24/7, camera, khu an ninh), THE Feature_Extractor SHALL set has_security_flag to true
4. WHEN the Search_Text contains high intellect community keywords (dan tri cao, hang xom van minh, cong dong van minh), THE Feature_Extractor SHALL set has_high_intellect_flag to true
5. WHEN high intellect community keywords match, THE Feature_Extractor SHALL also set has_educated_community_flag to true as a stable schema alias for the same educated-community signal
6. WHEN the Search_Text contains subdivision keywords (phan lo, khu phan lo, dat phan lo, biet thu phan lo), THE Feature_Extractor SHALL set has_subdivision_flag to true
7. IF the Search_Text does not contain any location context keywords from criteria 1 through 6, THEN THE Feature_Extractor SHALL set all six location context flags (has_urban_area_flag, has_residential_area_flag, has_security_flag, has_educated_community_flag, has_high_intellect_flag, has_subdivision_flag) to false

### Requirement 13: House Direction Extraction

**User Story:** As a data analyst, I want to extract the house/property direction (hướng), so that I can analyze feng shui preferences in the market.

#### Acceptance Criteria

1. WHEN the Search_Text contains a direction keyword preceded by a "huong" prefix pattern (matching "huong nha:", "nha huong", "dat huong", or "huong" followed by a direction value), THE Feature_Extractor SHALL extract the direction value
2. THE Feature_Extractor SHALL recognize the following direction values: dong, tay, nam, bac, dong nam, tay bac, dong bac, tay nam, and their abbreviations dn, db, tn, tb
3. THE Feature_Extractor SHALL normalize extracted directions to one of 8 standard values: dong, tay, nam, bac, dong_nam, tay_bac, dong_bac, tay_nam
4. THE Feature_Extractor SHALL require a "huong" prefix pattern before any direction value to avoid false positives from place names (e.g., "Ha Nam", "nam Tu Liem") or non-direction context (e.g., "phia nam")
5. IF the Search_Text contains multiple direction patterns, THEN THE Feature_Extractor SHALL extract the first matching direction in text order
6. IF the Search_Text does not contain any direction patterns with a valid "huong" prefix, THEN THE Feature_Extractor SHALL set direction to null

### Requirement 14: Negotiable Price Detection

**User Story:** As a data analyst, I want to detect when a listing indicates the price is negotiable, so that I can flag flexible-price listings.

#### Acceptance Criteria

1. WHEN the Search_Text contains any negotiable price keyword from the defined set (thuong luong, co thuong luong, gia thuong luong, thoa thuan, gia thoa thuan, co tl, tl manh, bot loc, gia chao, gia tot cho khach thien chi, khach thien chi co thuong luong), THE Feature_Extractor SHALL set is_price_negotiable to true
2. IF the Search_Text does not contain any negotiable price keyword from the defined set, THEN THE Feature_Extractor SHALL set is_price_negotiable to false
3. IF the Search_Text contains a negation modifier (khong, chua, khong co) immediately preceding a negotiable price keyword within 3 words, THEN THE Feature_Extractor SHALL NOT treat that occurrence as a positive match
4. WHEN the Bronze-to-Silver pipeline applies quality flags after feature extraction, THE quality flag logic SHALL preserve a true is_price_negotiable value produced by the Feature_Extractor and combine it with price_unit == "negotiable" using logical OR, so that regex-detected negotiable-price text is not overwritten.

### Requirement 15: Car Access Detection

**User Story:** As a data analyst, I want to detect whether a property has car access, so that I can filter properties by road accessibility.

#### Acceptance Criteria

1. WHEN the Search_Text contains any car access keyword from the following set: (o to vao, oto vao, xe hoi vao, o to do, oto do, cho de o to, bai do xe, gara, garage, o to tranh, oto tranh, o to ngu trong nha, oto ngu trong nha, duong o to, duong oto, ngo o to, ngo oto, hem xe hoi, o to do cua, oto do cua, oto vao nha, o to vao nha), THE Feature_Extractor SHALL set has_car_access to true
2. WHEN has_car_access is true, THE Feature_Extractor SHALL also set car_access_type to one of three sub-categories: "car_can_enter" if matched keyword is in (o to vao, oto vao, xe hoi vao, oto vao nha, o to vao nha), "car_can_park" if matched keyword is in (o to do, oto do, o to do cua, oto do cua, cho de o to, bai do xe, gara, garage, o to ngu trong nha, oto ngu trong nha), or "car_can_pass" if matched keyword is in (o to tranh, oto tranh, duong o to, duong oto, ngo o to, ngo oto, hem xe hoi)
3. WHILE the Property_Type_Group is "apartment", THE Feature_Extractor SHALL skip car access extraction and return null for both has_car_access and car_access_type
4. IF the Search_Text contains keywords from multiple sub-categories, THEN THE Feature_Extractor SHALL assign car_access_type based on the first matching keyword in text order
5. IF the Search_Text does not contain any car access keywords, THEN THE Feature_Extractor SHALL set has_car_access to false and car_access_type to null

### Requirement 16: Building/Tower Name Extraction

**User Story:** As a data analyst, I want to extract the building or tower name from apartment listings, so that I can identify specific buildings within complexes.

#### Acceptance Criteria

1. WHEN the raw (accented) text contains building name patterns matching any of the keywords "toa", "tòa", "toà", "thap", "tháp", "block", or "tower" (case-insensitive) followed by a name token, THE Feature_Extractor SHALL extract the name token immediately following the keyword as the building_name
2. THE Feature_Extractor SHALL run building name extraction on the raw accented text to preserve proper names with diacritical marks
3. THE Feature_Extractor SHALL capture the building name as a sequence of one or more alphanumeric characters, dots, dashes, and spaces up to the first delimiter that is not part of a name (comma, period followed by space, newline, or end of string), limited to a maximum of 50 characters after trimming leading/trailing whitespace
4. IF the raw text contains multiple building name pattern matches, THEN THE Feature_Extractor SHALL return the first match in text order
5. IF the raw text does not contain any building name patterns, THEN THE Feature_Extractor SHALL set building_name to null

### Requirement 17: Property-Type-Aware Extraction Orchestration

**User Story:** As a data engineer, I want the extraction pipeline to apply property-type-specific rules, so that irrelevant features are not extracted for certain property types.

#### Acceptance Criteria

1. WHILE the Property_Type_Group is "apartment", THE Feature_Extractor SHALL skip extraction of floor_count, frontage_width, and car_access
2. WHILE the Property_Type_Group is "land", THE Feature_Extractor SHALL skip extraction of floor_count and bedroom_count
3. THE Feature_Extractor SHALL return a dictionary containing all 16 feature keys for each Listing_Row, executing only the extractors not skipped by property type rules
4. WHEN an extractor is skipped due to property type rules, THE Feature_Extractor SHALL set the corresponding output field to null
5. IF the Property_Type_Group is null or not one of the defined values (house, apartment, villa_townhouse, land), THEN THE Feature_Extractor SHALL execute all 16 extractors without skipping
6. WHILE the Property_Type_Group is "house" or "villa_townhouse", THE Feature_Extractor SHALL execute all 16 extractors without skipping

### Requirement 18: Output Structure and Integration

**User Story:** As a data engineer, I want the extraction module to produce a well-defined output dictionary, so that it integrates cleanly into the Bronze-to-Silver pipeline.

#### Acceptance Criteria

1. THE Feature_Extractor SHALL return a dictionary containing exactly the 22 extracted feature keys (has_legal_info, legal_status_raw, has_red_pink_book, floor_count, seller_type, furniture_level, frontage_width, bathroom_count, project_name, bedroom_count, is_business_suitable, has_urban_area_flag, has_security_flag, has_educated_community_flag, has_high_intellect_flag, has_residential_area_flag, has_subdivision_flag, direction, is_price_negotiable, has_car_access, car_access_type, building_name), using null for features that were not detected or were skipped
2. WHEN the Feature_Extractor processes a Listing_Row, THE Feature_Extractor SHALL complete extraction within 50 milliseconds per listing on average, measured over a batch of at least 100 listings
3. IF any individual extractor raises an exception, THEN THE Feature_Extractor SHALL catch the exception, log a warning that includes the feature name and the exception message, set that feature to null, and continue processing remaining features
4. THE Feature_Extractor SHALL expose a single entry-point function that accepts a Listing_Row dictionary and returns a dictionary containing only the extracted feature keys without merging input fields
5. IF the input Listing_Row is null or contains none of the expected text fields (title_raw, description_raw, location_raw, property_type_raw, project_raw), THEN THE Feature_Extractor SHALL return the output dictionary with all feature values set to null
6. THE Feature_Extractor SHALL define a module-level FEATURE_OUTPUT_KEYS constant containing the ordered list of the 22 output keys, and extract_features SHALL build its result from that constant to keep the Silver schema stable across empty input, skipped extractors, and extractor failures.

### Requirement 19: Module Structure

**User Story:** As a data engineer, I want the extraction code organized into clear modules, so that patterns and logic are maintainable and testable independently.

#### Acceptance Criteria

1. THE Feature_Extractor SHALL organize code into three files: feature_text_utils.py for normalization utilities, feature_patterns.py for regex pattern definitions, and feature_extractors.py for extraction logic
2. THE Feature_Extractor SHALL place all module files under the existing src/crawler/parsing/ package to match the repository's current parser layout and import style, with __init__.py exporting the public API (extract_features entry-point function, normalize_text, FEATURE_PATTERNS, and FEATURE_OUTPUT_KEYS)
3. THE Pattern_Registry SHALL define all regex patterns as pre-compiled module-level constants or as entries in a FEATURE_PATTERNS dictionary within feature_patterns.py, and extraction functions in feature_extractors.py SHALL NOT define inline regex patterns
4. THE Feature_Extractor SHALL implement each feature extractor as a standalone function that accepts a string input (Search_Text or raw text) and returns the extracted value (typed scalar or null), enabling individual extractors to be imported and tested in isolation without instantiating the full pipeline
5. WHEN the crawler.parsing package is imported, THE Feature_Extractor SHALL make individual extract_* functions importable directly from feature_extractors.py so that test modules can call any single extractor with sample Vietnamese text and assert the expected output
