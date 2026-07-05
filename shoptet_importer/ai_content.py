from __future__ import annotations

from .product_model import UniversalProduct


def generate_basic_content(product: UniversalProduct) -> UniversalProduct:
    """Faza 3 placeholder: lokalne generovanie zakladneho obsahu bez API.

    Neskor sa sem napoji AI model. Zatial doplni rozumne SEO a HTML popis,
    aby produkt nebol prazdny.
    """
    if not product.seo_title:
        product.seo_title = product.name[:70]

    if not product.meta_description:
        product.meta_description = f"{product.name} od vyrobcu {product.manufacturer}. Kod produktu {product.code}."[:155]

    if not product.short_description:
        product.short_description = " / ".join(x for x in [product.manufacturer, product.model, product.category] if x)[:255]

    if not product.description:
        product.description = (
            f"<h2>{product.name}</h2>"
            f"<p>Produkt z kategorie {product.category}.</p>"
            "<ul>"
            f"<li><strong>Vyrobca:</strong> {product.manufacturer}</li>"
            f"<li><strong>Dodavatel:</strong> {product.supplier}</li>"
            f"<li><strong>Kod:</strong> {product.code}</li>"
            "</ul>"
        )

    return product
