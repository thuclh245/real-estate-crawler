from pathlib import Path
import csv
import re
import unicodedata


RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def print_error(message: str):
    print(f"{RED}{message}{RESET}")


def print_warning(message: str):
    print(f"{YELLOW}{message}{RESET}")


def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"\s+", " ", text)
    return text


def validate_seed_url(seed_url: str, final_url: str, location_path: str) -> bool:
    if not final_url:
        return False

    final_url_clean = final_url.rstrip("/")
    if location_path not in final_url_clean:
        return False

    if final_url_clean == "https://batdongsan.com.vn":
        return False

    if final_url_clean.endswith("/nha-dat-ban"):
        return False

    return True


def check_location_match(raw_text: str, expected_label: str | None, expected_slug: str | None = "") -> bool:
    if not raw_text:
        return False

    text_norm = normalize_text(raw_text)
    label_norm = normalize_text(expected_label or "")
    slug_norm = (expected_slug or "").replace("-", " ").lower()

    return bool((label_norm and label_norm in text_norm) or (slug_norm and slug_norm in text_norm))


CATEGORY_KEYWORDS = {
    "ban-can-ho-chung-cu": ["căn hộ", "chung cư", "can ho", "chung cu"],
    "ban-nha-rieng": ["nhà riêng", "nha rieng"],
    "ban-dat": ["đất", "dat"],
    "ban-nha-biet-thu-lien-ke": ["biệt thự", "liền kề", "biet thu", "lien ke"],
}


def check_category_match(raw_text: str, category_slug: str) -> bool:
    if not raw_text:
        return False

    text_norm = normalize_text(raw_text)
    keywords = CATEGORY_KEYWORDS.get(category_slug, [])
    return any(normalize_text(keyword) in text_norm for keyword in keywords)


def detect_location_conflict(
    raw_text: str,
    expected_label: str | None,
    known_location_labels: list[str],
) -> str | None:
    if not raw_text:
        return None

    text_norm = normalize_text(raw_text)
    expected_norm = normalize_text(expected_label or "")
    for label in known_location_labels:
        label_norm = normalize_text(label)
        if label_norm and label_norm != expected_norm and label_norm in text_norm:
            return label
    return None


def classify_location_match(
    raw_text: str,
    expected_label: str | None,
    expected_slug: str | None,
    is_seed_url_valid: bool,
    known_location_labels: list[str] | None = None,
) -> tuple[str, str, str]:
    if not is_seed_url_valid:
        return "unknown", "low", "invalid_seed_url"

    if check_location_match(raw_text, expected_label, expected_slug):
        return "matched", "high", "detail_text_contains_location"

    conflict_label = detect_location_conflict(raw_text, expected_label, known_location_labels or [])
    if conflict_label:
        return "mismatch", "low", f"detail_text_contains_other_location:{conflict_label}"

    return "assumed_from_seed", "medium", "seed_url_context"


def classify_category_match(raw_text: str, category_slug: str) -> tuple[str, str]:
    if check_category_match(raw_text, category_slug):
        return "matched", "high"
    return "unknown", "low"


def extract_detail_location_raw(raw_text: str, expected_label: str | None, expected_slug: str | None) -> str | None:
    if not raw_text:
        return None

    expected_terms = [
        normalize_text(expected_label or ""),
        (expected_slug or "").replace("-", " ").lower(),
    ]
    expected_terms = [term for term in expected_terms if term]
    for line in raw_text.splitlines():
        line_norm = normalize_text(line)
        if any(term in line_norm for term in expected_terms):
            return line.strip()
    return None


def safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0


def write_audit_sample_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "listing_url",
        "source_seed_url",
        "final_seed_url",
        "is_seed_url_valid",
        "crawl_category",
        "crawl_location_label",
        "title",
        "price_raw",
        "area_raw",
        "detail_location_raw",
        "location_match_status",
        "category_match_status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})
