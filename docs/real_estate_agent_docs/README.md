# Real Estate Big Data Lakehouse - Agent Documentation Pack

Bộ tài liệu này được chia nhỏ để đưa trực tiếp vào project `real-estate-crawler/` hoặc đưa cho code agent triển khai từng phần.

## Cách dùng nhanh

1. Copy thư mục `docs/` vào root project.
2. Đưa cho agent file `docs/00_PROJECT_CONTEXT.md` trước để hiểu bối cảnh.
3. Khi muốn code phase nào, đưa thêm file spec tương ứng.
4. Luôn yêu cầu agent làm theo `docs/14_ACCEPTANCE_CHECKLISTS.md` trước khi coi task là hoàn thành.

## Thứ tự đọc khuyến nghị cho agent

```text
00_PROJECT_CONTEXT.md
01_REPO_STRUCTURE.md
04_CONFIG_AND_CATEGORY_STRATEGY.md
02_PHASE1_CRAWLER_BRONZE.md
03_PHASE1_CRAWLER_IMPLEMENTATION_TASKS.md
05_BRONZE_CONTRACT.md
06_SILVER_PARSER_CONTRACT.md
07_SNAPSHOT_DEDUP_CONTRACT.md
08_GOLD_TABLE_CONTRACT.md
09_SPARK_ETL_JOBS.md
10_DASHBOARD_SPEC.md
11_ML_BASELINE_SPEC.md
12_REPORT_SPEC.md
13_AGENT_TASK_PROMPTS.md
14_ACCEPTANCE_CHECKLISTS.md
15_RISK_LIMITATIONS.md
16_CURRENT_STATUS_NEXT_STEPS.md
```

## Quy tắc quan trọng

- Phase 1: crawl first, save raw HTML to Bronze, parse later.
- CSV chỉ dùng để xem nhanh, không phải storage chính.
- Batdongsan source dùng `fetch_mode: crawl4ai`.
- Không tải ảnh thật ở version 1.
- Không lưu số điện thoại thật.
- Không cố geocode tới số nhà/GPS chính xác.
- ML chỉ là optional baseline, trọng tâm là data platform.
