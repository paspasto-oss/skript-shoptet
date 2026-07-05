from __future__ import annotations

from pathlib import Path

from .product_model import UniversalProduct


def image_filename_for(product: UniversalProduct) -> str:
    safe_code = "".join(ch for ch in product.code if ch.isalnum() or ch in "-_")
    return f"{safe_code}.jpg"


def attach_local_image_if_exists(product: UniversalProduct, image_dir: str | Path = "images") -> UniversalProduct:
    """Faza 3 placeholder: priradi lokalny obrazok podla kodu produktu.

    Neskor pribudne hladanie obrazkov u vyrobcov a optimalizacia.
    """
    folder = Path(image_dir)
    for suffix in [".jpg", ".jpeg", ".png", ".webp"]:
        candidate = folder / f"{product.code}{suffix}"
        if candidate.exists():
            product.image_url = str(candidate)
            break
    return product
