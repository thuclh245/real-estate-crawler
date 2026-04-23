# Crawler Architecture

Tai lieu nay mo ta luong chay cua crawler bang Mermaid de ban de hinh dung.

## 1) Tong quan luong ham

```mermaid
graph TD
    A[CLI start] --> B[main]
    B --> C[load config]
    B --> D[load existing links]
    B --> E[open crawler context]

    E --> F[collect listing links]
    F --> G[build listing page url]
    F --> H[fetch listing html]
    H --> I[extract listing links]
    I --> J[deduplicate and limit]

    J --> K[resume filter]
    K --> L[fetch detail pages]
    L --> M[fetch detail html]
    M --> N[parse detail]

    N --> O[json ld candidates]
    N --> P[pick best json ld]
    N --> Q[pick price]
    N --> R[extract numbers and id]
    N --> S[fallback regex]

    L --> T[rows]
    T --> U[append csv]
    U --> V[output file]
```

### Giai thich nhanh

- crawler.py: entrypoint, doc tham so, goi pipeline.
- crawler_storage.py: doc config, doc link da co (resume), ghi CSV.
- crawler_runner.py: dieu phoi crawl listing pages va detail pages.
- crawler_extractors.py: toan bo logic trich xuat field tu HTML/JSON-LD.
- crawler_settings.py: constants dung chung.

## 2) Trinh tu thuc thi theo thoi gian

```mermaid
sequenceDiagram
    participant User as User/CLI
    participant Main as crawler.py::main
    participant Store as crawler_storage
    participant Run as crawler_runner
    participant Ext as crawler_extractors
    participant Web as batdongsan.com.vn

    User->>Main: Run python crawler.py --max-pages N --max-items M
    Main->>Store: load_config(config_path)
    Store-->>Main: config dict
    Main->>Store: load_existing_links(output_file) (neu --resume)
    Store-->>Main: existing_links set

    loop Moi listing page
        Main->>Run: collect_listing_links(...)
        Run->>Ext: listing_page_url(base_url, page)
        Run->>Web: crawler.arun(page_url)
        Web-->>Run: page html
        Run->>Ext: extract_listing_links(html)
        Ext-->>Run: filtered links
    end

    Main->>Run: fetch_details(links)
    loop Moi detail link
        Run->>Web: crawler.arun(detail_url)
        Web-->>Run: detail html
        Run->>Ext: parse_detail(html, url)
        Ext-->>Run: row dict
    end

    Main->>Store: append_rows(rows, output_file)
    Store-->>Main: done
    Main-->>User: Done. Appended X rows
```

### Giai thich nhanh

- Vong 1: lay danh sach URL chi tiet tu cac trang listing.
- Vong 2: vao tung URL chi tiet de parse truong du lieu.
- Cuoi cung: ghi tat ca row vao CSV theo schema OUTPUT_COLUMNS.

## 3) Mapping truong du lieu (tam tat)

- title, description: uu tien JSON-LD, fallback title tag.
- price, price_raw: uu tien offers.price trong JSON-LD, fallback regex text.
- property_size, property_size_raw: uu tien floorSize JSON-LD, fallback regex m2.
- bedrooms, bathrooms: regex tren text da loai bo HTML tags.
- city, district: suy doan tu URL slug khi khong co du lieu ro rang.

## 4) Cach su dung file nay

1. Mo file nay trong VS Code.
2. Neu can preview: Open Preview to the Side.
3. Chinh sua Mermaid block neu ban doi ten ham/module.
