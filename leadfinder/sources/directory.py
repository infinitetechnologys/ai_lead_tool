from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from ..models import Lead
from ..enrich import fetch_html
from ..utils import extract_emails, extract_phones, extract_name_from_html, normalize_website


def _find_external_website(soup: BeautifulSoup, base_url: str) -> str | None:
    base_domain = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        text = a.get_text(" ", strip=True).lower()
        domain = urlparse(href).netloc
        if not domain:
            continue
        if domain != base_domain and ("website" in text or "visit" in text):
            return href
    return None


def _lead_from_html(url: str, html: str, source: str) -> Lead | None:
    name = extract_name_from_html(html, url)
    if not name:
        return None
    emails = extract_emails(html)
    phones = extract_phones(html)
    soup = BeautifulSoup(html, "html.parser")
    website = _find_external_website(soup, url) or url
    return Lead(
        name=name,
        email=emails[0] if emails else None,
        phone=phones[0] if phones else None,
        website=normalize_website(website),
        source=source,
    )


def crawl_directories(cfg: dict):
    src = cfg["sources"]["directories"]
    seeds = src.get("seed_urls") or []
    selector = src.get("listing_link_selector") or ""
    max_pages = int(src.get("max_business_pages", 50))

    for seed in seeds:
        html = fetch_html(seed, cfg)
        if not html:
            continue
        if selector:
            soup = BeautifulSoup(html, "html.parser")
            links = [urljoin(seed, a["href"]) for a in soup.select(selector) if a.get("href")]
            links = links[:max_pages]
        else:
            links = [seed]

        for link in links:
            page_html = fetch_html(link, cfg)
            if not page_html:
                continue
            lead = _lead_from_html(link, page_html, source="directory")
            if lead:
                yield lead
