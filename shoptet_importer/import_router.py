from __future__ import annotations

from pathlib import Path

from .csv_importer import import_csv_products
from .generic_pdf import extract_products_generic, extract_text_pages
from .pdf_plugins import detect_pdf_plugin, parse_blumut_pdf, parse_mitsubishi_pdf, parse_vaillant_pdf
from .product_model import UniversalProduct
from .xlsx_importer import import_xlsx_products
from .xml_importer import import_xml_products


SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".xml"}


def import_pdf_with_plugins(file_path: Path, limit: int | None = None) -> tuple[list[UniversalProduct], list[dict]]:
    pages = extract_text_pages(file_path)
    plugin = detect_pdf_plugin(file_path, pages)

    if plugin == "blumut":
        return parse_blumut_pdf(file_path, limit=limit)
    if plugin == "vaillant":
        return parse_vaillant_pdf(file_path, limit=limit)
    if plugin == "mitsubishi":
        return parse_mitsubishi_pdf(file_path, limit=limit)

    return extract_products_generic(file_path, limit=limit)


def import_file_to_products(path: str | Path, limit: int | None = None) -> tuple[list[UniversalProduct], list[dict]]:
    """Jednotny vstupny bod pre import produktov."""
    file_path = Path(path)
    ext = file_path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Nepodporovany format suboru: {ext}")

    if ext == ".pdf":
        return import_pdf_with_plugins(file_path, limit=limit)
    if ext == ".csv":
        return import_csv_products(file_path, limit=limit)
    if ext in {".xlsx", ".xls"}:
        return import_xlsx_products(file_path, limit=limit)
    if ext == ".xml":
        return import_xml_products(file_path, limit=limit)

    raise ValueError(f"Nepodporovany format suboru: {ext}")
