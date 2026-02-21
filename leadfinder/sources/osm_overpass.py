import time
from pathlib import Path
import requests

from ..models import Lead
from ..utils import extract_emails, extract_phones, normalize_website, load_json, save_json


CATEGORY_KEYS = [
    "amenity",
    "shop",
    "office",
    "craft",
    "tourism",
    "leisure",
    "healthcare",
    "emergency",
    "club",
    "service",
    "industrial",
]
EMAIL_KEYS = ["contact:email", "email"]
PHONE_KEYS = ["contact:phone", "phone", "contact:mobile", "mobile"]
WEBSITE_KEYS = ["contact:website", "website", "contact:url", "url"]
CITY_KEYS = ["addr:city", "addr:town", "addr:village", "addr:municipality", "addr:county", "addr:place"]

_last_geocode_ts = 0.0


def _parse_tag_filters(raw):
    filters = []
    for item in raw or []:
        if not item:
            continue
        text = str(item).strip()
        if not text:
            continue
        if "=" in text:
            key, value = text.split("=", 1)
            filters.append({"key": key.strip(), "value": value.strip()})
        else:
            filters.append({"key": text, "value": "*"})
    return filters


def _filter_to_overpass(tag):
    key = tag["key"]
    value = tag["value"]
    if value in ("", "*"):
        return f'["{key}"]'
    return f'["{key}"="{value}"]'


def _build_query(tag_filters, bbox, timeout_s):
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    parts = []
    for tag in tag_filters:
        filt = _filter_to_overpass(tag)
        parts.append(f"node{filt}({bbox_str});")
        parts.append(f"way{filt}({bbox_str});")
        parts.append(f"relation{filt}({bbox_str});")
    if not parts:
        return ""
    body = "\n".join(parts)
    return f"[out:json][timeout:{int(timeout_s)}];({body});out center tags;"


def _log(cfg, message: str) -> None:
    if cfg.get("sources", {}).get("osm_overpass", {}).get("debug"):
        print(message)


def _request_overpass(query, cfg):
    if not query:
        return {}
    delay = float(cfg["app"].get("request_delay_s", 0))
    if delay:
        time.sleep(delay)
    url = cfg["sources"]["osm_overpass"].get("overpass_url")
    timeout = float(cfg["app"].get("request_timeout_s", 20))
    headers = {"User-Agent": cfg["app"].get("user_agent", "LeadFinderBot/0.1")}
    try:
        resp = requests.post(url, data={"data": query}, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        _log(cfg, f"OSM Overpass request failed: {exc}")
        return {}
    if not resp.ok:
        snippet = (resp.text or "")[:200].replace("\n", " ")
        _log(cfg, f"OSM Overpass HTTP {resp.status_code}: {snippet}")
        return {}
    try:
        return resp.json()
    except ValueError:
        _log(cfg, "OSM Overpass: invalid JSON response.")
        return {}


def _parse_bbox(value):
    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            return [float(x) for x in value]
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if len(parts) == 4:
            try:
                return [float(p) for p in parts]
            except ValueError:
                return None
    return None


def _geocode_city(city, cfg, cache):
    if not city:
        return None
    if city in cache:
        return cache[city]

    delay_s = float(cfg["sources"]["osm_overpass"].get("geocode_delay_s", 1.1))
    global _last_geocode_ts
    now = time.time()
    wait = max(0.0, delay_s - (now - _last_geocode_ts))
    if wait:
        time.sleep(wait)
    _last_geocode_ts = time.time()

    url = cfg["sources"]["osm_overpass"].get("nominatim_url")
    timeout = float(cfg["app"].get("request_timeout_s", 20))
    headers = {"User-Agent": cfg["app"].get("user_agent", "LeadFinderBot/0.1")}
    params = {"format": "json", "q": city, "limit": 1, "addressdetails": 1}

    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    if not resp.ok:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    if not data:
        return None

    item = data[0]
    bbox = item.get("boundingbox")
    if not bbox or len(bbox) != 4:
        return None

    south, north, west, east = [float(x) for x in bbox]
    address = item.get("address", {}) if isinstance(item, dict) else {}
    city_name = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or city
    )
    result = {"bbox": [south, west, north, east], "city": city_name}
    cache[city] = result
    return result


def _pick_first_tag(tags, keys):
    for key in keys:
        val = tags.get(key)
        if val:
            return val
    return ""


def _extract_email(tags):
    raw = _pick_first_tag(tags, EMAIL_KEYS)
    emails = extract_emails(raw)
    return emails[0] if emails else None


def _extract_phone(tags):
    raw = _pick_first_tag(tags, PHONE_KEYS)
    phones = extract_phones(raw)
    return phones[0] if phones else None


def _extract_website(tags):
    raw = _pick_first_tag(tags, WEBSITE_KEYS)
    return normalize_website(raw) if raw else None


def _extract_city(tags):
    for key in CITY_KEYS:
        val = tags.get(key)
        if val:
            return val
    return None


def _extract_category(tags, tag_filters):
    parts = []
    for key in CATEGORY_KEYS:
        val = tags.get(key)
        if val:
            parts.append(f"{key}={val}")
    if not parts:
        for tag in tag_filters:
            key = tag.get("key")
            val = tags.get(key) if key else None
            if val:
                parts.append(f"{key}={val}")
    return ",".join(parts)


def _matches_name(name, tags, tokens):
    if not tokens:
        return True
    hay = " ".join(
        [
            name or "",
            tags.get("operator", ""),
            tags.get("brand", ""),
            tags.get("description", ""),
        ]
    ).lower()
    return any(tok in hay for tok in tokens)


def search_osm_overpass(cfg):
    src = cfg.get("sources", {}).get("osm_overpass", {})
    if not src.get("enabled"):
        return

    tag_filters = _parse_tag_filters(src.get("tag_filters"))
    if not tag_filters:
        print("OSM Overpass: tag_filters is empty.")
        return

    name_contains = [t.lower() for t in (src.get("name_contains") or []) if t]
    max_results = int(src.get("max_results", 0))
    overpass_timeout = float(src.get("overpass_timeout_s", 25))

    cache_dir = cfg.get("app", {}).get("cache_dir", "data/cache")
    cache_path = Path(cache_dir) / "nominatim.json"
    cache = load_json(str(cache_path))

    locations = []
    for bbox in src.get("bboxes") or []:
        parsed = _parse_bbox(bbox)
        if parsed:
            locations.append({"bbox": parsed, "city": None})

    for city in src.get("cities") or []:
        geo = _geocode_city(city, cfg, cache)
        if geo:
            locations.append({"bbox": geo["bbox"], "city": geo["city"]})

    if src.get("cities"):
        save_json(str(cache_path), cache)

    if not locations:
        print("OSM Overpass: no locations configured (cities or bboxes).")
        return

    for loc in locations:
        query = _build_query(tag_filters, loc["bbox"], overpass_timeout)
        data = _request_overpass(query, cfg)
        elements = data.get("elements", []) if isinstance(data, dict) else []
        if not elements:
            _log(
                cfg,
                f"OSM Overpass: 0 elements for bbox {loc['bbox']} and filters {tag_filters}",
            )
        fetched = 0

        for el in elements:
            if max_results and fetched >= max_results:
                break
            tags = el.get("tags", {}) if isinstance(el, dict) else {}
            name = tags.get("name") or tags.get("operator") or tags.get("brand")
            if not name:
                continue
            if not _matches_name(name, tags, name_contains):
                continue

            email = _extract_email(tags)
            phone = _extract_phone(tags)
            website = _extract_website(tags)
            city = _extract_city(tags) or loc.get("city")
            category = _extract_category(tags, tag_filters)

            yield Lead(
                name=name,
                email=email,
                phone=phone,
                website=website,
                city=city,
                source="osm_overpass",
                category=category,
                raw={"osm_id": el.get("id"), "osm_type": el.get("type"), "tags": tags},
            )
            fetched += 1
