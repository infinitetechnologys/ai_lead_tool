import argparse
import sys

from .config import load_config
from .db import LeadStore
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Lead Finder Tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="Initialize the SQLite database")
    p_init.add_argument("--config", default="config.yaml")

    p_run = sub.add_parser("run", help="Run lead collection pipeline")
    p_run.add_argument("--config", default="config.yaml")
    p_run.add_argument("--export", default="", help="Export CSV path (overrides config)")
    p_run.add_argument("--no-enrich", action="store_true", help="Disable website enrichment")
    p_run.add_argument("--dry-run", action="store_true", help="Do not write to DB")

    p_export = sub.add_parser("export", help="Export leads from DB to CSV")
    p_export.add_argument("--config", default="config.yaml")
    p_export.add_argument("--out", required=True, help="CSV output path")

    p_cfg = sub.add_parser("print-config", help="Print merged config")
    p_cfg.add_argument("--config", default="config.yaml")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.command == "init-db":
        store = LeadStore(cfg["app"]["db_path"])
        store.init_db()
        print(f"Initialized DB at {cfg['app']['db_path']}")
        return

    if args.command == "run":
        if args.no_enrich:
            cfg["enrichment"]["fetch_website_for_email"] = False
        export_path = args.export or ""
        stats = run_pipeline(cfg, export_path=export_path or None, dry_run=args.dry_run)
        print("Run complete:")
        print(f"  Fetched: {stats['fetched']}")
        print(f"  Kept:    {stats['kept']}")
        print(f"  Saved:   {stats['saved']}")
        if stats.get("exported_to"):
            print(f"  Export:  {stats['exported_to']}")
        return

    if args.command == "export":
        store = LeadStore(cfg["app"]["db_path"])
        store.init_db()
        store.export_csv(args.out)
        print(f"Exported CSV to {args.out}")
        return

    if args.command == "print-config":
        import yaml
        print(yaml.safe_dump(cfg, sort_keys=False))
        return

    parser.print_help()
    sys.exit(2)
