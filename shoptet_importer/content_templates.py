from __future__ import annotations

import html
import re
from typing import Any

from .product_model import UniversalProduct


LABELS = {
    "vykon": "Výkon",
    "teplota": "Otváracia teplota",
    "cerpadlo": "Čerpadlo",
    "pripojenie": "Pripojenie",
    "chladivo": "Chladivo",
}


def _escape(value: Any) -> str:
    return html.escape(str(value or "").strip())


def normalize_brand_prefix(name: str, manufacturer: str) -> str:
    """Odstrani dvojity vyrobca v nazve, napr. Blumut Blumut -> BLUMUT."""
    value = re.sub(r"\s+", " ", str(name or "")).strip()
    if not value:
        return value

    if manufacturer.upper() == "BLUMUT":
        value = re.sub(r"(?i)^blumut\s+blumut\b", "BLUMUT", value)
        value = re.sub(r"(?i)^blumut\b", "BLUMUT", value)
    elif manufacturer:
        pattern = rf"(?i)^{re.escape(manufacturer)}\s+{re.escape(manufacturer)}\b"
        value = re.sub(pattern, manufacturer, value)
    return value.replace("Copmact", "Compact")


def clean_text(value: str) -> str:
    return normalize_brand_prefix(value.replace("Copmact", "Compact"), "BLUMUT")


def build_product_description(product: UniversalProduct) -> str:
    params = product.parameters or {}
    popis = params.get("popis") or product.short_description or product.name
    rows = [
        ("Výrobca", product.manufacturer),
        ("Dodávateľ", product.supplier),
        ("Kód produktu", product.code),
        ("Model", product.model),
    ]
    for key in ["vykon", "teplota", "cerpadlo", "pripojenie", "chladivo"]:
        if params.get(key):
            rows.append((LABELS.get(key, key.capitalize()), params[key]))

    table_rows = "".join(
        f"<tr><th>{_escape(label)}</th><td>{_escape(value)}</td></tr>" for label, value in rows if value
    )
    return (
        f"<h2>{_escape(product.name)}</h2>"
        f"<p>{_escape(popis)}</p>"
        f"<table><tbody>{table_rows}</tbody></table>"
    )


def enrich_product_content(product: UniversalProduct) -> UniversalProduct:
    product.name = normalize_brand_prefix(product.name, product.manufacturer)
    if product.model:
        product.model = clean_text(product.model)
    if product.short_description:
        product.short_description = clean_text(product.short_description)

    if not product.short_description:
        product.short_description = " / ".join(x for x in [product.manufacturer, product.model, product.category] if x)[:255]
    product.short_description = normalize_brand_prefix(product.short_description, product.manufacturer)

    product.seo_title = product.name[:70]
    product.meta_description = f"{product.name} – kód {product.code}. Produkt pre vykurovanie a technické inštalácie."[:155]
    product.description = build_product_description(product)
    return product
