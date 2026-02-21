from ..models import Lead
from ..enrich import fetch_html
from ..utils import extract_emails, extract_phones, extract_name_from_html, normalize_website


def crawl_websites(cfg: dict):
    src = cfg["sources"]["websites"]
    seeds = src.get("seed_urls") or []
    for url in seeds:
        html = fetch_html(url, cfg)
        if not html:
            continue
        name = extract_name_from_html(html, url)
        emails = extract_emails(html)
        phones = extract_phones(html)
        yield Lead(
            name=name or normalize_website(url),
            email=emails[0] if emails else None,
            phone=phones[0] if phones else None,
            website=normalize_website(url),
            source="website",
        )
