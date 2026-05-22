# Silver Schema

Silver stores parsed, normalized, and enriched listing records. It is partitioned by source, crawl date, and crawl id:

```text
data/silver/source=batdongsan/crawl_date=YYYY-MM-DD/crawl_id=batdongsan_YYYYMMDD_HHMMSS/
```

## Core Fields

| Field | Type | Source | Description | Example |
|---|---|---|---|---|
| listing_id | string | Bronze metadata | Source listing id | 30821374 |
| listing_url | string | Bronze metadata | Listing detail URL | https://batdongsan.com.vn/... |
| title_raw | string | Bronze text/metadata | Raw listing title | Quỹ căn độc quyền... |
| description_raw | string | Bronze text | Raw listing description | Thông tin mô tả... |
| price_raw | string | Bronze text/metadata | Price text | 7 tỷ |
| area_raw | string | Bronze text/metadata | Area text | 103 m² |
| location_raw | string | Bronze metadata | Raw address | Phường Cầu Giấy, Hà Nội |
| price_vnd | float | derived | Price normalized to VND | 7000000000 |
| area_m2 | float | derived | Area normalized to square meters | 103 |
| unit_price_vnd_m2 | float | derived | price_vnd / area_m2 | 67961165 |
| property_type_group | string | derived | Normalized property group | apartment |
| listing_business_type | string | derived | sale/rent grouping | sale |
| city_norm | string | derived | Normalized city | Hà Nội |
| district_norm | string | derived | Normalized district | Cầu Giấy |
| parse_status | string | parser | Parser status | success |
| parser_version | string | parser | Parser contract version | phase2_v1 |

## Enrichment Fields

| Field | Type | Source | Description | Example |
|---|---|---|---|---|
| has_legal_info | boolean | regex enrichment | Any legal status text found | true |
| legal_status_raw | string | regex enrichment | Raw legal status phrase | Sổ đỏ/Sổ hồng |
| has_red_pink_book | boolean | regex enrichment | Red/pink book signal | true |
| furniture_level | string | regex enrichment | Furniture completeness | full |
| frontage_width | float | regex enrichment | Frontage width in meters | 5.0 |
| project_name | string | regex enrichment/parser | Project/building text when available | Roman Plaza |
| is_business_suitable | boolean | regex enrichment | Business suitability signal | true |
| has_car_access | boolean | regex enrichment | Car access signal | true |
| car_access_type | string | regex enrichment | Car access category | oto_vao_nha |
| building_name | string | regex enrichment | Building/tower name | The Pride |
| direction | string | regex enrichment | House/balcony direction | đông nam |

## Quality Flags

| Field | Type | Source | Description | Example |
|---|---|---|---|---|
| is_price_negotiable | boolean | parser/enrichment | Negotiable price flag | false |
| is_missing_price | boolean | quality checks | Missing price flag | false |
| is_missing_area | boolean | quality checks | Missing area flag | false |
| is_invalid_price | boolean | quality checks | Invalid price flag | false |
| is_outlier_area | boolean | quality checks | Area outlier flag | false |
