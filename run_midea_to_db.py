#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from shoptet_importer.adapters import midea_products_to_universal
from shoptet_importer.database import ProductDatabase
from shoptet_importer.midea_pdf import extract_products


def main() -> int:
    parser = argparse.ArgumentParser(description="Midea/MDV PDF -> SQLite produktova databaza")
    parser.add_argument("--pdf", required=True, help="Cesta k PDF cenniku Midea/MDV")
    parser.add_argument("--db", default="data/products.sqlite", help="Cesta k SQLite databaze")
    parser.add_argument("--config", default="config.json", help="Konfiguracny JSON")
    parser.add_argument("--limit", type=int, default=None, help="Testovaci limit produktov")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}

    parsed, skipped = extract_products(Path(args.pdf), config, limit=args.limit)
    universal_products = midea_products_to_universal(parsed)

    db = ProductDatabase(args.db)
    try:
        imported = db.upsert_many(universal_products)
        db.log_import("Midea/MDV PDF", imported, len(skipped))
    finally:
        db.close()

    print(f"Hotovo: {imported} produktov ulozenych do databazy {args.db}")
    print(f"Preskocene riadky: {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
