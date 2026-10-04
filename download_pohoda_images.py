from __future__ import annotations

import argparse
from pathlib import Path

from shoptet_importer.pohoda_image_downloader import run_downloader


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stiahne produktove obrazky pre skladove karty z POHODA XML exportu."
    )
    parser.add_argument("xml", help="POHODA XML export skladu")
    parser.add_argument("--out", default="output/pohoda_obrazky", help="Vystupny priecinok")
    parser.add_argument("--all", action="store_true", help="Spracovat aj karty, ktore uz maju obrazok")
    parser.add_argument("--limit", type=int, default=None, help="Testovaci limit poctu produktov")
    args = parser.parse_args()

    results = run_downloader(
        xml_path=Path(args.xml),
        out_dir=Path(args.out),
        missing_only=not args.all,
        limit=args.limit,
    )
    ok = sum(1 for r in results if r.status == "OK")
    missing = len(results) - ok
    print(f"Hotovo. Stiahnute: {ok}. Nenajdene: {missing}.")
    print(f"Obrazky: {Path(args.out) / 'obrazky'}")
    print(f"Parovanie: {Path(args.out) / 'parovanie_obrazkov.csv'}")


if __name__ == "__main__":
    main()
