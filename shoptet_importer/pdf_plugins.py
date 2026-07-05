from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .content_templates import enrich_product_content
from .generic_pdf import clean, extract_text_pages, guess_category, parse_price
from .product_model import UniversalProduct

CODE_DOTTED_RE = re.compile(r"^\d\.\d{3}\.\d{5}$")
CODE_LONG_RE = re.compile(r"^(?:00\d{8}|80\d{8})$")
PRICE_RE = re.compile(r"^\d{1,3}(?:[ \u00a0]\d{3})*,\d{2}$|^\d+[,.]\d{2}$")
REFRIGERANT_RE = re.compile(r"\b(R32|R410A|R290|R134A)\b", re.I)
POWER_RE = re.compile(r"(\d{1,2}(?:[,.]\d+)?)\s*kW", re.I)


def _is_price(text: str) -> bool:
    return bool(PRICE_RE.match(clean(text)))


def _is_code(text: str) -> bool:
    t = clean(text)
    return bool(CODE_DOTTED_RE.match(t) or CODE_LONG_RE.match(t))


def detect_pdf_plugin(pdf_path: Path, pages: list[tuple[int, list[str]]]) -> str:
    header = " ".join(" ".join(lines[:30]) for _, lines in pages[:3]).lower()
    name = pdf_path.name.lower()
    if "blumut" in header or "blumut" in name:
        return "blumut"
    if "vaillant" in header or "vaillant" in name:
        return "vaillant"
    if "mitsubishi electric" in header or "csmtrade" in header or "vykuruj" in header:
        return "mitsubishi"
    if "midea" in header or "hmid" in header or "cmid" in header:
        return "midea"
    return "generic"


def _finish_product(product: UniversalProduct) -> UniversalProduct:
    return enrich_product_content(product)


def _extract_blumut_params(text: str) -> dict[str, str]:
    params: dict[str, str] = {"popis": text}
    pump = re.search(r"čerpadlo\s+([^\-]+?)(?:\s+-|$)", text, re.I)
    if pump:
        params["cerpadlo"] = pump.group(1).strip()
    temp = re.search(r"(\d{2})°C", text)
    if temp:
        params["teplota"] = temp.group(1) + " °C"
    power = re.search(r"výkon\s+(\d+\s*kW)", text, re.I)
    if power:
        params["vykon"] = power.group(1).strip()
    conn = re.search(r"pripojenie\s+([^\-]+)", text, re.I)
    if conn:
        params["pripojenie"] = conn.group(1).strip()
    return params


def parse_blumut_pdf(pdf_path: Path, limit: int | None = None) -> tuple[list[UniversalProduct], list[dict[str, Any]]]:
    pages = extract_text_pages(pdf_path)
    products: list[UniversalProduct] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    context = "Vykurovanie > Protikondenzačné jednotky"

    for page_no, lines in pages:
        i = 0
        while i < len(lines):
            line_upper = lines[i].upper()
            code = clean(lines[i])
            if not CODE_DOTTED_RE.match(code):
                if "BLUMUT HE DN 32" in line_upper:
                    context = "Vykurovanie > Protikondenzačné jednotky > BLUMUT HE DN32"
                elif "BLUMUT COMPACT" in line_upper:
                    context = "Vykurovanie > Protikondenzačné jednotky > BLUMUT Compact HE DN25"
                i += 1
                continue

            block: list[str] = []
            j = i + 1
            while j < len(lines) and not CODE_DOTTED_RE.match(clean(lines[j])):
                block.append(clean(lines[j]))
                if block and _is_price(block[-1]):
                    break
                j += 1

            if block and _is_price(block[-1]):
                price = parse_price(block[-1])
                block = block[:-1]
            else:
                skipped.append({"page": page_no, "code": code, "reason": "missing_price"})
                i = max(j, i + 1)
                continue

            if code in seen:
                skipped.append({"page": page_no, "code": code, "reason": "duplicate"})
                i = max(j, i + 1)
                continue

            model_lines: list[str] = []
            desc_lines: list[str] = []
            for part in block:
                if part.upper() in {"WILO", "DAB", "GRUNDFOS"} or part.startswith("Blumut") or re.search(r"DN \d+", part):
                    model_lines.append(part.replace("Copmact", "Compact"))
                else:
                    desc_lines.append(part.replace("Copmact", "Compact"))
            model = " ".join(model_lines).strip()
            desc = " ".join(desc_lines).strip() or model

            if model:
                name = model if model.upper().startswith("BLUMUT") else f"BLUMUT {model}"
            else:
                name = f"BLUMUT {desc[:90]}"

            product = UniversalProduct(
                code=code,
                name=name,
                supplier="K-KOMPONENT s.r.o.",
                manufacturer="BLUMUT",
                supplier_code=code,
                model=model or code,
                category=context,
                purchase_price=price,
                sale_price=round(price * 1.35, 2),
                standard_price=0,
                source=f"blumut_pdf:{pdf_path.name}",
                source_page=page_no,
                parameters=_extract_blumut_params(desc),
            )
            products.append(_finish_product(product))
            seen.add(code)
            if limit and len(products) >= limit:
                return products, skipped
            i = max(j + 1, i + 1)
    return products, skipped


def parse_vaillant_pdf(pdf_path: Path, limit: int | None = None) -> tuple[list[UniversalProduct], list[dict[str, Any]]]:
    pages = extract_text_pages(pdf_path)
    products: list[UniversalProduct] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    current_category = "Produkty > Vaillant"

    for page_no, lines in pages:
        for head in lines[:12]:
            h = head.lower()
            if "tepelné čerpadlá" in h or "tepelne čerpadla" in h:
                current_category = "Tepelné čerpadlá > Vaillant"
            elif "kondenzačné kotly" in h or "kotly" == h.strip():
                current_category = "Kotly > Vaillant"
            elif "zásobník" in h or "zásobníky" in h:
                current_category = "Zásobníky > Vaillant"
            elif "príslušenstvo" in h or "prislusenstvo" in h:
                current_category = "Príslušenstvo > Vaillant"
            elif "rekuperačné" in h or "recovair" in h:
                current_category = "Rekuperácie > Vaillant"

        i = 0
        while i < len(lines):
            code = clean(lines[i])
            if not CODE_LONG_RE.match(code):
                i += 1
                continue

            block: list[str] = []
            j = i + 1
            prices: list[float] = []
            while j < len(lines) and not CODE_LONG_RE.match(clean(lines[j])):
                t = clean(lines[j])
                if _is_price(t):
                    prices.append(parse_price(t))
                    if len(prices) >= 2:
                        j += 1
                        break
                else:
                    if not re.match(r"^(A\+\+\+|A\+\+|A\+|A|R32|R410A|\d{1,2}[,.]\d|\d{1,2})$", t):
                        block.append(t)
                j += 1

            if not prices:
                skipped.append({"page": page_no, "code": code, "reason": "missing_price"})
                i = max(j, i + 1)
                continue
            if code in seen:
                skipped.append({"page": page_no, "code": code, "reason": "duplicate"})
                i = max(j, i + 1)
                continue

            action_price = prices[-1]
            standard_price = prices[0] if len(prices) > 1 else 0
            desc = " ".join(block).strip()
            name = desc[:180] if desc else f"Vaillant {code}"
            if not name.lower().startswith("vaillant"):
                name = f"Vaillant {name}"
            text_window = " ".join(lines[max(0, i - 5):j])
            refrigerant = REFRIGERANT_RE.search(text_window)
            power = POWER_RE.search(text_window)

            product = UniversalProduct(
                code=code,
                name=name,
                supplier="Vaillant Group Slovakia, s.r.o.",
                manufacturer="Vaillant",
                supplier_code=code,
                model=code,
                category=current_category,
                purchase_price=action_price,
                sale_price=action_price,
                standard_price=standard_price,
                source=f"vaillant_pdf:{pdf_path.name}",
                source_page=page_no,
                parameters={
                    "chladivo": refrigerant.group(1).upper() if refrigerant else "",
                    "vykon": power.group(0) if power else "",
                    "popis": desc,
                },
            )
            products.append(_finish_product(product))
            seen.add(code)
            if limit and len(products) >= limit:
                return products, skipped
            i = max(j, i + 1)
    return products, skipped


def parse_mitsubishi_pdf(pdf_path: Path, limit: int | None = None) -> tuple[list[UniversalProduct], list[dict[str, Any]]]:
    pages = extract_text_pages(pdf_path)
    products: list[UniversalProduct] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()

    model_re = re.compile(r"\b(?:MSZ|MUZ|MXZ|PUZ|PUD|SUZ|EHST|EHSD|PCA|PKA|PLA|PEA|VL|LGH|MAC)-[A-Z0-9\-]+\b")
    euro_re = re.compile(r"^(\d{2,6})(?:,-)?$")

    for page_no, lines in pages:
        context = " ".join(lines[:8])
        for idx, line in enumerate(lines):
            m = model_re.search(line)
            if not m:
                continue
            model = m.group(0)
            if model in seen:
                continue
            window = lines[idx: min(len(lines), idx + 10)]
            prices = []
            for w in window:
                wm = euro_re.match(clean(w).replace(" ", ""))
                if wm:
                    val = float(wm.group(1))
                    if val > 50:
                        prices.append(val)
            if not prices:
                skipped.append({"page": page_no, "code": model, "reason": "missing_price"})
                continue
            price = prices[-1]
            name = line if len(line) > len(model) else f"Mitsubishi Electric {model}"
            category = guess_category("Mitsubishi Electric", name, context)
            if category == "Produkty > Mitsubishi Electric":
                if "klimat" in context.lower() or model.startswith(("MSZ", "MUZ", "MXZ")):
                    category = "Klimatizácie > Mitsubishi Electric"
                elif model.startswith(("PUZ", "PUD", "SUZ", "EHS")):
                    category = "Tepelné čerpadlá > Mitsubishi Electric"
                elif model.startswith(("VL", "LGH")):
                    category = "Rekuperácie > Mitsubishi Electric"
            product = UniversalProduct(
                code=model,
                name=name if name.lower().startswith("mitsubishi") else f"Mitsubishi Electric {name}",
                supplier="CS-MTRADE SK s.r.o.",
                manufacturer="Mitsubishi Electric",
                supplier_code=model,
                model=model,
                category=category,
                purchase_price=price,
                sale_price=round(price * 1.25, 2),
                standard_price=price,
                source=f"mitsubishi_pdf:{pdf_path.name}",
                source_page=page_no,
                parameters={},
            )
            products.append(_finish_product(product))
            seen.add(model)
            if limit and len(products) >= limit:
                return products, skipped
    return products, skipped
