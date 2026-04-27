import re
import hashlib
from datetime import datetime, timezone


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def extract_listing_id(url: str) -> str | None:
    match = re.search(r"pr(\d+)", url)
    if match:
        return match.group(1)
    return None


def url_to_hash(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def get_listing_id_or_hash(url: str) -> str:
    return extract_listing_id(url) or url_to_hash(url)