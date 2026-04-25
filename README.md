## Cai dat (Windows PowerShell)

Luu y: dung dung moi truong `.venv` (khong dung `.venv_mingw_backup`).

```powershell
# 1) Tao virtual environment
py -3.12 -m venv .venv

# 2) Kich hoat venv
.\.venv\Scripts\Activate.ps1

# 3) Nang cap cong cu cai dat
python -m pip install --upgrade pip setuptools wheel

# 4) Cai dependencies
python -m pip install -r requirements.txt

# 5) Cai browser cho crawl4ai/playwright
crawl4ai-setup
```

## Kiem tra nhanh

```powershell
python -c "from crawl4ai import AsyncWebCrawler; print('OK')"
python .\crawler.py --max-pages 3 --max-items 10
```

## Settings (config + CLI)

Crawler doc settings tu `crawler_config.json`.

Vi du:

```json
{
  "start_url": "https://batdongsan.com.vn/nha-dat-ban-cau-giay",
  "max_pages": 5,
  "max_items": 50,
  "page_delay_min": 1.0,
  "page_delay_max": 2.0,
  "detail_delay_min": 0.5,
  "detail_delay_max": 1.5,
  "save_every": 1
}
```

Y nghia:

- `start_url`: URL listing dau vao can crawl.
- `max_pages`: so trang listing toi da.
- `max_items`: so tin chi tiet toi da trong 1 lan chay.
- `page_delay_min`, `page_delay_max`: do tre giua cac request listing page.
- `detail_delay_min`, `detail_delay_max`: do tre giua cac request detail page.
- `save_every`: ghi CSV moi N ban ghi thanh cong (1 = ghi ngay).

Thu tu uu tien gia tri:

1. Tham so CLI (neu co)
2. Gia tri trong `crawler_config.json`
3. Fallback noi bo trong code

Lenh hay dung:

```powershell
# Chay theo config.json
python .\crawler.py

# Chay lon, co resume, ghi ngay tung ban ghi
python .\crawler.py --resume --save-every 1

# Override gioi han de test nhanh
python .\crawler.py --resume --max-pages 2 --max-items 5  --save-every 1

chinh xac chay luon
python .\crawler.py --resume --max-pages 50 --max-items 1000 --save-every 20

```

Luu y:

- `--resume` se bo qua `listing_url` da co trong file output.
- Khong dung `--resume` thi crawler se crawl lai cac URL cu.

## Chay tren Google Colab

Xem huong dan rieng tai `COLAB_GUIDE.md`.

## Xu ly loi thuong gap

```powershell
python -c "import sys; print(sys.executable)"
```

Interpreter dung phai tro den duong dan co `.venv\Scripts\python.exe`.
