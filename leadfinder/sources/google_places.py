import time
import requests

from ..models import Lead


TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def _request(url: str, params: dict, cfg: dict) -> dict:
    delay = cfg["app"].get("request_delay_s", 0)
    if delay:
        time.sleep(delay)
    resp = requests.get(url, params=params, timeout=cfg["app"].get("request_timeout_s", 15))
    if not resp.ok:
        return {}
    return resp.json() or {}


def _parse_city(address_components: list[dict]) -> str | None:
    for comp in address_components or []:
        types = comp.get("types", [])
        if "locality" in types:
            return comp.get("long_name")
    for comp in address_components or []:
        types = comp.get("types", [])
        if "administrative_area_level_2" in types:
            return comp.get("long_name")
    return None


def _parse_city_from_address(address: str | None) -> str | None:
    if not address:
        return None
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[-3]
    if len(parts) >= 2:
        return parts[-2]
    return None


def _get_details(place_id: str, api_key: str, cfg: dict) -> dict:
    if not place_id:
        return {}
    params = {
        "place_id": place_id,
        "key": api_key,
        "fields": "name,formatted_phone_number,website,types,formatted_address,address_components",
    }
    data = _request(DETAILS_URL, params, cfg)
    return data.get("result", {}) if isinstance(data, dict) else {}


def search_google_places(cfg: dict):
    gp = cfg["sources"]["google_places"]
    api_key = gp.get("api_key") or ""
    if not api_key:
        print("Google Places API key missing. Set sources.google_places.api_key or GOOGLE_PLACES_API_KEY.")
        return

    query = gp.get("query", "")
    cities = gp.get("cities") or []
    max_results = int(gp.get("max_results", 60))
    fetch_details = bool(gp.get("fetch_details", True))

    targets = cities or [None]
    for city in targets:
        q = f"{query} in {city}" if city else query
        fetched = 0
        page_token = None

        while True:
            params = {"query": q, "key": api_key}
            if page_token:
                params["pagetoken"] = page_token
            data = _request(TEXT_SEARCH_URL, params, cfg)
            results = data.get("results", []) if isinstance(data, dict) else []

            for item in results:
                if fetched >= max_results:
                    break
                place_id = item.get("place_id")
                details = _get_details(place_id, api_key, cfg) if fetch_details else {}

                name = details.get("name") or item.get("name") or ""
                phone = details.get("formatted_phone_number")
                website = details.get("website")
                types = details.get("types") or item.get("types") or []
                address = details.get("formatted_address") or item.get("formatted_address")
                city_name = _parse_city(details.get("address_components")) or _parse_city_from_address(address)

                yield Lead(
                    name=name,
                    phone=phone,
                    website=website,
                    city=city_name,
                    source="google_places",
                    category=",".join(types),
                    raw={"text_search": item, "details": details},
                )
                fetched += 1

            if fetched >= max_results:
                break
            page_token = data.get("next_page_token") if isinstance(data, dict) else None
            if not page_token:
                break
            time.sleep(2.0)
