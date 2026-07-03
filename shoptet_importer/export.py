from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

HEADERS = [
    "code", "pairCode", "name", "price",
    "shortDescription", "description", "supplier", "manufacturer", "itemType",
    "productNumber", "partNumber", "defaultCategory", "standardPrice", "purchasePrice",
    "purchasePriceIncludingVat", "currency", "includingVat", "percentVat", "stock",
    "availabilityOutOfStock", "availabilityInStock", "unit", "warranty", "productVisibility",
    "seoTitle", "metaDescription",
    "filteringProperty:Výrobca", "filteringProperty:Výkon", "filteringProperty:Chladivo", "filteringProperty:Typ",
    "internalNote",
]

# Mapovanie názvov s diakritikou v Shoptet filtroch na interné atribúty.
HEADER_ALIASES = {
    "filteringProperty:Výrobca": "filteringProperty_Vyrobca",
    "filteringProperty:Výkon": "filteringProperty_Vykon",
    "filteringProperty:Chladivo": "filteringProperty_Chladivo",
    "filteringProperty:Typ": "filteringProperty_Typ",
}


def row_for(product: Any, headers: list[str] = HEADERS) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for h in headers:
        attr = HEADER_ALIASES.get(h, h)
        value = getattr(product, attr, "")
        if isinstance(value, float):
            value = f"{value:.2f}".rstrip("0").rstrip(".")
        out[h] = value
    return out


def write_csv(products: list[Any], out_path: Path, headers: list[str] = HEADERS) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers, delimiter=";")
        writer.writeheader()
        for p in products:
            writer.writerow(row_for(p, headers))


def write_report(products: list[Any], skipped: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["type", "page", "code", "model", "reason", "name_or_raw"]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers, delimiter=";")
        writer.writeheader()
        for p in products:
            writer.writerow({
                "type": "imported",
                "page": getattr(p, "page", ""),
                "code": p.code,
                "model": p.productNumber,
                "reason": "ok",
                "name_or_raw": p.name,
            })
        for s in skipped:
            writer.writerow({
                "type": "skipped",
                "page": s.get("page", ""),
                "code": s.get("code", ""),
                "model": s.get("model", ""),
                "reason": s.get("reason", ""),
                "name_or_raw": s.get("raw_name", ""),
            })
