from __future__ import annotations

from typing import Iterable

from .product_model import UniversalProduct


def midea_products_to_universal(products: Iterable[object]) -> list[UniversalProduct]:
    """Konverzia existujuceho Midea parsera do univerzalneho modelu.

    Toto je most medzi prvou verziou parsera a novym jadrom aplikacie.
    Parsery pre dalsich dodavatelov budu vracat UniversalProduct priamo.
    """
    out: list[UniversalProduct] = []
    for p in products:
        out.append(
            UniversalProduct(
                code=getattr(p, "code", ""),
                name=getattr(p, "name", ""),
                supplier=getattr(p, "supplier", ""),
                manufacturer=getattr(p, "manufacturer", ""),
                supplier_code=getattr(p, "code", ""),
                model=getattr(p, "productNumber", ""),
                product_type="set",
                category=getattr(p, "defaultCategory", ""),
                unit=getattr(p, "unit", "ks"),
                vat_rate=int(getattr(p, "percentVat", 23) or 23),
                currency=getattr(p, "currency", "EUR"),
                purchase_price=float(getattr(p, "purchasePrice", 0) or 0),
                sale_price=float(getattr(p, "price", 0) or 0),
                standard_price=float(getattr(p, "standardPrice", 0) or 0),
                stock=float(getattr(p, "stock", 0) or 0),
                availability_in_stock=getattr(p, "availabilityInStock", "Skladom"),
                availability_out_of_stock=getattr(p, "availabilityOutOfStock", "Na objednavku"),
                short_description=getattr(p, "shortDescription", ""),
                description=getattr(p, "description", ""),
                seo_title=getattr(p, "seoTitle", ""),
                meta_description=getattr(p, "metaDescription", ""),
                source="Midea/MDV PDF",
                source_page=getattr(p, "page", None),
                parameters={
                    "vykon": getattr(p, "filteringProperty_Vykon", ""),
                    "chladivo": getattr(p, "filteringProperty_Chladivo", ""),
                    "typ": getattr(p, "filteringProperty_Typ", ""),
                },
            )
        )
    return out
