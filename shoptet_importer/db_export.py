from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any


SHOPTET_HEADERS = [
    "code",
    "pairCode",
    "name",
    "price",
    "shortDescription",
    "description",
    "supplier",
    "manufacturer",
    "itemType",
    "productNumber",
    "partNumber",
    "defaultCategory",
    "standardPrice",
    "purchasePrice",
    "purchasePriceIncludingVat",
    "currency",
    "includingVat",
    "percentVat",
    "stock",
    "availabilityOutOfStock",
    "availabilityInStock",
    "unit",
    "productVisibility",
    "seoTitle",
    "metaDescription",
    "image",
    "internalNote",
]


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def product_row_to_shoptet(row: sqlite3.Row) -> dict[str, str]:
    params = {}
    try:
        params = json.loads(row["parameters_json"] or "{}")
    except Exception:
        params = {}

    internal_parts = [
        f"Zdroj: {row['source'] or ''}",
        f"Nakupna cena: {_fmt(row['purchase_price'])} {row['currency'] or 'EUR'}",
    ]
    if row["source_page"]:
        internal_parts.append(f"Strana: {row['source_page']}")
    if params:
        internal_parts.append("Parametre: " + json.dumps(params, ensure_ascii=False))

    return {
        "code": _fmt(row["code"]),
        "pairCode": _fmt(row["code"]),
        "name": _fmt(row["name"]),
        "price": _fmt(row["sale_price"]),
        "shortDescription": _fmt(row["short_description"]),
        "description": _fmt(row["description"]),
        "supplier": _fmt(row["supplier"]),
        "manufacturer": _fmt(row["manufacturer"]),
        "itemType": "product",
        "productNumber": _fmt(row["model"] or row["supplier_code"]),
        "partNumber": _fmt(row["model"] or row["supplier_code"]),
        "defaultCategory": _fmt(row["category"]),
        "standardPrice": _fmt(row["standard_price"]),
        "purchasePrice": _fmt(row["purchase_price"]),
        "purchasePriceIncludingVat": "0",
        "currency": _fmt(row["currency"] or "EUR"),
        "includingVat": "0",
        "percentVat": _fmt(row["vat_rate"] or 23),
        "stock": _fmt(row["stock"]),
        "availabilityOutOfStock": _fmt(row["availability_out_of_stock"]),
        "availabilityInStock": _fmt(row["availability_in_stock"]),
        "unit": _fmt(row["unit"] or "ks"),
        "productVisibility": "visible" if row["active"] else "hidden",
        "seoTitle": _fmt(row["seo_title"]),
        "metaDescription": _fmt(row["meta_description"]),
        "image": _fmt(row["image_url"]),
        "internalNote": " | ".join(x for x in internal_parts if x),
    }


def export_db_to_shoptet_csv(db_path: str | Path, out_path: str | Path, active_only: bool = True) -> int:
    db_path = Path(db_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM products"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY manufacturer, category, name"
        rows = list(conn.execute(sql))

        with out_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=SHOPTET_HEADERS, delimiter=";")
            writer.writeheader()
            for row in rows:
                writer.writerow(product_row_to_shoptet(row))
        return len(rows)
    finally:
        conn.close()
