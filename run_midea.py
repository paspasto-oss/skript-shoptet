#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from shoptet_importer.export import write_csv, write_report
from shoptet_importer.midea_pdf import extract_products


def main() -> int:
    parser = argparse.ArgumentParser(description="Midea/MDV PDF -> Shoptet CSV import, iba kompletné sety.")
    parser.add_argument("--pdf", required=True, help="Cesta k PDF cenníku Midea/MDV")
    parser.add_argument("--out", default="out/shoptet_midea_sety.csv", help="Výstupný CSV súbor pre Shoptet")
    parser.add_argument("--report", default="out/kontrola_midea.csv", help="Kontrolný CSV report")
    parser.add_argument("--config", default="config.json", help="Konfiguračný JSON")
    parser.add_argument("--limit", type=int, default=None, help="Testovací limit produktov, napr. 10")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}

    products, skipped = extract_products(Path(args.pdf), config, limit=args.limit)
    if not products:
        raise SystemExit("Nenašli sa žiadne kompletné sety. Skontroluj PDF alebo pravidlá parsera.")

    codes = [p.code for p in products]
    duplicate_codes = sorted({c for c in codes if codes.count(c) > 1})
    if duplicate_codes:
        raise SystemExit(f"Duplicitné code v importe: {', '.join(duplicate_codes[:20])}")

    write_csv(products, Path(args.out))
    write_report(products, skipped, Path(args.report))

    print(f"Hotovo: {len(products)} produktov -> {args.out}")
    print(f"Kontrola: {len(skipped)} preskočených riadkov -> {args.report}")
    print("Prvé stĺpce CSV sú: code;pairCode;name;price")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
