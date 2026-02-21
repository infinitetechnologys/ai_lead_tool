from copy import deepcopy
from pathlib import Path
import os
import yaml


DEFAULT_CONFIG = {
    "app": {
        "db_path": "data/leads.db",
        "export_path": "data/leads.csv",
        "save_to_db": True,
        "export_on_run": False,
        "user_agent": "LeadFinderBot/0.2 (contact: you@example.com)",
        "request_timeout_s": 20,
        "request_delay_s": 0.2,
        "cache_dir": "data/cache",
    },
    "sources": {
        "osm_overpass": {
            "enabled": True,
            "overpass_url": "https://overpass-api.de/api/interpreter",
            "nominatim_url": "https://nominatim.openstreetmap.org/search",
            "tag_filters": ["craft=plumber"],
            "name_contains": [],
            "cities": ["Austin, TX"],
            "bboxes": [],
            "max_results": 200,
            "overpass_timeout_s": 25,
            "geocode_delay_s": 1.1,
            "debug": False,
        },
        "google_places": {
            "enabled": False,
            "api_key": "",
            "query": "plumber",
            "cities": ["Austin, TX"],
            "max_results": 60,
            "fetch_details": True,
        },
        "google_maps_browser": {
            "enabled": False,
            "query": "real estate agent",
            "cities": ["Ahmedabad, Gujarat, India"],
            "max_results": 40,
            "headless": True,
            "slow_mo_ms": 0,
            "wait_after_search_ms": 2000,
            "result_click_delay_s": 0.8,
        },
        "directories": {
            "enabled": False,
            "seed_urls": [],
            "listing_link_selector": "",
            "max_business_pages": 50,
        },
        "websites": {
            "enabled": False,
            "seed_urls": [],
        },
    },
    "filters": {
        "exclude_startups": True,
        "startup_keywords": ["startup", "saas", "venture", "accelerator", "incubator"],
        "website_policy": "exclude_missing",
    },
    "enrichment": {
        "fetch_website_for_email": True,
        "max_pages_per_site": 1,
        "allowed_email_domains": [],
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: str) -> dict:
    cfg = deepcopy(DEFAULT_CONFIG)
    p = Path(path)
    if p.exists():
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        deep_merge(cfg, data)

    if not cfg["sources"]["google_places"].get("api_key"):
        env_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
        if env_key:
            cfg["sources"]["google_places"]["api_key"] = env_key

    filt = cfg.get("filters", {})
    if "website_policy" not in filt and "require_missing_website" in filt:
        filt["website_policy"] = "only_missing" if filt.get("require_missing_website") else "allow_all"

    return cfg
