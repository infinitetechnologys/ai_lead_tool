from .db import LeadStore
from .enrich import enrich_lead_from_website
from .filters import passes_filters
from .sources.osm_overpass import search_osm_overpass
from .sources.google_places import search_google_places
from .sources.google_maps_browser import crawl_google_maps
from .sources.directory import crawl_directories
from .sources.website_crawl import crawl_websites
from .utils import normalize_website, write_csv


def iter_sources(cfg: dict):
    sources = cfg.get("sources", {})
    if sources.get("osm_overpass", {}).get("enabled"):
        yield from search_osm_overpass(cfg)
    if sources.get("google_places", {}).get("enabled"):
        yield from search_google_places(cfg)
    if sources.get("google_maps_browser", {}).get("enabled"):
        yield from crawl_google_maps(cfg)
    if sources.get("directories", {}).get("enabled"):
        yield from crawl_directories(cfg)
    if sources.get("websites", {}).get("enabled"):
        yield from crawl_websites(cfg)


def run_pipeline(cfg: dict, export_path: str | None = None, dry_run: bool = False) -> dict:
    store = None
    if cfg["app"].get("save_to_db", True) and not dry_run:
        store = LeadStore(cfg["app"]["db_path"])
        store.init_db()

    results = []
    total = kept = saved = 0

    for lead in iter_sources(cfg):
        total += 1
        lead.website = normalize_website(lead.website)
        if cfg.get("enrichment", {}).get("fetch_website_for_email") and not lead.email:
            lead = enrich_lead_from_website(lead, cfg)
        if not passes_filters(lead, cfg):
            continue
        kept += 1
        if store:
            store.upsert(lead)
            saved += 1
        results.append(lead)

    path = export_path or (cfg["app"]["export_path"] if cfg["app"].get("export_on_run") else None)
    if path:
        if store:
            store.export_csv(path)
        else:
            write_csv(path, results)

    return {"fetched": total, "kept": kept, "saved": saved, "exported_to": path}
