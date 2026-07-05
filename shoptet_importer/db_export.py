from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


# Minimalny import pre Shoptet: pouzivame iba polia, ktore potrebujeme pre zalozenie produktu.
# Dolezite: textProperty obsahuje bodkociarku vo vnutri hodnoty, preto exportujeme QUOTE_ALL.
SHOPTET_HEADERS = [
    "code",
    "pairCode",
    "name",
    "shortDescription",
    "description",
    "manufacturer",
    "supplier",
    "metaDescription",
    "itemType",
    "ean",
    "productNumber",
    "partNumber",
    "defaultCategory",
    "categoryText",
    "price",
    "standardPrice",
    "purchasePrice",
    "purchasePriceVatRate",
    "purchasePriceIncludingVat",
    "currency",
    "includingVat",
    "percentVat",
    "stock",
    "negativeAmount",
    "availabilityOutOfStock",
    "availabilityInStock",
    "unit",
    "decimalCount",
    "textProperty",
    "textProperty2",
    "textProperty3",
    "textProperty4",
    "textProperty5",
    "textProperty6",
    "textProperty7",
    "textProperty8",
    "textProperty9",
    "textProperty10",
    "textProperty11",
    "textProperty12",
    "productVisibility",
    "adult",
    "seoTitle",
    "heurekaHidden",
    "heurekaCartHidden",
    "zboziHidden",
    "arukeresoHidden",
    "arukeresoMarketplaceHidden",
    "internalNote",
]

PARAM_LABELS = {
    "vykon": "Výkon",
    "teplota": "Otváracia teplota",
    "cerpadlo": "Čerpadlo",
    "pripojenie": "Pripojenie",
    "chladivo": "Chladivo",
    "popis": "Popis",
}


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
    return f"{val:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _params_from_json(raw: str | None) -> dict[str, Any]:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def _text_properties(params: dict[str, Any], manufacturer: str, model: str, code: str) -> list[str]:
    items: list[tuple[str, str]] = []
    for key in ["vykon", "teplota", "cerpadlo", "pripojenie", "chladivo"]:
        value = _safe_text(params.get(key))
        if value:
            items.append((PARAM_LABELS.get(key, key), value))

    if manufacturer:
        items.append(("Výrobca", manufacturer))
    if model:
        items.append(("Model", model))
    if code:
        items.append(("Kód produktu", code))

    seen: set[str] = set()
    result: list[str] = []
    for label, value in items:
        label = _safe_text(label, 64)
        value = _safe_text(value, 255)
        if not label or not value:
            continue
        dedupe = label.lower()
        if dedupe in seen:
            continue
        seen.add(dedupe)
        result.append(f"{label};{value}")
        if len(result) >= 12:
            break

    if not result and code:
        result.append(f"Kód produktu;{code}")
    return result


def product_row_to_shoptet(row: sqlite3.Row) -> dict[str, str]:
    params = _params_from_json(row["parameters_json"])

    price = float(row["sale_price"] or 0)
    purchase_price = float(row["purchase_price"] or 0)
    standard_price = float(row["standard_price"] or 0)
    if price <= 0 and standard_price > 0:
        price = standard_price
    if price <= 0 and purchase_price > 0:
        price = round(purchase_price * 1.35, 2)

    code = _safe_text(row["code"], 64)
    name = _safe_text(row["name"], 255)
    manufacturer = _safe_text(row["manufacturer"], 128)
    supplier = _safe_text(row["supplier"], 128)
    category = _safe_text(row["category"] or "Produkty", 255)
    model = _safe_text(row["model"] or row["supplier_code"] or code, 128)
    description = _safe_html(row["description"])
    short_description = _safe_html(row["short_description"])

    if not description:
        description = f"<h2>{name}</h2><p>{short_description or name}</p>"
    if not short_description:
        short_description = f"<p>{name}</p>"

    result = {header: "" for header in SHOPTET_HEADERS}
    result.update({
        "code": code,
        "pairCode": code,
        "name": name,
        "shortDescription": short_description,
        "description": description,
        "manufacturer": manufacturer,
        "supplier": supplier,
        "metaDescription": _safe_text(row["meta_description"] or f"{name} – kód {code}.", 155),
        "itemType": "product",
        "ean": _safe_text(row["ean"], 32) if "ean" in row.keys() else "",
        "productNumber": model,
        "partNumber": model,
        "defaultCategory": category,
        "categoryText": category,
        "price": _number(price),
        "standardPrice": _number(standard_price) if standard_price > 0 else "",
        "purchasePrice": _number(purchase_price) if purchase_price > 0 else "",
        "purchasePriceVatRate": str(int(row["vat_rate"] or 23)),
        "purchasePriceIncludingVat": "0",
        "currency": _safe_text(row["currency"] or "EUR", 3),
        "includingVat": "1",
        "percentVat": str(int(row["vat_rate"] or 23)),
        "stock": _number(row["stock"]),
        "negativeAmount": "1",
        "availabilityOutOfStock": _safe_text(row["availability_out_of_stock"] or "Na objednávku", 64),
        "availabilityInStock": _safe_text(row["availability_in_stock"] or "Skladom", 64),
        "unit": _safe_text(row["unit"] or "ks", 16),
        "decimalCount": "0",
        "productVisibility": "visible" if row["active"] else "hidden",
        "adult": "0",
        "seoTitle": _safe_text(row["seo_title"] or name, 70),
        "heurekaHidden": "0",
        "heurekaCartHidden": "0",
        "zboziHidden": "0",
        "arukeresoHidden": "0",
        "arukeresoMarketplaceHidden": "0",
        "internalNote": _safe_text(
            f"Zdroj: {row['source'] or ''} | Nakupna cena: {_number(purchase_price)} {row['currency'] or 'EUR'}"
            + (f" | Strana: {row['source_page']}" if row["source_page"] else ""),
            2048,
        ),
    })

    for i, prop in enumerate(_text_properties(params, manufacturer, model, code), start=1):
        field = "textProperty" if i == 1 else f"textProperty{i}"
        if field in result:
            result[field] = prop

    return result


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
            writer = csv.DictWriter(
                f,
                fieldnames=SHOPTET_HEADERS,
                delimiter=";",
                quotechar='"',
                quoting=csv.QUOTE_ALL,
                lineterminator="\r\n",
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(product_row_to_shoptet(row))
        return len(rows)
    finally:
        conn.close()
