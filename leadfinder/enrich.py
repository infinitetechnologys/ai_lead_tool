import requests
from bs4 import BeautifulSoup

from .utils import extract_emails, extract_phones, normalize_website


def fetch_html(url: str, cfg: dict) -> str:
    timeout = cfg["app"].get("request_timeout_s", 15)
    headers = {"User-Agent": cfg["app"].get("user_agent", "LeadFinderBot/0.1")}
    resp = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
    if not resp.ok:
        return ""
    ctype = resp.headers.get("content-type", "")
    if "text/html" not in ctype:
        return ""
    return resp.text


def pick_email(emails: list[str], cfg: dict) -> str | None:
    allowed = cfg.get("enrichment", {}).get("allowed_email_domains") or []
    if allowed:
        allowed_lc = {d.lower() for d in allowed}
        for e in emails:
            domain = e.split("@")[-1].lower()
            if domain in allowed_lc:
                return e
    return emails[0] if emails else None


def enrich_lead_from_website(lead, cfg: dict):
    if not lead.website:
        return lead
    url = normalize_website(lead.website)
    if not url:
        return lead
    html = fetch_html(url, cfg)
    if not html:
        return lead

    emails = extract_emails(html)
    if emails and not lead.email:
        lead.email = pick_email(emails, cfg)

    if not lead.phone:
        phones = extract_phones(html)
        if phones:
            lead.phone = phones[0]

    if not lead.name:
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.get_text(strip=True):
            lead.name = soup.title.get_text(strip=True)[:200]
    return lead
