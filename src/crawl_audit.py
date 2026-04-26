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


def audit_location(record: dict, target: dict, known_location_labels: list[str] | None = None) -> dict:
    expected_label = target.get("location_label") or target.get("district_label")
    expected_slug = target.get("location_slug") or target.get("district")
    expected_path = target.get("location_path") or target.get("district") or ""
    is_seed_url_valid = bool(record.get("is_seed_url_valid"))

    evidence_candidates = [
        ("detail_address_block", record.get("detail_address_raw"), "high"),
        ("listing_card_location", record.get("listing_card_location_raw"), "high"),
        ("breadcrumb", record.get("breadcrumb_location_raw") or record.get("breadcrumb_raw"), "high"),
    ]

    for method, evidence_text, confidence in evidence_candidates:
        if evidence_text and check_location_match(evidence_text, expected_label, expected_slug):
            return {
                "location_evidence_text": evidence_text,
                "location_evidence_source": method,
                "detail_location_raw": evidence_text,
                "location_match_status": "matched",
                "location_match_confidence": confidence,
                "location_match_method": method,
            }

        conflict_label = detect_location_conflict(evidence_text or "", expected_label, known_location_labels or [])
        if conflict_label:
            return {
                "location_evidence_text": evidence_text,
                "location_evidence_source": method,
                "detail_location_raw": evidence_text,
                "location_match_status": "mismatch",
                "location_match_confidence": "low",
                "location_match_method": f"{method}_contains_other_location:{conflict_label}",
            }

    detail_url = record.get("final_detail_url") or record.get("listing_url") or ""
    if expected_path and expected_path in detail_url:
        return {
            "location_evidence_text": None,
            "location_evidence_source": "detail_url",
            "detail_location_raw": None,
            "location_match_status": "matched",
            "location_match_confidence": "high",
            "location_match_method": "detail_url_contains_location_path",
        }

    title_description = " ".join(
        text for text in [record.get("title"), record.get("description")] if text
    )
    if title_description and check_location_match(title_description, expected_label, expected_slug):
        return {
            "location_evidence_text": None,
            "location_evidence_source": "title_or_description",
            "detail_location_raw": None,
            "location_match_status": "matched",
            "location_match_confidence": "medium",
            "location_match_method": "title_or_description_contains_location",
        }

    if is_seed_url_valid:
        return {
            "location_evidence_text": None,
            "location_evidence_source": "seed_url",
            "detail_location_raw": None,
            "location_match_status": "assumed_from_seed",
            "location_match_confidence": "medium",
            "location_match_method": "seed_url_context",
        }

    return {
        "location_evidence_text": None,
        "location_evidence_source": "none",
        "detail_location_raw": None,
        "location_match_status": "unknown",
        "location_match_confidence": "low",
        "location_match_method": "no_location_evidence",
    }


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
        "listing_card_location_raw",
        "listing_card_old_district_raw",
        "detail_address_raw",
        "breadcrumb_location_raw",
        "detail_location_raw",
        "location_evidence_text",
        "location_evidence_source",
        "location_match_status",
        "category_match_status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})
