#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from shoptet_importer.db_export import export_db_to_shoptet_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite produktova databaza -> Shoptet CSV")
    parser.add_argument("--db", default="data/products.sqlite", help="Cesta k SQLite databaze")
    parser.add_argument("--out", default="output/shoptet_products.csv", help="Vystupny CSV subor pre Shoptet")
    parser.add_argument("--all", action="store_true", help="Exportovat aj neaktivne produkty")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"Databaza neexistuje: {db_path}")

    count = export_db_to_shoptet_csv(db_path, args.out, active_only=not args.all)
    print(f"Hotovo: {count} produktov exportovanych do {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
