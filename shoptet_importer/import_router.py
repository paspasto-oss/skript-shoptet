from __future__ import annotations

from pathlib import Path

from .csv_importer import import_csv_products
from .generic_pdf import extract_products_generic
from .product_model import UniversalProduct
from .xlsx_importer import import_xlsx_products
from .xml_importer import import_xml_products


SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".xml"}


def import_file_to_products(path: str | Path, limit: int | None = None) -> tuple[list[UniversalProduct], list[dict]]:
    """Jednotny vstupny bod pre import produktov."""
    file_path = Path(path)
    ext = file_path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Nepodporovany format suboru: {ext}")

    if ext == ".pdf":
        return extract_products_generic(file_path, limit=limit)
    if ext == ".csv":
        return import_csv_products(file_path, limit=limit)
    if ext in {".xlsx", ".xls"}:
        return import_xlsx_products(file_path, limit=limit)
    if ext == ".xml":
        return import_xml_products(file_path, limit=limit)

    raise ValueError(f"Nepodporovany format suboru: {ext}")
