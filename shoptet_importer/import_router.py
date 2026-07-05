from __future__ import annotations

from pathlib import Path

from .generic_pdf import extract_products_generic
from .product_model import UniversalProduct


SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".xml"}


def import_file_to_products(path: str | Path, limit: int | None = None) -> tuple[list[UniversalProduct], list[dict]]:
    """Jednotny vstupny bod pre import produktov.

    Faza 1 implementuje PDF. Ostatne formaty budu doplnene vo fazach 1-2.
    """
    file_path = Path(path)
    ext = file_path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Nepodporovany format suboru: {ext}")

    if ext == ".pdf":
        return extract_products_generic(file_path, limit=limit)

    raise NotImplementedError(f"Importer pre format {ext} este nie je implementovany.")
