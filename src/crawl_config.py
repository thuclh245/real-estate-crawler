from pathlib import Path

import yaml


def load_config(config_path: str | Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def expand_targets(config: dict) -> list[dict]:
    if config.get("targets"):
        expanded_targets = []
        for target in config["targets"]:
            categories = target.get("categories")
            if not categories:
                expanded_targets.append(target)
                continue

            base_target = {key: value for key, value in target.items() if key != "categories"}
            for category in categories:
                expanded_targets.append({
                    **base_target,
                    "business_type": category.get("listing_business_type") or category.get("business_type"),
                    "category": category.get("slug") or category.get("category"),
                    "category_label": category.get("label") or category.get("category_label"),
                    "property_type_group": category.get("property_type_group"),
                })
        return expanded_targets

    if config.get("categories") and config.get("locations"):
        expanded_targets = []
        for location in config["locations"]:
            for category in config["categories"]:
                expanded_targets.append({
                    **location,
                    "business_type": category.get("listing_business_type") or category.get("business_type"),
                    "category": category.get("slug") or category.get("category"),
                    "category_label": category.get("label") or category.get("category_label"),
                    "property_type_group": category.get("property_type_group"),
                })
        return expanded_targets

    raise ValueError("Config must define either targets or categories + locations.")


def get_target_city(target: dict) -> str | None:
    return target.get("city") or target.get("city_slug")


def get_target_location_path(target: dict) -> str:
    location_path = target.get("location_path") or target.get("district")
    if not location_path:
        raise ValueError(f"Target is missing location_path/district: {target}")
    return location_path


def get_target_location_slug(target: dict) -> str | None:
    return target.get("location_slug") or target.get("district")


def get_target_location_label(target: dict) -> str | None:
    return target.get("location_label") or target.get("district_label")
