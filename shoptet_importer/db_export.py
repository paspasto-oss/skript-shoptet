from __future__ import annotations

import csv
import json
import re
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


def _safe_text(value: Any, max_len: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if max_len and len(text) > max_len:
        return text[:max_len].rstrip()
    return text


def _safe_html(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _number(value: Any, fallback: float = 0.0) -> str:
    try:
        val = float(value or 0)
    except Exception:
        val = fallback
    return f"{val:.2f}".rstrip("0").rstrip(".")


def product_row_to_shoptet(row: sqlite3.Row) -> dict[str, str]:
    params = {}
    try:
        params = json.loads(row["parameters_json"] or "{}")
    except Exception:
        params = {}

    price = float(row["sale_price"] or 0)
    purchase_price = float(row["purchase_price"] or 0)
    standard_price = float(row["standard_price"] or 0)
    if price <= 0 and standard_price > 0:
        price = standard_price
    if price <= 0 and purchase_price > 0:
        price = round(purchase_price * 1.35, 2)

    name = _safe_text(row["name"], 255)
    code = _safe_text(row["code"], 64)
    category = _safe_text(row["category"] or "Produkty", 255)
    unit = _safe_text(row["unit"] or "ks", 16)
    vat_rate = int(row["vat_rate"] or 23)
    model = _safe_text(row["model"] or row["supplier_code"] or code, 128)

    internal_parts = [
        f"Zdroj: {row['source'] or ''}",
        f"Nakupna cena: {_number(purchase_price)} {row['currency'] or 'EUR'}",
    ]
    if row["source_page"]:
        internal_parts.append(f"Strana: {row['source_page']}")
    if params:
        internal_parts.append("Parametre: " + json.dumps(params, ensure_ascii=False))

    return {
        "code": code,
        "pairCode": code,
        "name": name,
        "price": _number(price),
        "shortDescription": _safe_text(row["short_description"], 255),
        "description": _safe_html(row["description"]),
        "supplier": _safe_text(row["supplier"], 128),
        "manufacturer": _safe_text(row["manufacturer"], 128),
        "itemType": "product",
        "productNumber": model,
        "partNumber": model,
        "defaultCategory": category,
        "standardPrice": _number(standard_price),
        "purchasePrice": _number(purchase_price),
        "purchasePriceIncludingVat": "0",
        "currency": _safe_text(row["currency"] or "EUR", 3),
        "includingVat": "0",
        "percentVat": str(vat_rate),
        "stock": _number(row["stock"]),
        "availabilityOutOfStock": _safe_text(row["availability_out_of_stock"] or "Na objednávku", 64),
        "availabilityInStock": _safe_text(row["availability_in_stock"] or "Skladom", 64),
        "unit": unit,
        "productVisibility": "visible" if row["active"] else "hidden",
        "seoTitle": _safe_text(row["seo_title"] or name, 70),
        "metaDescription": _safe_text(row["meta_description"], 155),
        "image": _safe_text(row["image_url"], 512),
        "internalNote": _safe_text(" | ".join(x for x in internal_parts if x), 2048),
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
