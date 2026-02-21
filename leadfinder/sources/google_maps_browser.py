import time
from urllib.parse import quote_plus

from ..models import Lead
from ..utils import normalize_website


def _safe_text(locator, timeout_ms: int = 1000) -> str:
    try:
        return (locator.first.inner_text(timeout=timeout_ms) or "").strip()
    except Exception:
        return ""


def _safe_attr(locator, attr: str, timeout_ms: int = 1000) -> str:
    try:
        return (locator.first.get_attribute(attr, timeout=timeout_ms) or "").strip()
    except Exception:
        return ""


def crawl_google_maps(cfg: dict):
    src = cfg.get("sources", {}).get("google_maps_browser", {})
    if not src.get("enabled"):
        return

    query = (src.get("query") or "").strip()
    cities = [c for c in (src.get("cities") or []) if c]
    max_results = int(src.get("max_results", 40))
    headless = bool(src.get("headless", True))
    slow_mo_ms = int(src.get("slow_mo_ms", 0))
    wait_after_search_ms = int(src.get("wait_after_search_ms", 2000))
    result_click_delay_s = float(src.get("result_click_delay_s", 0.8))

    if not query:
        print("Google Maps Browser: query is empty.")
        return

    from playwright.sync_api import sync_playwright

    targets = cities or [None]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo_ms)
        page = browser.new_page()

        for city in targets:
            q = f"{query} {city}".strip() if city else query
            url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(q)}"
            page.goto(url, wait_until="domcontentloaded")

            try:
                page.wait_for_selector("div[role='article']", timeout=15000)
            except Exception:
                print("Google Maps Browser: no results list found.")
                continue

            if wait_after_search_ms:
                time.sleep(wait_after_search_ms / 1000.0)

            seen_names = set()
            idx = 0

            while idx < max_results:
                items = page.locator("div[role='article']")
                count = items.count()
                if idx >= count:
                    feed = page.locator("div[role='feed']")
                    if feed.count():
                        try:
                            feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
                        except Exception:
                            break
                        time.sleep(1.0)
                        if items.count() == count:
                            break
                        continue
                    break

                item = items.nth(idx)
                name = _safe_attr(item, "aria-label") or _safe_text(item.locator("div[role='heading']"))
                if not name or name in seen_names:
                    idx += 1
                    continue
                seen_names.add(name)

                try:
                    item.click(timeout=2000)
                except Exception:
                    idx += 1
                    continue

                if result_click_delay_s:
                    time.sleep(result_click_delay_s)

                address = _safe_text(page.locator("[data-item-id='address']"))
                phone = _safe_text(page.locator("[data-item-id^='phone']"))

                website = _safe_attr(page.locator("a[data-item-id='authority']"), "href")
                if not website:
                    website = _safe_text(page.locator("[data-item-id='authority']"))

                lead_city = city
                if address and not lead_city:
                    parts = [p.strip() for p in address.split(",") if p.strip()]
                    if len(parts) >= 2:
                        lead_city = parts[-2]

                yield Lead(
                    name=name,
                    phone=phone or None,
                    website=normalize_website(website) if website else None,
                    city=lead_city,
                    source="google_maps_browser",
                    category="",
                    raw={"query": q, "address": address},
                )

                idx += 1

        browser.close()
