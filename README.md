# AI Lead Finder Tool

Python lead finder that pulls business leads from OpenStreetMap (Overpass API), optionally enriches from websites, then filters, stores, and exports to CSV.

Features
- Free Overpass API business search (no paid key)
- Optional website and email enrichment
- Startup and website filters
- SQLite storage and CSV export
- Extensible sources (directories, websites)

Quickstart
1. Create a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Edit `config.yaml`.
Set `sources.osm_overpass.tag_filters` to your business type (example: `craft=plumber`).
Set `sources.osm_overpass.cities` or `sources.osm_overpass.bboxes`.
Update `app.user_agent` with contact info for polite API usage.
4. Initialize the database: `python -m leadfinder init-db --config config.yaml`
5. Run the pipeline: `python -m leadfinder run --config config.yaml --export data/leads.csv`

Local web service
1. Install dependencies: `pip install -r requirements.txt`
2. Start the API: `python -m leadfinder.server`
3. Examples:
   - Dashboard: `http://127.0.0.1:8000/`
   - Health: `GET http://127.0.0.1:8000/health`
   - Run: `POST http://127.0.0.1:8000/run?config_path=config.yaml&export=data/leads.csv&no_enrich=true`
   - Export: `POST http://127.0.0.1:8000/export?out=data/leads.csv&config_path=config.yaml`

Config notes
- `sources.osm_overpass.tag_filters` accepts `key=value` or `key=*`.
- `filters.website_policy` options.
`allow_all`: keep all businesses.
`exclude_missing`: drop businesses without websites.
`only_missing`: keep only businesses without websites.
- `enrichment.fetch_website_for_email` enables crawling business websites to find emails and phones.

Usage policies
- Overpass and Nominatim are free public services with rate limits. Use caching and delays.
- For large scale usage, consider running your own Overpass or Nominatim instance.
- Respect site terms of service and robots.txt when crawling websites.
