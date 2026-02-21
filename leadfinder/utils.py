import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s\(\)]{7,}\d)")


def normalize_website(url: str | None) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/")


def extract_emails(text: str) -> list[str]:
    return sorted(set(m.lower() for m in EMAIL_RE.findall(text or "")))


def extract_phones(text: str) -> list[str]:
    found = []
    for m in PHONE_RE.findall(text or ""):
        digits = re.sub(r"\D", "", m)
        if 10 <= len(digits) <= 15:
            found.append("+" + digits if m.strip().startswith("+") else digits)
    unique = []
    for p in found:
        if p not in unique:
            unique.append(p)
    return unique


def extract_name_from_html(html: str, url: str = "") -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in ("h1", "h2"):
        el = soup.find(tag)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)[:200]
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)[:200]
    if url:
        host = urlparse(url).netloc
        return host.replace("www.", "")
    return ""


def ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_csv(path: str, leads) -> None:
    ensure_parent_dir(path)
    fieldnames = ["name", "email", "phone", "website", "city", "source", "category", "created_at"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            writer.writerow(
                {
                    "name": lead.name,
                    "email": lead.email or "",
                    "phone": lead.phone or "",
                    "website": lead.website or "",
                    "city": lead.city or "",
                    "source": lead.source or "",
                    "category": lead.category or "",
                    "created_at": lead.created_at.isoformat(),
                }
            )


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_json(path: str, data: dict) -> None:
    ensure_parent_dir(path)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
