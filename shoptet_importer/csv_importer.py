from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .ai_content import generate_basic_content
from .product_model import UniversalProduct


COLUMN_ALIASES = {
    "code": ["code", "kod", "kód", "sku", "obj. č.", "objednavacie cislo", "objednávacie číslo"],
    "name": ["name", "nazov", "názov", "produkt", "popis"],
    "manufacturer": ["vyrobca", "výrobca", "manufacturer", "brand", "znacka", "značka"],
    "supplier": ["dodavatel", "dodávateľ", "supplier"],
    "model": ["model", "objednavaci nazov", "objednávací názov", "partnumber"],
    "purchase_price": ["nakup", "nákup", "nakupna cena", "nákupná cena", "purchaseprice", "cena bez dph", "cena"],
    "sale_price": ["predaj", "predajna cena", "predajná cena", "price", "moc", "odporucana cena", "odporúčaná cena"],
    "category": ["kategoria", "kategória", "category", "defaultcategory"],
    "ean": ["ean", "barcode"],
}


def normalize_header(value: str) -> str:
    return value.strip().lower().replace("_", " ").replace("-", " ")


def detect_delimiter(path: Path) -> str:
    sample = path.read_text(encoding="utf-8-sig", errors="ignore")[:4096]
    if sample.count(";") >= sample.count(","):
        return ";"
    return ","


def map_headers(headers: list[str]) -> dict[str, str]:
    normalized = {normalize_header(h): h for h in headers}
    result: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[field] = normalized[alias]
                break
    return result


def parse_float(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace("€", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def import_csv_products(path: str | Path, default_supplier: str = "", default_manufacturer: str = "", limit: int | None = None) -> tuple[list[UniversalProduct], list[dict]]:
    path = Path(path)
    delimiter = detect_delimiter(path)
    products: list[UniversalProduct] = []
    skipped: list[dict] = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            return [], [{"reason": "missing_headers", "file": str(path)}]
        header_map = map_headers(reader.fieldnames)
        for index, row in enumerate(reader, start=2):
            code = str(row.get(header_map.get("code", ""), "")).strip()
            name = str(row.get(header_map.get("name", ""), "")).strip()
            if not code or not name:
                skipped.append({"row": index, "reason": "missing_code_or_name", "raw": dict(row)})
                continue

            purchase = parse_float(row.get(header_map.get("purchase_price", ""), 0))
            sale = parse_float(row.get(header_map.get("sale_price", ""), 0))
            if sale <= 0:
                sale = round(purchase * 1.35, 2) if purchase > 0 else 0.0

            product = UniversalProduct(
                code=code,
                name=name,
                supplier=str(row.get(header_map.get("supplier", ""), default_supplier)).strip() or default_supplier,
                manufacturer=str(row.get(header_map.get("manufacturer", ""), default_manufacturer)).strip() or default_manufacturer,
                supplier_code=code,
                model=str(row.get(header_map.get("model", ""), "")).strip(),
                ean=str(row.get(header_map.get("ean", ""), "")).strip(),
                category=str(row.get(header_map.get("category", ""), "Produkty")).strip() or "Produkty",
                purchase_price=purchase,
                sale_price=sale,
                standard_price=sale,
                source=f"csv:{path.name}",
            )
            products.append(generate_basic_content(product))
            if limit and len(products) >= limit:
                break

    return products, skipped
