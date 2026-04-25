# 04 - Crawl Config and Category Strategy

## Core principle

Do not hard-code crawl targets in Python. Use YAML config.

## Recommended `configs/crawl_targets.yaml`

```yaml
source: batdongsan.com.vn
base_url: https://batdongsan.com.vn

crawl_settings:
  fetch_mode: crawl4ai
  max_pages_per_target: 2
  max_listings_per_target: 20
  request_delay_seconds: 5
  concurrency: 1
  stop_on_block: true
  save_images: false
  crawler_version: v0.2-crawl4ai
  parser_version: null

targets:
  - business_type: sale
    category: ban-nha-rieng
    category_label: Bán nhà riêng
    property_type_group: private_house
    city: ha-noi
    city_label: Hà Nội
    district: cau-giay
    district_label: Cầu Giấy
    seed_url: https://batdongsan.com.vn/ban-nha-rieng-cau-giay

  - business_type: sale
    category: ban-can-ho-chung-cu
    category_label: Bán căn hộ chung cư
    property_type_group: apartment
    city: ha-noi
    city_label: Hà Nội
    district: thanh-xuan
    district_label: Thanh Xuân
    seed_url: https://batdongsan.com.vn/ban-can-ho-chung-cu-thanh-xuan

  - business_type: sale
    category: ban-dat
    category_label: Bán đất
    property_type_group: land
    city: ha-noi
    city_label: Hà Nội
    district: ha-dong
    district_label: Hà Đông
    seed_url: https://batdongsan.com.vn/ban-dat-ha-dong
```

## Required target fields

```text
business_type           sale/rent
category                website slug
category_label          Vietnamese label
property_type_group     normalized group
city                    slug
city_label              Vietnamese city
 district               slug
 district_label         Vietnamese district
seed_url                direct list page URL
```

## v1 priority categories

```text
ban-can-ho-chung-cu       apartment
ban-nha-rieng             private_house
ban-dat                   land
ban-nha-biet-thu-lien-ke  villa_townhouse
```

## v2 optional categories

```text
ban-nha-mat-pho
ban-shophouse-nha-pho-thuong-mai
ban-dat-nen-du-an
```

## rental categories

Keep separate from sale analytics:

```text
cho-thue-can-ho-chung-cu
cho-thue-nha-rieng
cho-thue-van-phong
cho-thue-nha-tro-phong-tro
```

## Why category + location matters

The detail page may not always have district/address. Crawl context provides fallback:

```text
crawl_city
crawl_district
crawl_category
property_type_group
```

Do not rely only on title or description for location.
