from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from .product_model import UniversalProduct

DEFAULT_MARGIN = 0.30

# Kody bez diakritiky/varianty dodavatelov:
# 7.030.02016, HMID000006, CMID002084, 0010043966, 8000039233, MSZ-AY25VGK
CODE_RE = re.compile(
    r"\b("
    r"\d\.\d{3}\.\d{5}"
    r"|[A-Z]{1,6}\d{4,8}"
    r"|00\d{8}"
    r"|80\d{8}"
    r"|[A-Z]{2,5}-[A-Z0-9][A-Z0-9\-\/]{2,}"
    r")\b"
)

PRICE_TOKEN_RE = re.compile(
    r"(?<![\w.])(?:EUR|€)?\s*(\d{1,3}(?:[ \u00a0.]\d{3})*(?:[,.]\d{1,2})?|\d{2,6}(?:[,.]\d{1,2})?)\s*(?:EUR|€)?(?![\w.])",
    re.I,
)

HEADER_WORDS = {
    "kod", "kód", "code", "cena", "price", "nazov", "názov", "model", "typ", "popis",
    "ks", "eur", "bez", "dph", "s", "dph", "zlava", "zľava", "strana", "page",
}


@dataclass
class BasicExtractedProduct:
    code: str
    name: str
    purchase_price: float
    margin_percent: float
    sale_price: float
    page: int
    raw_text: str
    confidence: int


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def parse_price(value: str) -> float:
    text = value.replace("EUR", "").replace("€", "").replace(" ", "").replace("\xa0", "")
    # Bodka medzi tisickami, ciarka/desatinna bodka na konci.
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        parts = text.split(".")
        if len(parts) > 2:
            text = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def extract_prices(text: str) -> list[float]:
    prices: list[float] = []
    for match in PRICE_TOKEN_RE.finditer(text):
        value = parse_price(match.group(1))
        # Filtre proti rokom, strankam, teplotam a rozmerom.
        if 0.01 <= value <= 500000 and int(value) not in {2023, 2024, 2025, 2026, 2027}:
            prices.append(value)
    return prices


def text_from_pdf(pdf_path: str | Path) -> list[tuple[int, list[str]]]:
    doc = fitz.open(str(pdf_path))
    result: list[tuple[int, list[str]]] = []
    for page_index, page in enumerate(doc, start=1):
        words = page.get_text("words")
        if not words:
            lines = [clean_text(x) for x in page.get_text().splitlines() if clean_text(x)]
            result.append((page_index, lines))
            continue
        # Zlozenie riadkov podla suradnic, presnejsie ako splitlines pri tabulkach.
        sorted_words = sorted(words, key=lambda w: (round(w[1] / 3) * 3, w[0]))
        lines_map: dict[int, list[tuple[float, str]]] = {}
        for x0, y0, _x1, _y1, word, *_rest in sorted_words:
            key = int(round(y0 / 3) * 3)
            lines_map.setdefault(key, []).append((float(x0), str(word)))
        lines: list[str] = []
        for key in sorted(lines_map):
            parts = [w for _x, w in sorted(lines_map[key], key=lambda x: x[0])]
            line = clean_text(" ".join(parts))
            if line:
                lines.append(line)
        result.append((page_index, lines))
    return result


def is_noise_line(line: str) -> bool:
    low = line.lower()
    compact = re.sub(r"[^a-záäčďéíĺľňóôŕšťúýž0-9]+", " ", low).strip()
    words = compact.split()
    if not words:
        return True
    if len(words) <= 3 and all(w in HEADER_WORDS for w in words):
        return True
    if "www." in low or "tel." in low or "email" in low:
        return True
    return False


def guess_supplier_manufacturer(pdf_path: str | Path, all_text: str) -> tuple[str, str]:
    t = (Path(pdf_path).name + " " + all_text).lower()
    if "blumut" in t:
        return "K-KOMPONENT s.r.o.", "BLUMUT"
    if "womix" in t:
        return "K-KOMPONENT s.r.o.", "WOMIX"
    if "vaillant" in t:
        return "Vaillant Group Slovakia, s.r.o.", "Vaillant"
    if "mitsubishi electric" in t or "csmtrade" in t:
        return "CS-MTRADE SK s.r.o.", "Mitsubishi Electric"
    if "midea" in t or "hmid" in t or "cmid" in t:
        return "Planning & Trading Slovakia s.r.o.", "Midea"
    return "", ""


def candidate_name_from_block(code: str, block: list[str]) -> str:
    text = " ".join(block)
    text = CODE_RE.sub(" ", text)
    text = PRICE_TOKEN_RE.sub(" ", text)
    text = clean_text(text)
    # Odstran bezne nadpisy a tabulkove slova.
    words = [w for w in text.split() if w.lower().strip(":") not in HEADER_WORDS]
    text = clean_text(" ".join(words))
    if not text:
        return code
    return text[:255]


def group_blocks(lines: list[str]) -> list[tuple[int, int, list[str]]]:
    """Vrati bloky okolo riadkov s kodom.

    Nie je to preklad do Shoptetu. Je to len extrakcia zakladnych obchodnych udajov.
    """
    code_indexes = [i for i, line in enumerate(lines) if CODE_RE.search(line)]
    blocks: list[tuple[int, int, list[str]]] = []
    for pos, index in enumerate(code_indexes):
        next_index = code_indexes[pos + 1] if pos + 1 < len(code_indexes) else min(len(lines), index + 8)
        end = min(next_index, index + 8)
        start = max(0, index - 1)
        block = [line for line in lines[start:end] if not is_noise_line(line)]
        blocks.append((start, end, block))
    return blocks


def extract_basic_products_from_pdf(
    pdf_path: str | Path,
    default_margin: float = DEFAULT_MARGIN,
    limit: int | None = None,
) -> tuple[list[UniversalProduct], list[dict[str, Any]]]:
    pages = text_from_pdf(pdf_path)
    all_text = "\n".join("\n".join(lines[:40]) for _page, lines in pages[:5])
    supplier, manufacturer = guess_supplier_manufacturer(pdf_path, all_text)

    products: list[UniversalProduct] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page_no, lines in pages:
        for _start, _end, block in group_blocks(lines):
            raw_text = " | ".join(block)
            code_match = CODE_RE.search(raw_text)
            if not code_match:
                continue
            code = code_match.group(1)
            if code in seen:
                skipped.append({"page": page_no, "code": code, "reason": "duplicate", "raw": raw_text})
                continue

            prices = extract_prices(raw_text)
            # Vyluc kódové cisla omylom nacitane ako cena.
            prices = [p for p in prices if str(int(p)) not in code.replace(".", "")]
            if not prices:
                skipped.append({"page": page_no, "code": code, "reason": "missing_price", "raw": raw_text})
                continue

            purchase_price = prices[0]
            # Ak je v bloku viac cien, berieme najnizsiu ako nakup a najvyssiu ako standard/predaj.
            if len(prices) >= 2:
                purchase_price = min(prices)
                standard_price = max(prices)
            else:
                standard_price = 0.0

            margin_percent = round(default_margin * 100, 2)
            sale_price = round(purchase_price * (1 + default_margin), 2)
            name = candidate_name_from_block(code, block)
            if manufacturer and not name.lower().startswith(manufacturer.lower()):
                name = f"{manufacturer} {name}"
            name = clean_text(name)

            product = UniversalProduct(
                code=code,
                name=name,
                supplier=supplier,
                manufacturer=manufacturer,
                supplier_code=code,
                model=code,
                category=f"Produkty > {manufacturer}" if manufacturer else "Produkty",
                purchase_price=purchase_price,
                sale_price=sale_price,
                standard_price=standard_price,
                source=f"pdf_basic:{Path(pdf_path).name}",
                source_page=page_no,
                parameters={
                    "marza": f"{margin_percent:g} %",
                    "zdrojovy_text": raw_text,
                },
            )
            product.short_description = f"{name}. Kód produktu: {code}."
            product.description = (
                f"<h2>{name}</h2>"
                f"<p>Základné údaje produktu importované z cenníka dodávateľa.</p>"
                f"<table><tbody>"
                f"<tr><th>Kód produktu</th><td>{code}</td></tr>"
                f"<tr><th>Výrobca</th><td>{manufacturer}</td></tr>"
                f"<tr><th>Nákupná cena</th><td>{purchase_price:.2f} EUR bez DPH</td></tr>"
                f"<tr><th>Marža</th><td>{margin_percent:g} %</td></tr>"
                f"</tbody></table>"
            )
            product.seo_title = name[:70]
            product.meta_description = f"{name} – kód {code}."[:155]

            products.append(product)
            seen.add(code)
            if limit and len(products) >= limit:
                return products, skipped

    return products, skipped


def export_basic_products_csv(products: list[UniversalProduct], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["code", "name", "purchase_price", "margin_percent", "sale_price", "manufacturer", "supplier", "page", "raw_text"],
            delimiter=";",
        )
        writer.writeheader()
        for product in products:
            writer.writerow({
                "code": product.code,
                "name": product.name,
                "purchase_price": product.purchase_price,
                "margin_percent": product.parameters.get("marza", "30 %"),
                "sale_price": product.sale_price,
                "manufacturer": product.manufacturer,
                "supplier": product.supplier,
                "page": product.source_page,
                "raw_text": product.parameters.get("zdrojovy_text", ""),
            })
