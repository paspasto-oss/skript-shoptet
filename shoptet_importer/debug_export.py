from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .generic_pdf import extract_text_pages
from .product_model import UniversalProduct


def export_pdf_raw_lines(pdf_path: str | Path, out_path: str | Path) -> int:
    """Exportuje surovo precitane riadky z PDF pre kontrolu parsera.

    Toto je diagnostika: najprv musime vidiet, co program z PDF realne cita,
    az potom z toho skladat produkty.
    """
    pdf_path = Path(pdf_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pages = extract_text_pages(pdf_path)
    count = 0
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["page", "line_no", "text"], delimiter=";")
        writer.writeheader()
        for page_no, lines in pages:
            for line_no, text in enumerate(lines, start=1):
                writer.writerow({"page": page_no, "line_no": line_no, "text": text})
                count += 1
    return count


def export_parsed_preview(products: list[UniversalProduct], skipped: list[dict[str, Any]], out_path: str | Path) -> None:
    """Exportuje kontrolny prehlad toho, co parser poskladal z PDF."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "status",
                "code",
                "name",
                "manufacturer",
                "supplier",
                "category",
                "model",
                "purchase_price",
                "sale_price",
                "source_page",
                "parameters",
                "raw_reason",
                "raw_line",
            ],
            delimiter=";",
        )
        writer.writeheader()
        for product in products:
            writer.writerow({
                "status": "OK",
                "code": product.code,
                "name": product.name,
                "manufacturer": product.manufacturer,
                "supplier": product.supplier,
                "category": product.category,
                "model": product.model,
                "purchase_price": product.purchase_price,
                "sale_price": product.sale_price,
                "source_page": product.source_page,
                "parameters": product.parameters,
                "raw_reason": "",
                "raw_line": "",
            })
        for item in skipped:
            writer.writerow({
                "status": "SKIPPED",
                "code": item.get("code", ""),
                "name": "",
                "manufacturer": "",
                "supplier": "",
                "category": "",
                "model": "",
                "purchase_price": "",
                "sale_price": "",
                "source_page": item.get("page", ""),
                "parameters": "",
                "raw_reason": item.get("reason", ""),
                "raw_line": item.get("raw", ""),
            })
