from flask import Flask, Response, jsonify, request
from pathlib import Path
import yaml

from .config import load_config
from .db import LeadStore
from .pipeline import run_pipeline


app = Flask(__name__)


def _persist_google_maps_settings(config_path: str, gm_query: str | None, gm_cities: str | None, gm_max_results):
    if not config_path:
        return
    if gm_query is None and gm_cities is None and (gm_max_results is None or gm_max_results == ""):
        return

    path = Path(config_path)
    data = {}
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}

    sources = data.setdefault("sources", {})
    gm = sources.setdefault("google_maps_browser", {})
    gm["enabled"] = True
    if gm_query:
        gm["query"] = gm_query
    if gm_cities is not None:
        gm["cities"] = [c.strip() for c in gm_cities.split(",") if c.strip()]
    if gm_max_results is not None and gm_max_results != "":
        try:
            gm["max_results"] = int(gm_max_results)
        except ValueError:
            pass

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@app.get("/")
def index():
    html = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI Lead Finder</title>
    <style>
      :root {
        --bg: #f6f3ee;
        --card: #ffffff;
        --ink: #1f1d1b;
        --muted: #6b6460;
        --accent: #0f4c81;
        --accent-2: #f0b429;
        --border: #e6e0d8;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Georgia", "Times New Roman", serif;
        color: var(--ink);
        background: radial-gradient(circle at top, #fffaf2, var(--bg));
      }
      .wrap {
        max-width: 860px;
        margin: 40px auto;
        padding: 0 20px 40px;
      }
      h1 {
        font-size: 32px;
        margin: 0 0 6px;
        letter-spacing: 0.2px;
      }
      p.subtitle {
        margin: 0 0 22px;
        color: var(--muted);
      }
      .card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 10px 30px rgba(30, 20, 10, 0.08);
      }
      .row {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-bottom: 14px;
      }
      label {
        display: flex;
        flex-direction: column;
        gap: 6px;
        font-size: 14px;
        color: var(--muted);
        flex: 1 1 220px;
      }
      input[type="text"] {
        padding: 10px 12px;
        border-radius: 10px;
        border: 1px solid var(--border);
        font-size: 14px;
      }
      .checks {
        display: flex;
        gap: 18px;
        align-items: center;
        margin: 8px 0 16px;
        color: var(--muted);
        font-size: 14px;
      }
      .btns {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }
      button {
        border: none;
        border-radius: 999px;
        padding: 10px 18px;
        font-size: 14px;
        cursor: pointer;
        background: var(--accent);
        color: white;
      }
      button.secondary {
        background: #e7ecef;
        color: #22303a;
      }
      pre {
        margin: 16px 0 0;
        padding: 12px;
        background: #0e0c0b;
        color: #f6f3ee;
        border-radius: 10px;
        min-height: 110px;
        white-space: pre-wrap;
      }
      .badge {
        display: inline-block;
        background: var(--accent-2);
        color: #1c1200;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        margin-left: 10px;
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>AI Lead Finder <span class="badge">Local</span></h1>
      <p class="subtitle">Run your pipeline and export CSVs without leaving the browser.</p>
      <div class="card">
        <div class="row">
          <label>
            Search query
            <input id="gm_query" type="text" value="real estate agent" />
          </label>
          <label>
            Cities (comma separated)
            <input id="gm_cities" type="text" value="Ahmedabad, Gujarat, India" />
          </label>
        </div>
        <div class="row">
          <label>
            Max results
            <input id="gm_max" type="text" value="40" />
          </label>
          <label>
            Config path
            <input id="config_path" type="text" value="config.yaml" />
          </label>
          <label>
            Export path
            <input id="export_path" type="text" value="data/leads.csv" />
          </label>
        </div>
        <div class="checks">
          <label><input id="no_enrich" type="checkbox" checked /> No enrich</label>
          <label><input id="dry_run" type="checkbox" /> Dry run</label>
        </div>
        <div class="btns">
          <button id="run_btn">Run pipeline</button>
          <button id="export_btn" class="secondary">Export from DB</button>
          <button id="clear_btn" class="secondary">Clear output</button>
        </div>
        <pre id="output">Ready.</pre>
      </div>
    </div>
    <script>
      const output = document.getElementById("output");
      const cfg = document.getElementById("config_path");
      const exp = document.getElementById("export_path");
      const gmQuery = document.getElementById("gm_query");
      const gmCities = document.getElementById("gm_cities");
      const gmMax = document.getElementById("gm_max");
      const noEnrich = document.getElementById("no_enrich");
      const dryRun = document.getElementById("dry_run");

      function log(message) {
        output.textContent = message;
      }

      function buildParams(base) {
        const params = new URLSearchParams();
        for (const [key, value] of Object.entries(base)) {
          if (value === undefined || value === null || value === "") {
            continue;
          }
          params.append(key, value);
        }
        return params.toString();
      }

      document.getElementById("run_btn").addEventListener("click", async () => {
        log("Running...");
        const params = buildParams({
          config_path: cfg.value || "config.yaml",
          export: exp.value || "",
          gm_query: gmQuery.value || "",
          gm_cities: gmCities.value || "",
          gm_max_results: gmMax.value || "",
          no_enrich: noEnrich.checked ? "true" : "false",
          dry_run: dryRun.checked ? "true" : "false",
        });
        try {
          const res = await fetch(`/run?${params}`, { method: "POST" });
          const data = await res.json();
          log(JSON.stringify(data, null, 2));
        } catch (err) {
          log(`Error: ${err}`);
        }
      });

      document.getElementById("export_btn").addEventListener("click", async () => {
        log("Exporting...");
        const params = buildParams({
          out: exp.value || "data/leads.csv",
          config_path: cfg.value || "config.yaml",
        });
        try {
          const res = await fetch(`/export?${params}`, { method: "POST" });
          const data = await res.json();
          log(JSON.stringify(data, null, 2));
        } catch (err) {
          log(`Error: ${err}`);
        }
      });

      document.getElementById("clear_btn").addEventListener("click", () => {
        log("Ready.");
      });
    </script>
  </body>
</html>
    """.strip()
    return Response(html, mimetype="text/html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/config")
def get_config():
    config_path = request.args.get("config_path", "config.yaml")
    cfg = load_config(config_path)
    return jsonify(cfg)


@app.post("/run")
def run():
    try:
        config_path = request.args.get("config_path", "config.yaml")
        export = request.args.get("export") or None
        no_enrich = request.args.get("no_enrich", "false").lower() in ("1", "true", "yes", "y")
        dry_run = request.args.get("dry_run", "false").lower() in ("1", "true", "yes", "y")
        gm_query = request.args.get("gm_query") or None
        gm_cities = request.args.get("gm_cities") or None
        gm_max_results = request.args.get("gm_max_results")

        cfg = load_config(config_path)
        if no_enrich:
            cfg["enrichment"]["fetch_website_for_email"] = False
        if gm_query or gm_cities or gm_max_results is not None:
            gm = cfg.setdefault("sources", {}).setdefault("google_maps_browser", {})
            gm["enabled"] = True
            if gm_query:
                gm["query"] = gm_query
            if gm_cities is not None:
                cities = [c.strip() for c in gm_cities.split(",") if c.strip()]
                gm["cities"] = cities
            if gm_max_results is not None and gm_max_results != "":
                gm["max_results"] = int(gm_max_results)

        _persist_google_maps_settings(config_path, gm_query, gm_cities, gm_max_results)

        stats = run_pipeline(cfg, export_path=export, dry_run=dry_run)
        return jsonify(stats)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/export")
def export():
    try:
        out = request.args.get("out")
        if not out:
            return jsonify({"error": "Missing 'out' parameter."}), 400
        config_path = request.args.get("config_path", "config.yaml")
        cfg = load_config(config_path)
        store = LeadStore(cfg["app"]["db_path"])
        store.init_db()
        store.export_csv(out)
        return jsonify({"exported_to": out})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def main():
    app.run(host="127.0.0.1", port=8000, debug=False)


if __name__ == "__main__":
    main()
