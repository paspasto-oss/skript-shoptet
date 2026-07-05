from __future__ import annotations

import html
import json
import sqlite3
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def _text(value: Any) -> str:
    return str(value or "").strip()


def _price(value: Any) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except Exception:
        return "0.00"


def _params(raw: str | None) -> dict[str, Any]:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def _cdata(parent: ET.Element, tag: str, value: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    # ElementTree nema nativne CDATA. Shoptet HTML prijme aj escapovane HTML.
    el.text = value or ""
    return el


def _sub(parent: ET.Element, tag: str, value: Any = "") -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = _text(value)
    return el


def product_row_to_shopitem(row: sqlite3.Row) -> ET.Element:
    code = _text(row["code"])
    name = _text(row["name"])
    category = _text(row["category"] or "Produkty")
    vat = int(row["vat_rate"] or 23)
    price_vat = float(row["sale_price"] or 0)
    purchase_price = float(row["purchase_price"] or 0)
    description = _text(row["description"]) or f"<h2>{html.escape(name)}</h2><p>Produkt importovaný z cenníka dodávateľa.</p>"
    short_description = _text(row["short_description"]) or f"<p>{html.escape(name)}</p>"
    params = _params(row["parameters_json"])

    item = ET.Element("SHOPITEM")
    _sub(item, "NAME", name)
    _cdata(item, "SHORT_DESCRIPTION", short_description)
    _cdata(item, "DESCRIPTION", description)
    _sub(item, "ADULT", "0")
    _sub(item, "ITEM_TYPE", "product")

    categories = ET.SubElement(item, "CATEGORIES")
    _sub(categories, "CATEGORY", category)
    _sub(categories, "DEFAULT_CATEGORY", category)

    images = ET.SubElement(item, "IMAGES")
    image_url = _text(row["image_url"])
    if image_url:
        _sub(images, "IMAGE", image_url)

    props = ET.SubElement(item, "TEXT_PROPERTIES")
    pairs: list[tuple[str, str]] = []
    for key, label in [
        ("vykon", "Výkon"),
        ("teplota", "Otváracia teplota"),
        ("cerpadlo", "Čerpadlo"),
        ("pripojenie", "Pripojenie"),
        ("chladivo", "Chladivo"),
        ("marza", "Marža"),
    ]:
        if params.get(key):
            pairs.append((label, _text(params.get(key))))
    if row["manufacturer"]:
        pairs.append(("Výrobca", _text(row["manufacturer"])))
    if row["model"]:
        pairs.append(("Model", _text(row["model"])))
    pairs.append(("Kód produktu", code))

    seen: set[str] = set()
    for label, value in pairs:
        if not label or not value:
            continue
        if label.lower() in seen:
            continue
        seen.add(label.lower())
        prop = ET.SubElement(props, "TEXT_PROPERTY")
        _sub(prop, "NAME", label)
        _sub(prop, "VALUE", value)
        _sub(prop, "DESCRIPTION", "")

    _sub(item, "VISIBILITY", "visible" if row["active"] else "hidden")
    _sub(item, "UNIT", _text(row["unit"] or "ks"))
    _sub(item, "CODE", code)
    _sub(item, "CURRENCY", _text(row["currency"] or "EUR"))
    _sub(item, "VAT", str(vat))
    _sub(item, "PRICE_VAT", _price(price_vat))
    _sub(item, "PURCHASE_PRICE", _price(purchase_price))
    _sub(item, "PURCHASE_VAT", str(vat))
    _sub(item, "PURCHASE_PRICE_INCL_VAT", "0")
    _sub(item, "STANDARD_PRICE", _price(row["standard_price"]) if row["standard_price"] else "")

    stock = ET.SubElement(item, "STOCK")
    _sub(stock, "AMOUNT", _price(row["stock"]))
    _sub(stock, "LOCATION", "")
    _sub(stock, "MINIMAL_AMOUNT", "")
    _sub(stock, "MAXIMAL_AMOUNT", "")

    _sub(item, "VISIBLE", "1" if row["active"] else "0")
    _sub(item, "DECIMAL_COUNT", "0")
    _sub(item, "NEGATIVE_AMOUNT", "1")
    _sub(item, "PRICE_RATIO", "1")
    _sub(item, "APPLY_LOYALTY_DISCOUNT", "0")
    _sub(item, "APPLY_VOLUME_DISCOUNT", "0")
    _sub(item, "APPLY_QUANTITY_DISCOUNT", "0")
    _sub(item, "APPLY_DISCOUNT_COUPON", "0")
    _sub(item, "INTERNAL_NOTE", f"Zdroj: {_text(row['source'])}")
    return item


def export_db_to_shoptet_xml(db_path: str | Path, out_path: str | Path, active_only: bool = True) -> int:
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

        shop = ET.Element("SHOP")
        for row in rows:
            shop.append(product_row_to_shopitem(row))

        tree = ET.ElementTree(shop)
        ET.indent(tree, space="  ", level=0)
        tree.write(out_path, encoding="utf-8", xml_declaration=True)
        return len(rows)
    finally:
        conn.close()
