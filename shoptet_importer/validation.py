from __future__ import annotations

from .product_model import UniversalProduct


def validate_products(products: list[UniversalProduct]) -> list[dict]:
    """Zakladna kontrola pred ulozenim/exportom."""
    errors: list[dict] = []
    seen: set[str] = set()

    for index, product in enumerate(products, start=1):
        if not product.code:
            errors.append({"row": index, "code": "", "field": "code", "message": "Chyba kod produktu"})
        if product.code in seen:
            errors.append({"row": index, "code": product.code, "field": "code", "message": "Duplicitny kod produktu"})
        seen.add(product.code)

        if not product.name:
            errors.append({"row": index, "code": product.code, "field": "name", "message": "Chyba nazov produktu"})
        if product.sale_price <= 0:
            errors.append({"row": index, "code": product.code, "field": "sale_price", "message": "Predajna cena je nulova"})
        if not product.category:
            errors.append({"row": index, "code": product.code, "field": "category", "message": "Chyba kategoria"})

    return errors
