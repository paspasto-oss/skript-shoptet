#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from shoptet_importer.database import ProductDatabase
from shoptet_importer.generic_pdf import extract_products_generic


def main() -> int:
    parser = argparse.ArgumentParser(description="Univerzalny PDF cennik -> SQLite produktova databaza")
    parser.add_argument("--pdf", required=True, help="Cesta k PDF cenniku")
    parser.add_argument("--db", default="data/products.sqlite", help="Cesta k SQLite databaze")
    parser.add_argument("--limit", type=int, default=None, help="Testovaci limit produktov")
    args = parser.parse_args()

    products, skipped = extract_products_generic(Path(args.pdf), limit=args.limit)
    if not products:
        raise SystemExit("Parser nenasiel ziadne produkty. Treba doplnit pravidlo pre tento format PDF.")

    db = ProductDatabase(args.db)
    try:
        imported = db.upsert_many(products)
        db.log_import(str(args.pdf), imported, len(skipped))
    finally:
        db.close()

    print(f"Hotovo: {imported} produktov ulozenych do databazy {args.db}")
    print(f"Preskocene riadky: {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
