# Kế hoạch triển khai dự án Big Data Lakehouse cho dữ liệu tin đăng bất động sản

## Tên dự án đề xuất

**A Big Data Lakehouse Platform for Real Estate Listings and Market Analytics in Vietnam**

## Định hướng tổng thể

Dự án xây dựng một nền tảng dữ liệu Big Data theo kiến trúc **lakehouse batch-first** cho dữ liệu tin đăng bất động sản. Phân tích chính tập trung vào **Hà Nội**, trong khi phạm vi **toàn Việt Nam** được dùng để kiểm thử khả năng mở rộng kỹ thuật của crawler, storage và Spark ETL pipeline.

Trọng tâm của dự án không phải là chỉ cào dữ liệu thành CSV, mà là xây dựng một pipeline dữ liệu có khả năng:

- Lưu dữ liệu thô để tái xử lý.
- Chuẩn hóa dữ liệu web bán cấu trúc.
- Theo dõi lịch sử tin đăng theo snapshot hằng ngày.
- Đánh giá chất lượng dữ liệu.
- Tạo bảng phân tích phục vụ dashboard.
- Chuẩn bị dữ liệu sạch cho ML baseline nếu còn thời gian.

## Kiến trúc tổng quan

```text
Web sources
    ↓
Crawler
    ↓
Bronze Layer: raw HTML / raw text / raw JSON / crawl log
    ↓
Spark Batch ETL
    ↓
Silver Layer: cleaned and standardized listing snapshots
    ↓
Snapshot tracking + Deduplication
    ↓
Gold Layer: analytics tables
    ↓
Dashboard + Optional ML baseline
```

## Quyết định thiết kế đã chốt

```text
Crawl frequency:
- Mỗi ngày 1 lần.
- Mỗi lần crawl lưu thành snapshot theo crawl_date.

Data source:
- Nguồn chính: batdongsan.com.vn.
- Nguồn mở rộng sau: alonhadat, nhatot, muabannhadat.

Storage:
- Dev local trước.
- Sau đó đẩy Bronze raw HTML/JSON lên Google Cloud Storage.
- CSV chỉ dùng để khảo sát, không dùng làm storage chính.

Processing:
- Spark batch ETL.
- Bronze giữ raw.
- Silver parse, clean, chuẩn hóa, gắn quality flags.
- Gold tạo bảng dashboard.

Location:
- Không cố xác định số nhà/toạ độ chính xác.
- Chuẩn hóa đến cấp tỉnh/thành, quận/huyện, phường/xã, đường/phố hoặc dự án.
- Gắn location_confidence.

Missing values:
- Không xóa ở Bronze.
- Gắn missing flags ở Silver.
- Gold lọc theo từng mục đích phân tích.

ML:
- Làm baseline đơn giản với subset sạch nếu còn thời gian.
- Target khuyến nghị: unit_price_vnd_m2.
```

---

# Phase 0: Chốt phạm vi và mục tiêu

## 0.1. Mục tiêu

Chốt rõ phạm vi dự án trước khi triển khai crawler và pipeline để tránh làm quá rộng hoặc đi sai hướng.

Dự án nên được mô tả là:

> Một nền tảng Big Data lakehouse cho dữ liệu tin đăng bất động sản, tập trung vào thu thập, lưu trữ raw data, chuẩn hóa dữ liệu, theo dõi snapshot, đánh giá chất lượng dữ liệu và phân tích thị trường theo khu vực.

## 0.2. Phạm vi chính

```text
Phân tích chính:
- Hà Nội.

Mở rộng kỹ thuật:
- Toàn Việt Nam.

Nguồn chính:
- batdongsan.com.vn.

Nguồn mở rộng:
- alonhadat.
- nhatot.
- muabannhadat.
```

## 0.3. Loại bất động sản ưu tiên

Nên crawl theo các category chính:

```text
ban-can-ho-chung-cu
ban-nha-rieng
ban-dat
ban-nha-biet-thu-lien-ke
```

Tuy nhiên, không nên chỉ crawl theo category. Cần crawl theo cả **category + location** để tránh mất thông tin khu vực.

Ví dụ:

```text
ban-nha-rieng + ha-noi + cau-giay
ban-can-ho-chung-cu + ha-noi + thanh-xuan
ban-dat + ha-noi + ha-dong
```

## 0.4. Câu hỏi phân tích chính

Dashboard và Gold tables nên phục vụ các câu hỏi sau:

1. Mỗi ngày crawler thu được bao nhiêu bản ghi?
2. Tỷ lệ crawl thành công là bao nhiêu?
3. Tỷ lệ dữ liệu thiếu giá, thiếu diện tích, thiếu location là bao nhiêu?
4. Quận nào ở Hà Nội có nhiều tin đăng nhất?
5. Loại bất động sản nào phổ biến nhất?
6. Giá trung vị và đơn giá/m² trung vị theo quận là bao nhiêu?
7. Mỗi ngày có bao nhiêu tin mới, tin cũ, tin đổi giá, tin hết hạn?
8. Dữ liệu toàn Việt Nam có giúp kiểm thử khả năng mở rộng pipeline không?

## 0.5. Deliverables của Phase 0

- File mô tả phạm vi dự án.
- Danh sách nguồn dữ liệu.
- Danh sách category cần crawl.
- Danh sách khu vực crawl chính.
- Danh sách câu hỏi dashboard.
- Sơ đồ kiến trúc tổng quan.

## 0.6. Tiêu chí hoàn thành

Phase 0 hoàn thành khi nhóm trả lời được:

```text
Dự án phân tích cái gì?
Phạm vi địa lý là gì?
Nguồn dữ liệu nào là chính?
Dữ liệu được crawl theo lịch nào?
Dashboard trả lời những câu hỏi nào?
ML có phải trọng tâm không?
```

---

# Phase 1: Crawl

## 1.1. Mục tiêu

Thu thập dữ liệu từ website bất động sản và lưu lại đầy đủ dữ liệu thô. Không chỉ lưu CSV sau parse, mà cần lưu cả HTML/JSON/text để có thể tái xử lý khi parser sai hoặc website thay đổi cấu trúc.

## 1.2. Chiến lược crawl

### Giai đoạn test

```text
100–300 listing/ngày
```

Mục tiêu:

- Kiểm tra crawler có chạy ổn không.
- Kiểm tra có bị block không.
- Kiểm tra HTML/JSON có lưu đúng không.
- Kiểm tra parser có lấy được các trường chính không.
- Kiểm tra tỷ lệ N/A ban đầu.

### Giai đoạn chính tại Hà Nội

```text
1,000–2,000 listing/ngày
```

Mục tiêu:

- Có đủ dữ liệu cho dashboard Hà Nội.
- Có dữ liệu snapshot theo ngày.
- Có dữ liệu để tính duplicate, missing value, crawl success, parse success.

### Giai đoạn mở rộng toàn Việt Nam

```text
5,000 listing/ngày hoặc crawl theo từng tỉnh/thành lớn
```

Mục tiêu:

- Kiểm thử khả năng mở rộng.
- Không cần phân tích chi tiết toàn Việt Nam ngay từ đầu.

## 1.3. Crawl theo category + location

Mỗi request crawl cần lưu context:

```text
source
crawl_date
crawl_category
crawl_city
crawl_district
page_number
listing_url
```

Ví dụ:

```json
{
  "source": "batdongsan.com.vn",
  "crawl_date": "2026-04-24",
  "crawl_category": "ban-nha-rieng",
  "crawl_city": "ha-noi",
  "crawl_district": "cau-giay",
  "page_number": 1,
  "listing_url": "https://batdongsan.com.vn/..."
}
```

Lý do cần `crawl_context`:

- Nếu trang chi tiết thiếu quận, có thể fallback từ trang danh sách.
- Nếu breadcrumb lỗi, vẫn biết listing được lấy từ khu vực nào.
- Giúp đánh giá missing_location chính xác hơn.

## 1.4. Dữ liệu cần lưu khi crawl

Với mỗi listing, cần lưu:

```text
listing_id
listing_url
source
scraped_at
crawl_date
crawl_id
crawl_status
http_status
raw_html_path
raw_text_path
raw_json_path
crawl_category
crawl_city
crawl_district
page_number
parser_version
```

## 1.5. Có cần lưu ảnh không?

Không nên tải ảnh thật ở version 1.

Nên lưu metadata nhẹ:

```text
image_count
has_image
image_urls_raw
```

Lý do:

- `image_count` có thể dùng để đánh giá chất lượng tin đăng.
- Lưu ảnh thật làm dữ liệu phình rất nhanh.
- ML ảnh là hướng nâng cao, không cần cho capstone hiện tại.

## 1.6. Có cần lưu thông tin môi giới không?

Có thể lưu ở mức metadata, không phân tích cá nhân sâu.

Nên lưu:

```text
seller_type
seller_years_on_platform
seller_active_listing_count
has_broker_certificate
phone_masked
```

Không nên lưu số điện thoại thật. Nếu có, chỉ lưu:

```text
phone_masked = true
```

Dữ liệu môi giới có thể dùng để phân tích chất lượng tin đăng:

- Tin của môi giới chuyên nghiệp có nhiều ảnh hơn không?
- Tin của seller có nhiều tin đăng có tỷ lệ duplicate cao hơn không?
- Tin VIP có đầy đủ giá/diện tích hơn không?

## 1.7. Cấu trúc thư mục crawl local

```text
data/
  bronze/
    source=batdongsan/
      crawl_date=2026-04-24/
        raw_html/
          listing_id=45615966.html
        raw_text/
          listing_id=45615966.txt
        raw_json/
          listing_id=45615966.json
        crawl_log/
          crawl_log_20260424.jsonl
```

## 1.8. Cấu trúc thư mục trên Google Cloud Storage

```text
gs://real-estate-lakehouse/
  bronze/
    source=batdongsan/
      crawl_date=2026-04-24/
        raw_html/
        raw_text/
        raw_json/
        crawl_log/
```

## 1.9. Deliverables của Phase 1

- Crawler lấy được URL từ trang danh sách.
- Crawler vào được trang chi tiết.
- Lưu được raw HTML.
- Lưu được raw text.
- Lưu được extracted JSON ban đầu.
- Lưu được crawl log.
- Có file thống kê crawl mỗi ngày.

## 1.10. Tiêu chí hoàn thành

Phase 1 hoàn thành khi:

```text
Crawl được ít nhất 100–300 listing/ngày ở giai đoạn test.
Mỗi listing có HTML/text/JSON lưu trong Bronze.
Có crawl_status cho từng URL.
Có crawl log để debug lỗi.
Không phụ thuộc vào CSV làm dữ liệu chính.
```

---

# Phase 2: Bronze Layer

## 2.1. Mục tiêu

Bronze là nơi lưu dữ liệu thô hoặc gần-thô. Không làm sạch quá nhiều ở Bronze. Mục tiêu là giữ dữ liệu gốc để có thể tái xử lý.

## 2.2. Nguyên tắc của Bronze

```text
Không xóa duplicate.
Không xóa bản ghi thiếu giá.
Không xóa bản ghi thiếu địa chỉ.
Không ghi đè dữ liệu raw.
Luôn lưu crawl metadata.
Luôn lưu parser_version nếu đã có extracted JSON.
```

## 2.3. Bronze file types

Bronze nên có 4 loại file:

```text
1. raw_html
2. raw_text
3. raw_json hoặc extracted_json
4. crawl_log
```

## 2.4. Bronze schema đề xuất

```text
crawl_id: string
source: string
crawl_date: date
scraped_at: timestamp
listing_id: string
listing_url: string
crawl_category: string
crawl_city: string
crawl_district: string
page_number: integer
crawl_status: string
http_status: integer
raw_html_path: string
raw_text_path: string
raw_json_path: string
parser_version: string
error_message: string
```

## 2.5. Crawl status values

```text
ok
failed_http
failed_timeout
failed_parse
blocked
duplicate_url
missing_listing_id
```

## 2.6. Bronze không dùng để phân tích trực tiếp

Không nên dùng Bronze để tính giá trung bình hoặc dashboard cuối cùng.

Bronze dùng để:

- Reprocess.
- Debug.
- Audit.
- Lưu snapshot raw.
- Kiểm chứng dữ liệu gốc.

## 2.7. Deliverables của Phase 2

- Thư mục Bronze có partition theo `source` và `crawl_date`.
- Có metadata file hoặc crawl log.
- Có raw HTML/text/JSON.
- Có thể truy ngược từ `listing_id` sang file raw.

## 2.8. Tiêu chí hoàn thành

Phase 2 hoàn thành khi:

```text
Mỗi listing có thể tìm lại raw HTML theo listing_id.
Mỗi ngày crawl có thư mục riêng theo crawl_date.
Dữ liệu raw không bị ghi đè.
Có thể re-run parser từ Bronze.
```

---

# Phase 3: Silver Layer

## 3.1. Mục tiêu

Silver chuyển dữ liệu thô thành dữ liệu sạch, có schema thống nhất. Đây là lớp dùng để chuẩn hóa dữ liệu từ nhiều nguồn khác nhau.

## 3.2. Nguyên tắc Silver

```text
Giữ raw fields và tạo thêm normalized fields.
Không tự ý điền bừa dữ liệu thiếu.
Gắn quality flags cho dữ liệu thiếu hoặc mơ hồ.
Có parser_version.
Có confidence score cho location và price.
```

## 3.3. Silver table chính

```text
silver_listing_snapshot
```

Bảng này chứa bản ghi đã chuẩn hóa cho từng listing trong từng ngày crawl.

## 3.4. Nhóm cột crawl metadata

```text
crawl_id
source
crawl_date
snapshot_date
scraped_at
parser_version
listing_id
listing_url
crawl_category
crawl_city
crawl_district
```

## 3.5. Nhóm cột nội dung listing

```text
title
description
content_hash
image_count
has_image
```

## 3.6. Nhóm cột thời gian

```text
posted_date
expired_date
first_seen_at
last_seen_at
```

Trong Silver, `first_seen_at` và `last_seen_at` có thể chưa tính hoàn chỉnh. Có thể tính ở Phase 4/Gold.

## 3.7. Nhóm cột location

```text
province
city
district
ward_old
ward_new
street
project_name
full_address
breadcrumb
location_level
location_parse_method
location_confidence
missing_location_flag
```

## 3.8. Thứ tự parse location

```text
1. Detail page address
2. Breadcrumb
3. URL slug
4. Crawl context
5. Title
6. Description
```

## 3.9. Location confidence

```text
high:
- Có address chi tiết hoặc breadcrumb rõ tỉnh/quận/phường.

medium:
- Có district từ crawl_context hoặc URL slug.
- Có street từ title nhưng thiếu phường.

low:
- Chỉ suy luận từ description/title mơ hồ.

unknown:
- Không xác định được location.
```

## 3.10. Nhóm cột giá

```text
price_raw
price_value_vnd
price_type
currency
unit_price_raw
unit_price_vnd_m2
market_min_unit_price_vnd_m2
market_common_unit_price_vnd_m2
market_max_unit_price_vnd_m2
description_price_raw
description_price_value_vnd
price_confidence
missing_price_flag
ambiguous_price_flag
```

## 3.11. Price type

```text
fixed_total_price
unit_price
negotiable
range_price
hidden_in_description
unknown
```

Ví dụ:

```text
"9 tỷ" → fixed_total_price
"121.6tr/m2" → unit_price
"Thỏa thuận" → negotiable
"2x,x tỷ" → hidden_in_description + ambiguous
```

## 3.12. Nhóm cột diện tích

```text
area_raw
area_m2
missing_area_flag
```

## 3.13. Nhóm cột đặc điểm bất động sản

```text
property_type
bedrooms
bathrooms
toilets
floors
frontage_m
entrance_width_m
house_direction
balcony_direction
legal_status
furniture_status
amenities
```

## 3.14. Nhóm cột seller metadata

```text
seller_type
seller_years_on_platform
seller_active_listing_count
has_broker_certificate
phone_masked
```

## 3.15. Nhóm cột data quality

```text
is_valid_record
is_valid_for_count_analysis
is_valid_for_price_analysis
is_valid_for_unit_price_analysis
is_valid_for_ml
duplicate_flag
quality_score
quality_errors
```

## 3.16. Cách xử lý missing values

### Thiếu giá

```text
price_value_vnd = null
missing_price_flag = true
is_valid_for_price_analysis = false
is_valid_for_count_analysis = true
```

### Thiếu diện tích

```text
area_m2 = null
missing_area_flag = true
is_valid_for_unit_price_analysis = false
```

### Thiếu location

```text
district = null
missing_location_flag = true
location_confidence = low hoặc unknown
is_valid_for_district_analysis = false
```

### Thiếu bedroom/bathroom

Không coi là lỗi nặng vì một số loại BĐS không có trường này.

## 3.17. Deliverables của Phase 3

- Bảng `silver_listing_snapshot`.
- Parser chuẩn hóa giá.
- Parser chuẩn hóa diện tích.
- Parser chuẩn hóa location.
- Parser chuẩn hóa property features.
- Data quality flags.
- Báo cáo tỷ lệ missing ban đầu.

## 3.18. Tiêu chí hoàn thành

Phase 3 hoàn thành khi:

```text
Dữ liệu có schema thống nhất.
Có price_value_vnd nếu parse được.
Có area_m2 nếu parse được.
Có district/ward/street nếu xác định được.
Có missing flags cho dữ liệu thiếu.
Có quality_score hoặc quality_errors.
```

---

# Phase 4: Snapshot & Deduplication

## 4.1. Mục tiêu

Theo dõi vòng đời tin đăng theo thời gian:

- Tin mới.
- Tin cũ.
- Tin đổi giá.
- Tin trùng.
- Tin hết hạn hoặc bị gỡ.

## 4.2. Vì sao cần snapshot?

Bất động sản không thay đổi real-time từng giây, nhưng listing có thể:

- Đăng mới.
- Gia hạn.
- Sửa giá.
- Sửa diện tích.
- Bị gỡ.
- Hết hạn.
- Đăng lại với nội dung gần giống.

Vì vậy mỗi ngày crawl là một snapshot của thị trường.

## 4.3. Snapshot key

```text
snapshot_date
source
listing_id
```

Nếu thiếu `listing_id`, dùng:

```text
normalized_url_hash
```

Nếu vẫn thiếu, dùng:

```text
content_hash
```

## 4.4. Deduplication rules

### Rule 1: Trùng listing_id trong cùng ngày

```text
same source + same crawl_date + same listing_id
```

Giữ bản ghi tốt nhất theo:

```text
crawl_status = ok
quality_score cao nhất
scraped_at mới nhất
```

### Rule 2: Trùng URL

```text
same normalized_url
```

Gắn:

```text
duplicate_flag = true
duplicate_reason = same_url
```

### Rule 3: Trùng nội dung gần giống

```text
same title + same area + same district + same price
```

Gắn:

```text
possible_duplicate_flag = true
duplicate_reason = similar_content
```

## 4.5. Detect listing lifecycle

### Tin mới

```text
listing_id chưa từng xuất hiện trước snapshot_date hiện tại
```

### Tin cũ

```text
listing_id đã từng xuất hiện trước đó và vẫn xuất hiện hôm nay
```

### Tin đổi giá

```text
same listing_id nhưng price_value_vnd khác snapshot trước
```

### Tin đổi nội dung

```text
same listing_id nhưng content_hash khác snapshot trước
```

### Tin hết hạn/bị gỡ

```text
listing_id từng xuất hiện nhưng không thấy trong N lần crawl gần nhất
```

Khuyến nghị:

```text
N = 2 hoặc 3 ngày
```

## 4.6. Output fields

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

## 4.7. Deliverables của Phase 4

- Logic dedup.
- Logic lifecycle tracking.
- Bảng snapshot sạch theo ngày.
- Bảng current listing.
- Thống kê tin mới/tin cũ/tin đổi giá/tin hết hạn.

## 4.8. Tiêu chí hoàn thành

Phase 4 hoàn thành khi:

```text
Phát hiện được duplicate theo listing_id.
Phân biệt được tin mới và tin cũ.
Phát hiện được tin đổi giá.
Tạo được is_active.
Tính được first_seen_at và last_seen_at.
```

---

# Phase 5: Gold Layer

## 5.1. Mục tiêu

Gold là lớp dữ liệu phục vụ dashboard, phân tích và ML baseline. Gold không lưu dữ liệu quá thô, mà lưu dữ liệu đã được tổng hợp hoặc chuẩn hóa cho từng use case.

## 5.2. Bảng 1: gold_listing_current

Mỗi listing chỉ giữ bản mới nhất.

### Schema đề xuất

```text
listing_id
source
listing_url
title
latest_price_value_vnd
price_raw
price_type
area_m2
unit_price_vnd_m2
city
district
ward_old
ward_new
street
project_name
property_type
bedrooms
bathrooms
floors
frontage_m
entrance_width_m
legal_status
furniture_status
image_count
first_seen_at
last_seen_at
is_active
days_observed
quality_score
is_valid_for_price_analysis
is_valid_for_ml
```

### Use cases

- Dashboard trạng thái hiện tại.
- Đếm listing theo quận.
- So sánh loại bất động sản.
- Chuẩn bị ML dataset.

## 5.3. Bảng 2: gold_listing_snapshot_fact

Lưu lịch sử từng listing theo ngày.

### Schema đề xuất

```text
snapshot_date
source
listing_id
price_value_vnd
area_m2
unit_price_vnd_m2
city
district
ward_old
ward_new
property_type
content_hash
is_seen
is_new_listing
price_changed_flag
content_changed_flag
is_removed_listing
quality_score
```

### Use cases

- Phân tích trend.
- Theo dõi price change.
- Theo dõi active listing.
- Theo dõi removed listing.

## 5.4. Bảng 3: gold_market_district_daily

Tổng hợp theo ngày, quận và loại bất động sản.

### Schema đề xuất

```text
snapshot_date
city
district
property_type
listing_count
active_listing_count
new_listing_count
removed_listing_count
price_changed_count
median_price_value_vnd
avg_price_value_vnd
median_unit_price_vnd_m2
avg_unit_price_vnd_m2
median_area_m2
avg_area_m2
valid_price_count
valid_area_count
```

### Use cases

- Dashboard market overview.
- District comparison.
- Trend theo ngày.

## 5.5. Bảng 4: gold_data_quality_daily

Theo dõi chất lượng dữ liệu mỗi ngày.

### Schema đề xuất

```text
crawl_date
source
crawl_category
crawl_city
crawl_district
total_urls
total_records
successful_crawls
failed_crawls
crawl_success_rate
parse_success_rate
duplicate_rate
missing_price_rate
missing_area_rate
missing_location_rate
valid_price_records
valid_location_records
processing_time_seconds
bronze_size_mb
silver_size_mb
gold_size_mb
```

### Use cases

- Data quality dashboard.
- Pipeline evaluation.
- Report evaluation.

## 5.6. Deliverables của Phase 5

- 4 bảng Gold chính.
- Dữ liệu Gold ở dạng Parquet hoặc Delta nếu có thể.
- Query hoặc notebook kiểm tra từng bảng.
- Dashboard đọc được từ Gold.

## 5.7. Tiêu chí hoàn thành

Phase 5 hoàn thành khi:

```text
Có gold_listing_current.
Có gold_listing_snapshot_fact.
Có gold_market_district_daily.
Có gold_data_quality_daily.
Dashboard có thể đọc được từ Gold.
```

---

# Phase 6: Spark Batch ETL

## 6.1. Mục tiêu

Dùng Spark để xử lý dữ liệu từ Bronze sang Silver và Gold theo batch hằng ngày.

## 6.2. Vì sao dùng Spark?

Dữ liệu có nhiều file HTML/JSON, nhiều snapshot, nhiều nguồn và cần xử lý theo batch. Spark phù hợp cho:

- Đọc nhiều file phân tán.
- Chuẩn hóa dữ liệu dạng bảng.
- Join với bảng location reference.
- Deduplication.
- Aggregation.
- Tạo Gold tables.
- Scale khi dữ liệu tăng.

## 6.3. ETL jobs đề xuất

### Job 1: bronze_to_silver

Input:

```text
bronze/source=*/crawl_date=YYYY-MM-DD/raw_json/
```

Output:

```text
silver/silver_listing_snapshot/crawl_date=YYYY-MM-DD/
```

Tasks:

- Read extracted JSON.
- Parse price.
- Parse area.
- Parse location.
- Normalize property_type.
- Extract features.
- Add data quality flags.
- Write Silver.

### Job 2: silver_snapshot_dedup

Input:

```text
silver_listing_snapshot
```

Output:

```text
silver_listing_snapshot_dedup
```

Tasks:

- Dedup by listing_id.
- Dedup by URL.
- Compute content_hash.
- Keep best record.

### Job 3: silver_to_gold_current

Input:

```text
silver_listing_snapshot_dedup
```

Output:

```text
gold_listing_current
```

Tasks:

- Find latest snapshot per listing.
- Compute first_seen_at.
- Compute last_seen_at.
- Compute is_active.
- Compute days_observed.

### Job 4: silver_to_gold_snapshot_fact

Input:

```text
silver_listing_snapshot_dedup
```

Output:

```text
gold_listing_snapshot_fact
```

Tasks:

- Detect new listing.
- Detect price change.
- Detect content change.
- Detect removed listing.

### Job 5: gold_aggregations

Input:

```text
gold_listing_snapshot_fact
gold_listing_current
```

Output:

```text
gold_market_district_daily
gold_data_quality_daily
```

Tasks:

- Aggregate by date/district/property_type.
- Compute data quality metrics.
- Compute pipeline metrics.

## 6.4. Batch schedule

Khuyến nghị:

```text
Daily crawl: 00:00 hoặc 01:00
Bronze validation: sau khi crawl xong
Spark ETL: sau khi Bronze hoàn thành
Dashboard refresh: sau khi Gold hoàn thành
```

## 6.5. Development environment

### Giai đoạn đầu

```text
Local machine hoặc Ubuntu VM
Spark local mode
Data lưu local
```

### Giai đoạn sau

```text
Google Cloud Storage cho Bronze
Spark local đọc từ GCS hoặc Google Dataproc nếu kịp
```

## 6.6. Deliverables của Phase 6

- Spark scripts hoặc notebooks.
- ETL jobs tách riêng theo phase.
- Log thời gian xử lý.
- Output Parquet/Delta.
- Tài liệu hướng dẫn chạy pipeline.

## 6.7. Tiêu chí hoàn thành

Phase 6 hoàn thành khi:

```text
Chạy được Bronze → Silver.
Chạy được Silver → Gold.
Có processing_time.
Có output partition theo crawl_date.
Có thể rerun job cho một ngày bất kỳ.
```

---

# Phase 7: Dashboard

## 7.1. Mục tiêu

Tạo dashboard để trình bày kết quả dữ liệu và chứng minh pipeline có giá trị.

Dashboard nên tập trung vào:

```text
Data quality
Market overview
District analysis
Trend / snapshot
```

## 7.2. Công cụ đề xuất

Có thể dùng:

```text
Streamlit
Power BI
Tableau
Superset
```

Khuyến nghị cho prototype:

```text
Streamlit
```

Vì dễ đọc Parquet/CSV, dễ demo, dễ tùy chỉnh.

## 7.3. Tab 1: Data Quality

### Metrics

```text
total_records
crawl_success_rate
parse_success_rate
duplicate_rate
missing_price_rate
missing_area_rate
missing_location_rate
processing_time_seconds
```

### Charts

- Line chart: records_per_day.
- Bar chart: missing rate by field.
- Bar chart: duplicate rate by source/category.
- Table: crawl errors.

## 7.4. Tab 2: Market Overview

### Metrics

```text
total_active_listings
median_price
median_unit_price_vnd_m2
top_property_type
top_district
```

### Charts

- Listing count by property_type.
- Listing count by city/district.
- Price distribution.
- Area distribution.

## 7.5. Tab 3: Hanoi District Analysis

### Metrics

```text
listing_count_by_district
median_unit_price_by_district
median_area_by_district
valid_price_count_by_district
```

### Charts

- Bar chart: số listing theo quận.
- Bar chart: giá/m² trung vị theo quận.
- Stacked bar: property_type theo quận.
- Table: top listings sạch.

## 7.6. Tab 4: Trend / Snapshot

### Metrics

```text
new_listing_count
removed_listing_count
price_changed_count
active_listing_count
```

### Charts

- Line chart: active listings by day.
- Line chart: new listings by day.
- Line chart: price changes by day.
- Line chart: median unit price by day/district.

## 7.7. Dashboard filters

Nên có filters:

```text
date range
city
district
property_type
price range
area range
source
```

## 7.8. Deliverables của Phase 7

- Dashboard chạy được.
- Dashboard đọc từ Gold.
- Có ít nhất 4 tab.
- Có ảnh chụp dashboard đưa vào report.
- Có giải thích ý nghĩa từng biểu đồ.

## 7.9. Tiêu chí hoàn thành

Phase 7 hoàn thành khi:

```text
Dashboard hiển thị data quality.
Dashboard hiển thị market overview.
Dashboard hiển thị phân tích theo quận Hà Nội.
Dashboard hiển thị trend theo ngày.
Người xem hiểu được giá trị của pipeline.
```

---

# Phase 8: Optional ML Baseline

## 8.1. Mục tiêu

Xây dựng mô hình định giá baseline đơn giản trên tập dữ liệu sạch từ Gold. ML không phải trọng tâm chính, chỉ là downstream use case chứng minh dữ liệu Gold có thể dùng cho phân tích nâng cao.

## 8.2. Điều kiện để làm ML

Chỉ làm ML nếu có đủ dữ liệu sạch:

```text
price_value_vnd IS NOT NULL
area_m2 IS NOT NULL
unit_price_vnd_m2 IS NOT NULL
district IS NOT NULL
property_type IS NOT NULL
```

## 8.3. Target

Khuyến nghị dùng:

```text
unit_price_vnd_m2
```

Không nên dùng tổng giá ngay từ đầu vì tổng giá phụ thuộc rất mạnh vào diện tích.

## 8.4. Features

```text
district
ward_old hoặc ward_new
property_type
area_m2
bedrooms
bathrooms
floors
frontage_m
entrance_width_m
legal_status
furniture_status
image_count
seller_type
```

## 8.5. Models

### Baseline 1

```text
Linear Regression
```

### Baseline 2

```text
Random Forest Regressor
```

### Optional

```text
XGBoost
CatBoost
```

## 8.6. Evaluation metrics

```text
MAE
RMSE
R²
MAPE nếu phù hợp
```

## 8.7. ML output

- Model performance table.
- Feature importance.
- Predicted vs actual chart.
- Error analysis theo quận/property_type.

## 8.8. Cách viết trong báo cáo

> Mô hình ML được triển khai như một baseline thử nghiệm trên subset dữ liệu sạch từ Gold Layer. Mục tiêu là chứng minh dữ liệu lakehouse có thể hỗ trợ downstream valuation task. Trọng tâm chính của dự án vẫn là data pipeline, snapshot tracking, data quality và market analytics.

## 8.9. Deliverables của Phase 8

- Notebook ML baseline.
- Dataset train/test từ Gold.
- Metric MAE/RMSE/R².
- Biểu đồ predicted vs actual.
- Feature importance.
- Nhận xét limitations.

## 8.10. Tiêu chí hoàn thành

Phase 8 hoàn thành khi:

```text
Có dataset ML sạch.
Có ít nhất một baseline model.
Có metrics đánh giá.
Có nhận xét vì sao model còn hạn chế.
Không làm ML lấn át phần Big Data pipeline.
```

---

# Phase 9: Report

## 9.1. Mục tiêu

Viết báo cáo cuối kỳ theo hướng **Big Data lakehouse platform**, không viết như một bài scrape dữ liệu đơn giản.

## 9.2. Cấu trúc báo cáo đề xuất

```text
1. Introduction
2. Problem Statement
3. Objectives and Scope
4. Functional and Non-functional Requirements
5. Data Sources and Data Challenges
6. System Architecture
7. Data Lakehouse Design
8. Data Schema: Bronze, Silver, Gold
9. Data Processing Pipeline with Spark
10. Snapshot Tracking and Deduplication
11. Data Quality Evaluation
12. Dashboard and Market Analytics
13. Optional ML Baseline
14. Evaluation
15. Limitations
16. Conclusion and Future Work
```

## 9.3. Nội dung cần nhấn mạnh

### Không phải dữ liệu giao dịch thật

Cần ghi rõ:

```text
Dự án phân tích thị trường tin đăng bất động sản, không phải thị trường giao dịch thực tế.
```

### Dữ liệu có nhiều vấn đề thực tế

Cần mô tả:

```text
Dữ liệu bán cấu trúc.
Nhiều giá trị thiếu.
Nhiều kiểu giá khác nhau.
Địa chỉ không luôn chính xác.
Có duplicate.
Có tin hết hạn.
Có tin thay đổi theo thời gian.
```

### Vì sao cần lakehouse

Cần giải thích:

```text
Bronze giữ raw data để reprocess.
Silver chuẩn hóa schema và quality flags.
Gold phục vụ dashboard và ML.
Snapshot giúp phân tích lịch sử.
Spark giúp batch processing và scale.
```

## 9.4. Hình ảnh nên có trong report

```text
System architecture diagram
Bronze/Silver/Gold data flow
Crawler workflow
Spark ETL workflow
Snapshot & dedup logic
Schema diagram
Dashboard screenshots
Data quality charts
Market analytics charts
Optional ML result chart
```

## 9.5. Evaluation section

Nên chia thành 3 phần:

### Data collection evaluation

```text
crawl_success_rate
records_per_day
failed_crawls
```

### Data quality evaluation

```text
parse_success_rate
duplicate_rate
missing_price_rate
missing_area_rate
missing_location_rate
```

### Processing evaluation

```text
processing_time_seconds
storage_size_by_layer
number_of_records_processed
```

## 9.6. Limitations

Cần ghi thẳng:

```text
Dữ liệu là listing, không phải giao dịch thật.
Địa chỉ không luôn đầy đủ do người đăng che thông tin.
Một số giá là "Thỏa thuận" hoặc giá ẩn trong mô tả.
Geocoding tới số nhà không đảm bảo chính xác.
Crawler có thể bị ảnh hưởng nếu website đổi cấu trúc.
ML baseline chỉ mang tính thử nghiệm.
```

## 9.7. Future work

```text
Thêm nhiều nguồn dữ liệu.
Dùng Delta Lake cho ACID/time travel.
Dùng Airflow để orchestration.
Dùng Google Dataproc để chạy Spark trên cloud.
Thêm geocoding enrichment.
Thêm entity resolution giữa nhiều nguồn.
Cải thiện ML valuation model.
Thêm monitoring và alert.
```

## 9.8. Deliverables của Phase 9

- Báo cáo cuối kỳ.
- Slide thuyết trình.
- Architecture diagram.
- Dashboard screenshots.
- Bảng kết quả evaluation.
- Code repository.
- Data sample.
- Hướng dẫn chạy pipeline.

## 9.9. Tiêu chí hoàn thành

Phase 9 hoàn thành khi:

```text
Báo cáo chứng minh được đây là Big Data platform.
Có pipeline end-to-end.
Có dữ liệu Bronze/Silver/Gold.
Có dashboard.
Có metrics đánh giá.
Có limitations rõ ràng.
Có future work hợp lý.
```

---

# Checklist tổng hợp toàn dự án

## Data collection

- [ ] Crawl được listing URLs.
- [ ] Crawl được detail pages.
- [ ] Lưu raw HTML.
- [ ] Lưu raw text.
- [ ] Lưu raw JSON/extracted JSON.
- [ ] Lưu crawl log.
- [ ] Có crawl_status.
- [ ] Có crawl_context: category/city/district.

## Bronze

- [ ] Partition theo source.
- [ ] Partition theo crawl_date.
- [ ] Raw data không bị ghi đè.
- [ ] Có raw path cho từng listing.
- [ ] Có thể reprocess từ Bronze.

## Silver

- [ ] Parse title.
- [ ] Parse description.
- [ ] Parse price.
- [ ] Parse area.
- [ ] Parse location.
- [ ] Parse property_type.
- [ ] Parse bedroom/bathroom/floors nếu có.
- [ ] Gắn missing flags.
- [ ] Gắn confidence score.
- [ ] Tạo quality_score.

## Snapshot & Dedup

- [ ] Dedup theo listing_id.
- [ ] Dedup theo normalized_url.
- [ ] Tạo content_hash.
- [ ] Phát hiện tin mới.
- [ ] Phát hiện tin đổi giá.
- [ ] Phát hiện tin hết hạn/bị gỡ.
- [ ] Tạo first_seen_at, last_seen_at, is_active.

## Gold

- [ ] gold_listing_current.
- [ ] gold_listing_snapshot_fact.
- [ ] gold_market_district_daily.
- [ ] gold_data_quality_daily.

## Spark ETL

- [ ] bronze_to_silver job.
- [ ] silver_dedup job.
- [ ] silver_to_gold_current job.
- [ ] silver_to_gold_snapshot job.
- [ ] gold_aggregation job.
- [ ] Log processing_time.
- [ ] Có thể rerun theo crawl_date.

## Dashboard

- [ ] Data quality tab.
- [ ] Market overview tab.
- [ ] Hanoi district analysis tab.
- [ ] Trend/snapshot tab.
- [ ] Filters theo date, district, property_type.

## ML baseline

- [ ] Tạo clean ML dataset.
- [ ] Chọn target unit_price_vnd_m2.
- [ ] Train baseline model.
- [ ] Có MAE/RMSE/R².
- [ ] Có feature importance.
- [ ] Có nhận xét hạn chế.

## Report

- [ ] Problem statement rõ.
- [ ] Scope rõ.
- [ ] Architecture diagram.
- [ ] Data lakehouse design.
- [ ] Schema Bronze/Silver/Gold.
- [ ] Spark ETL explanation.
- [ ] Data quality results.
- [ ] Dashboard results.
- [ ] Optional ML results.
- [ ] Limitations.
- [ ] Future work.

---

# Gợi ý timeline triển khai

## Tuần 1: Crawler + Bronze

```text
- Chốt category và location.
- Viết crawler lấy listing URLs.
- Crawl detail pages.
- Lưu raw HTML/text/JSON.
- Lưu crawl log.
- Test 100–300 listing/ngày.
```

## Tuần 2: Parser + Silver

```text
- Parse price.
- Parse area.
- Parse location.
- Parse property features.
- Gắn missing flags.
- Tạo silver_listing_snapshot.
```

## Tuần 3: Snapshot + Gold

```text
- Dedup.
- Tính first_seen_at, last_seen_at, is_active.
- Tạo gold_listing_current.
- Tạo gold_listing_snapshot_fact.
- Tạo gold_market_district_daily.
- Tạo gold_data_quality_daily.
```

## Tuần 4: Spark ETL + Dashboard

```text
- Chuyển logic sang Spark batch.
- Chạy Bronze → Silver → Gold.
- Làm dashboard data quality.
- Làm dashboard market overview.
- Làm dashboard district analysis.
- Làm dashboard trend.
```

## Tuần 5: ML baseline + Report

```text
- Tạo ML dataset từ Gold.
- Train baseline model.
- Đánh giá MAE/RMSE/R².
- Viết báo cáo.
- Chụp dashboard.
- Vẽ architecture.
- Chuẩn bị slide.
```

---

# Kết luận định hướng

Dự án nên được triển khai theo hướng:

```text
Daily batch snapshot + lakehouse storage + Spark ETL + data quality monitoring + market analytics + optional ML
```

Điểm mạnh của dự án là không cố chứng minh dữ liệu bất động sản có velocity rất cao, mà chứng minh bài toán có:

```text
Volume: nhiều listing, nhiều ngày snapshot, nhiều raw HTML/JSON.
Variety: nhiều loại BĐS, nhiều kiểu giá, nhiều schema khác nhau.
Veracity: nhiều missing values, duplicate, giá thỏa thuận, địa chỉ không đầy đủ.
Value: dashboard thị trường, chất lượng dữ liệu, xu hướng quận, ML baseline.
```

Đây là hướng phù hợp cho môn Big Data vì tập trung vào data lifecycle, storage, distributed batch processing, data quality, scalability và analytics.
