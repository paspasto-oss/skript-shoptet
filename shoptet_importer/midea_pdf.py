from __future__ import annotations

import html
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

CMID_RE = re.compile(r"^(CMID\d{6})\s+(\S+)\s+(.+)$")
PRICE_RE = re.compile(r"^\d[\d\s]*\s*€$")
POWER_RE = re.compile(r"(\d{1,2}(?:[,.]\d+)?)\s*kW", re.I)
REFRIGERANT_RE = re.compile(r"\b(R32|R290|R410A|R134A)\b", re.I)

@dataclass
class Product:
    page: int
    code: str
    pairCode: str
    name: str
    raw_name: str
    model: str
    shortDescription: str
    description: str
    manufacturer: str
    supplier: str
    itemType: str
    productNumber: str
    partNumber: str
    defaultCategory: str
    price: float
    standardPrice: float
    purchasePrice: float
    purchasePriceIncludingVat: int
    currency: str
    includingVat: int
    percentVat: int
    stock: int
    availabilityOutOfStock: str
    availabilityInStock: str
    unit: str
    warranty: str
    productVisibility: str
    seoTitle: str
    metaDescription: str
    internalNote: str
    filteringProperty_Vyrobca: str
    filteringProperty_Vykon: str
    filteringProperty_Chladivo: str
    filteringProperty_Typ: str


def clean(text: str) -> str:
    text = text.replace("\xa0", " ")
    fixes = {
        "jedotka": "jednotka",
        "vút.": "vnút.",
        "kánálová": "kanálová",
        "3 fázis": "3 fázy",
    }
    for bad, good in fixes.items():
        text = text.replace(bad, good)
    return re.sub(r"\s+", " ", text).strip()


def parse_price(text: str) -> float | None:
    digits = re.sub(r"\D", "", text)
    return float(digits) if digits else None


def is_complete_set(raw_name: str) -> bool:
    name = raw_name.lower()
    # B2C prvá fáza: len kompletné zostavy, nie samostatné vnútorné/vonkajšie jednotky.
    include = any(x in name for x in ["split", "monoblok"])
    exclude = any(x in name for x in ["vnút. jed", "vonk. jed", "rámček", "ovládač"])
    return include and not exclude


def category_for(page: int, raw_name: str) -> str:
    n = raw_name.lower()
    if "monoblok" in n or page >= 12:
        return "Tepelné čerpadlá > Midea"
    if "kazet" in n:
        return "Klimatizácie > Midea > Kazetové splity"
    if "kanál" in n or "kanal" in n:
        return "Klimatizácie > Midea > Kanálové splity"
    if "podstrop" in n or "parapet" in n:
        return "Klimatizácie > Midea > Podstropno-parapetné splity"
    if page in (2, 3, 4, 5):
        return "Klimatizácie > Midea > Nástenné monosplity"
    return "Klimatizácie > Midea"


def warranty_for(page: int, raw_name: str) -> str:
    if "monoblok" in raw_name.lower() or page >= 12:
        return "36 mesiacov"
    return "60 mesiacov"


def display_name(manufacturer: str, raw_name: str) -> str:
    # Zachová modelový názov z katalógu, ale pridá výrobcu na začiatok.
    return f"{manufacturer} {raw_name}"


def build_description(product_name: str, manufacturer: str, supplier: str, model: str, code: str, power: str, refrigerant: str, warranty: str) -> str:
    rows = [
        ("Výrobca", manufacturer),
        ("Dodávateľ", supplier),
        ("Model", model),
        ("Kód dodávateľa", code),
    ]
    if power:
        rows.append(("Výkon", power))
    if refrigerant:
        rows.append(("Chladivo", refrigerant))
    rows.append(("Záruka", warranty))
    lis = "".join(f"<li><strong>{html.escape(k)}:</strong> {html.escape(v)}</li>" for k, v in rows)
    return (
        f"<h2>{html.escape(product_name)}</h2>"
        "<p>Kompletná zostava Midea určená na chladenie a vykurovanie. "
        "Produkt bol pripravený automatickým importom z dodávateľského cenníka.</p>"
        f"<ul>{lis}</ul>"
    )


def extract_products(pdf_path: Path, config: dict[str, Any], limit: int | None = None) -> tuple[list[Product], list[dict[str, Any]]]:
    doc = fitz.open(str(pdf_path))
    products: list[Product] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()

    manufacturer = config.get("manufacturer", "Midea")
    supplier = config.get("supplier", "Planning & Trading Slovakia s.r.o.")
    price_mode = config.get("price_mode", "recommended")
    multiplier = float(config.get("margin_multiplier", 2.15))

    for page_no, page in enumerate(doc, start=1):
        lines = [clean(x) for x in page.get_text().splitlines() if clean(x)]
        for i, line in enumerate(lines):
            m = CMID_RE.match(line)
            if not m:
                continue
            code, model, raw_name = m.groups()
            raw_name = clean(raw_name)

            if config.get("only_complete_sets", True) and not is_complete_set(raw_name):
                skipped.append({"page": page_no, "code": code, "model": model, "reason": "not_complete_set", "raw_name": raw_name})
                continue
            if code in seen:
                skipped.append({"page": page_no, "code": code, "model": model, "reason": "duplicate_code", "raw_name": raw_name})
                continue
            seen.add(code)

            prices: list[float] = []
            for j in range(i + 1, min(len(lines), i + 14)):
                if PRICE_RE.match(lines[j]):
                    price = parse_price(lines[j])
                    if price is not None:
                        prices.append(price)
                    if len(prices) == 2:
                        break
            if len(prices) != 2:
                skipped.append({"page": page_no, "code": code, "model": model, "reason": "missing_two_prices", "raw_name": raw_name})
                continue

            purchase_price, recommended_price = prices
            if price_mode == "margin":
                sell_price = round(purchase_price * multiplier, 2)
            else:
                sell_price = recommended_price

            power_match = POWER_RE.search(raw_name)
            refrigerant_match = REFRIGERANT_RE.search(raw_name)
            power = (power_match.group(1).replace(".", ",") + " kW") if power_match else ""
            refrigerant = refrigerant_match.group(1).upper() if refrigerant_match else ""
            warranty = warranty_for(page_no, raw_name)
            name = display_name(manufacturer, raw_name)
            short = " / ".join(x for x in [manufacturer, model, power, refrigerant] if x)
            desc = build_description(name, manufacturer, supplier, model, code, power, refrigerant, warranty)

            products.append(Product(
                page=page_no,
                code=code,
                pairCode="",
                name=name,
                raw_name=raw_name,
                model=model,
                shortDescription=short,
                description=desc,
                manufacturer=manufacturer,
                supplier=supplier,
                itemType="product",
                productNumber=model,
                partNumber=model,
                defaultCategory=category_for(page_no, raw_name),
                price=sell_price,
                standardPrice=recommended_price,
                purchasePrice=purchase_price,
                purchasePriceIncludingVat=int(config.get("purchase_price_including_vat", 0)),
                currency="EUR",
                includingVat=int(config.get("including_vat", 0)),
                percentVat=int(config.get("vat_rate", 23)),
                stock=int(config.get("stock", 0)),
                availabilityOutOfStock=config.get("availability_out_of_stock", "Na objednávku"),
                availabilityInStock=config.get("availability_in_stock", "Skladom"),
                unit=config.get("unit", "ks"),
                warranty=warranty,
                productVisibility=config.get("product_visibility", "visible"),
                seoTitle=name[:70],
                metaDescription=f"{name} – kompletná zostava, model {model}, kód {code}."[:155],
                internalNote=f"Midea/MDV PDF 2026, strana {page_no}. VIP bez DPH {purchase_price:.0f} €, odporúčaná cena bez DPH {recommended_price:.0f} €.",
                filteringProperty_Vyrobca=manufacturer,
                filteringProperty_Vykon=power,
                filteringProperty_Chladivo=refrigerant,
                filteringProperty_Typ="Kompletný set",
            ))
            if limit and len(products) >= limit:
                return products, skipped
    return products, skipped


def product_to_row(product: Product, headers: list[str]) -> dict[str, Any]:
    base = asdict(product)
    # Interné polia, ktoré Shoptet nepotrebuje ako stĺpce.
    base.pop("page", None)
    base.pop("raw_name", None)
    base.pop("model", None)
    return {h: base.get(h, "") for h in headers}
