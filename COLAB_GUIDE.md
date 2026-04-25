# Huong Dan Chay Tren Google Colab

Tai lieu nay huong dan chay crawler tren Google Colab theo quy trinh:

1. Cap nhat code local.
2. Push len Git.
3. Colab clone repo ve va chay.

Khong upload tay cac file `.py` len Colab.

## 1) Clone source code tu Git

Trong Colab, chi clone repo tu Git:

```python
REPO_URL = "https://github.com/<your-org-or-user>/<your-repo>.git"
!git clone {REPO_URL}
```

Sau do vao dung thu muc repo (rat quan trong de path `output/...` dung):

```python
%cd /content/<your-repo>
!pwd
!ls
```

Ban phai thay cac file nhu `crawler.py`, `crawler_config.json`, `requirements.txt` trong thu muc hien tai.

Neu ban vua push code moi, co the xoa repo cu trong Colab roi clone lai:

```python
!rm -rf /content/<your-repo>
!git clone {REPO_URL}
%cd /content/<your-repo>
```

## 2) Cai dependencies

```python
!python -m pip install --upgrade pip setuptools wheel
!python -m pip install -r requirements.txt
```

## 3) Cai browser cho crawl4ai/playwright

```python
!crawl4ai-setup
```

Neu Colab bao khong tim thay `crawl4ai-setup`, chay fallback:

```python
!python -m playwright install chromium
```

## 4) Chay crawler

```python
!python crawler.py --resume --max-pages 2 --max-items 5 --save-every 1
```

Hoac de doc settings tu `crawler_config.json`:

```python
!python crawler.py --resume --save-every 1
```

Kiem tra output duoc tao dung vi tri:

```python
!ls -lah output
!head -n 5 output/listings_crawl4ai.csv
```

## 5) Tai file ket qua ve may

```python
from google.colab import files
files.download("output/listings_crawl4ai.csv")
```

## Luu y khi chay Colab

- Runtime Colab co the reset, nen uu tien `--save-every 1` de ghi du lieu lien tuc.
- Nen dung `--resume` khi chay lai de tranh crawl trung URL da co.
- Neu crawl lon, nen chia nho theo `--max-pages` va `--max-items`.
- Neu duong dan output sai, kiem tra lai `%cd` da vao dung thu muc repo chua.
