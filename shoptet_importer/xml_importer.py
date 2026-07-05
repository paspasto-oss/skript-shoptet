from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from .ai_content import generate_basic_content
from .product_model import UniversalProduct


FIELD_ALIASES = {
    "code": ["CODE", "SKU", "ITEM_ID", "PRODUCTNO", "PRODUCT_NO", "ID"],
    "name": ["NAME", "PRODUCTNAME", "PRODUCT_NAME", "TITLE"],
    "description": ["DESCRIPTION", "DESC", "TEXT"],
    "manufacturer": ["MANUFACTURER", "BRAND", "VYROBCA"],
    "supplier": ["SUPPLIER", "DODAVATEL"],
    "model": ["MODEL", "PARTNO", "PART_NO"],
    "ean": ["EAN", "BARCODE"],
    "purchase_price": ["PURCHASE_PRICE", "BUY_PRICE", "PRICE_BUY", "NAKUP"],
    "sale_price": ["PRICE", "PRICE_VAT", "SALE_PRICE", "SELL_PRICE"],
    "category": ["CATEGORY", "CATEGORYTEXT", "CATEGORY_TEXT"],
    "image": ["IMGURL", "IMAGE", "IMAGE_URL", "PICTURE"],
}


def norm(tag: str) -> str:
    return tag.split("}")[-1].upper().replace("-", "_").replace(" ", "_")


def parse_float(value: str | None) -> float:
    if not value:
        return 0.0
    text = value.strip().replace("€", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def first_text(item: ET.Element, aliases: list[str]) -> str:
    aliases_norm = {a.upper() for a in aliases}
    for child in item.iter():
        if child is item:
            continue
        if norm(child.tag) in aliases_norm and child.text:
            return child.text.strip()
    return ""


def candidate_items(root: ET.Element) -> list[ET.Element]:
    names = {"SHOPITEM", "ITEM", "PRODUCT", "PRODUCTITEM"}
    found = [el for el in root.iter() if norm(el.tag) in names]
    if found:
        return found
    return list(root)


def import_xml_products(path: str | Path, default_supplier: str = "", default_manufacturer: str = "", limit: int | None = None) -> tuple[list[UniversalProduct], list[dict]]:
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()
    products: list[UniversalProduct] = []
    skipped: list[dict] = []

    for index, item in enumerate(candidate_items(root), start=1):
        code = first_text(item, FIELD_ALIASES["code"])
        name = first_text(item, FIELD_ALIASES["name"])
        if not code or not name:
            skipped.append({"row": index, "reason": "missing_code_or_name"})
            continue

        purchase = parse_float(first_text(item, FIELD_ALIASES["purchase_price"]))
        sale = parse_float(first_text(item, FIELD_ALIASES["sale_price"]))
        if sale <= 0:
            sale = round(purchase * 1.35, 2) if purchase > 0 else 0.0

        product = UniversalProduct(
            code=code,
            name=name,
            supplier=first_text(item, FIELD_ALIASES["supplier"]) or default_supplier,
            manufacturer=first_text(item, FIELD_ALIASES["manufacturer"]) or default_manufacturer,
            supplier_code=code,
            model=first_text(item, FIELD_ALIASES["model"]),
            ean=first_text(item, FIELD_ALIASES["ean"]),
            category=first_text(item, FIELD_ALIASES["category"]) or "Produkty",
            purchase_price=purchase,
            sale_price=sale,
            standard_price=sale,
            image_url=first_text(item, FIELD_ALIASES["image"]),
            description=first_text(item, FIELD_ALIASES["description"]),
            source=f"xml:{path.name}",
        )
        products.append(generate_basic_content(product))
        if limit and len(products) >= limit:
            break

    return products, skipped
