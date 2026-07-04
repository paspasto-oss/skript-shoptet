from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz

from .product_model import UniversalProduct

CODE_RE = re.compile(r"\b([A-Z]{1,4}\d{6}|\d{6}|\d\.\d{3}\.\d{5})\b")
PRICE_EUR_RE = re.compile(r"(\d{1,3}(?:[ \u00a0]\d{3})*(?:[,.]\d{2})?|\d+)\s*€")
PRICE_AT_END_RE = re.compile(r"\s(\d{1,3}(?:[ \u00a0]\d{3})*(?:[,.]\d{2})?|\d+)(?:\s*)$")
POWER_RE = re.compile(r"(\d{1,2}(?:[,.]\d+)?)\s*kW", re.I)
REFRIGERANT_RE = re.compile(r"\b(R32|R290|R410A|R134A)\b", re.I)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def parse_price(value: str) -> float:
    value = value.replace("€", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return 0.0


def detect_supplier_and_manufacturer(text: str, filename: str) -> tuple[str, str]:
    t = (text + " " + filename).lower()
    if "vaillant" in t:
        return "Vaillant Group Slovakia, s.r.o.", "Vaillant"
    if "blumut" in t:
        return "K-KOMPONENT s.r.o.", "Blumut"
    if "womix" in t or "čerpadlové skupiny" in t or "cerpadlove skupiny" in t:
        return "K-KOMPONENT s.r.o.", "WOMIX"
    if "midea" in t or "hmid" in t or "cmid" in t:
        return "Planning & Trading Slovakia s.r.o.", "Midea"
    return "", ""


def guess_category(manufacturer: str, name: str, context: str = "") -> str:
    n = (name + " " + context).lower()
    if "ohrievač vody" in n or "ohrievac vody" in n:
        return "Ohrievače vody > Midea"
    if "čistička" in n or "cisticka" in n or "filter pre" in n:
        return "Čističky vzduchu"
    if "odvlhčovač" in n or "odvlhcovac" in n:
        return "Odvlhčovače vzduchu"
    if "prenosná jednotka" in n or "mobilná klimatizácia" in n or "portasplit" in n:
        return "Klimatizácie > Mobilné klimatizácie"
    if "tepelné čerpadlo" in n or "tepelne čerpadlo" in n or "arotherm" in n:
        return "Tepelné čerpadlá > Vaillant"
    if "kotol" in n or "ecotec" in n:
        return "Kotly > Vaillant"
    if "čerpadlov" in n or "cerpadlov" in n or "wilo" in n or "grundfos" in n or "dab" in n:
        return "Vykurovanie > Čerpadlové skupiny"
    if "rozdeľovač" in n or "rozdelovac" in n:
        return "Vykurovanie > Rozdeľovače"
    if "hydraulický separátor" in n or "hydraulicky separator" in n:
        return "Vykurovanie > Hydraulické separátory"
    if "protikondenzač" in n or "protikondenzac" in n or "blumut" in n:
        return "Vykurovanie > Protikondenzačné jednotky"
    return f"Produkty > {manufacturer}" if manufacturer else "Produkty"


def build_description(product: UniversalProduct) -> str:
    rows = [
        ("Výrobca", product.manufacturer),
        ("Dodávateľ", product.supplier),
        ("Kód", product.code),
    ]
    if product.model:
        rows.append(("Model", product.model))
    for key, value in product.parameters.items():
        if value:
            rows.append((key.capitalize(), str(value)))
    lis = "".join(f"<li><strong>{k}:</strong> {v}</li>" for k, v in rows if v)
    return f"<p>{product.name}</p><ul>{lis}</ul>"


def extract_text_pages(pdf_path: Path) -> list[tuple[int, list[str]]]:
    doc = fitz.open(str(pdf_path))
    pages: list[tuple[int, list[str]]] = []
    for page_no, page in enumerate(doc, start=1):
        lines = [clean(x) for x in page.get_text().splitlines() if clean(x)]
        pages.append((page_no, lines))
    return pages


def extract_midea_household_line(line: str, supplier: str, manufacturer: str, page_no: int) -> UniversalProduct | None:
    # Formaty:
    # HMID000006 LumeMini ... D10-20VD1(U) 52 € 70 €
    # 20 l/den CMID002084 Odvlhčovač ... MDDF... 150 € 190 €
    prices = PRICE_EUR_RE.findall(line)
    if len(prices) < 2:
        return None
    code_match = re.search(r"\b([HC]MID\d{6})\b", line)
    if not code_match:
        return None
    code = code_match.group(1)
    before_prices = PRICE_EUR_RE.split(line)[0]
    after_code = before_prices.split(code, 1)[1].strip()
    tokens = after_code.split()
    model_index = None
    for idx in range(len(tokens) - 1, -1, -1):
        if re.search(r"[A-Z]{2,}|\d", tokens[idx]) and ("-" in tokens[idx] or re.search(r"\d", tokens[idx])):
            model_index = idx
            break
    if model_index is not None and model_index > 0:
        name = " ".join(tokens[:model_index]).strip()
        model = " ".join(tokens[model_index:]).strip()
    else:
        name = after_code
        model = ""
    purchase = parse_price(prices[0])
    standard = parse_price(prices[1])
    power = POWER_RE.search(line)
    refrigerant = REFRIGERANT_RE.search(line)
    product = UniversalProduct(
        code=code,
        name=f"{manufacturer} {name}" if manufacturer and not name.lower().startswith(manufacturer.lower()) else name,
        supplier=supplier,
        manufacturer=manufacturer,
        supplier_code=code,
        model=model,
        product_type="product",
        category=guess_category(manufacturer, name),
        purchase_price=purchase,
        sale_price=standard,
        standard_price=standard,
        source="generic_pdf:midea_household",
        source_page=page_no,
        parameters={
            "vykon": power.group(0) if power else "",
            "chladivo": refrigerant.group(1).upper() if refrigerant else "",
        },
    )
    product.short_description = " / ".join(x for x in [manufacturer, model] if x)
    product.seo_title = product.name[:70]
    product.meta_description = f"{product.name} – kód {code}."[:155]
    product.description = build_description(product)
    return product


def extract_simple_offer_line(line: str, supplier: str, manufacturer: str, page_no: int, context: str) -> UniversalProduct | None:
    # WOMIX / BLUMUT riadky často nemajú €, cena je na konci riadku.
    code_match = CODE_RE.search(line)
    if not code_match:
        return None
    code = code_match.group(1)
    if code.lower() in {"2026"}:
        return None
    price_match = PRICE_AT_END_RE.search(line)
    if not price_match:
        return None
    price = parse_price(price_match.group(1))
    if price <= 0:
        return None
    body = line[: price_match.start()].strip()
    body = body.replace(code, "", 1).strip(" -")
    if len(body) < 4:
        return None
    parts = body.split(" - ", 1)
    if len(parts) == 2:
        model = parts[0].strip()
        desc = parts[1].strip()
        name = f"{model} - {desc[:80]}".strip()
    else:
        model = ""
        desc = body
        name = body[:120]
    product = UniversalProduct(
        code=code,
        name=f"{manufacturer} {name}" if manufacturer and not name.lower().startswith(manufacturer.lower()) else name,
        supplier=supplier,
        manufacturer=manufacturer,
        supplier_code=code,
        model=model,
        product_type="product",
        category=guess_category(manufacturer, name, context),
        purchase_price=price,
        sale_price=round(price * 1.35, 2),
        standard_price=0,
        source="generic_pdf:simple_offer",
        source_page=page_no,
        parameters={},
    )
    product.short_description = desc[:255]
    product.seo_title = product.name[:70]
    product.meta_description = f"{product.name} – kód {code}."[:155]
    product.description = build_description(product)
    return product


def extract_vaillant_line(line: str, supplier: str, manufacturer: str, page_no: int, context: str) -> UniversalProduct | None:
    # Prvá verzia: zachytáva riadky, kde je obj. číslo a dve ceny na konci.
    m = re.match(r"^(\d{10})\s+(.+?)\s+(\d{1,3}(?: \d{3})*,\d{2})\s+(\d{1,3}(?: \d{3})*,\d{2})\s*$", line)
    if not m:
        return None
    code, name, standard_s, action_s = m.groups()
    standard = parse_price(standard_s)
    action = parse_price(action_s)
    refrigerant = REFRIGERANT_RE.search(line)
    power = POWER_RE.search(line)
    product = UniversalProduct(
        code=code,
        name=f"Vaillant {name}" if not name.lower().startswith("vaillant") else name,
        supplier=supplier,
        manufacturer=manufacturer,
        supplier_code=code,
        model="",
        product_type="product",
        category=guess_category(manufacturer, name, context),
        purchase_price=action,
        sale_price=action,
        standard_price=standard,
        source="generic_pdf:vaillant",
        source_page=page_no,
        parameters={
            "chladivo": refrigerant.group(1).upper() if refrigerant else "",
            "vykon": power.group(0) if power else "",
        },
    )
    product.short_description = manufacturer
    product.seo_title = product.name[:70]
    product.meta_description = f"{product.name} – obj. č. {code}."[:155]
    product.description = build_description(product)
    return product


def extract_products_generic(pdf_path: Path, limit: int | None = None) -> tuple[list[UniversalProduct], list[dict[str, Any]]]:
    pages = extract_text_pages(pdf_path)
    all_text = "\n".join("\n".join(lines) for _, lines in pages[:3])
    supplier, manufacturer = detect_supplier_and_manufacturer(all_text, pdf_path.name)
    products: list[UniversalProduct] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page_no, lines in pages:
        context = " ".join(lines[:8])
        for raw_line in lines:
            line = clean(raw_line)
            product = None
            if manufacturer == "Midea":
                product = extract_midea_household_line(line, supplier, manufacturer, page_no)
            if product is None and manufacturer == "Vaillant":
                product = extract_vaillant_line(line, supplier, manufacturer, page_no, context)
            if product is None:
                product = extract_simple_offer_line(line, supplier, manufacturer, page_no, context)

            if product is None:
                continue
            if product.code in seen:
                skipped.append({"page": page_no, "code": product.code, "reason": "duplicate", "raw": line})
                continue
            seen.add(product.code)
            products.append(product)
            if limit and len(products) >= limit:
                return products, skipped

    return products, skipped
