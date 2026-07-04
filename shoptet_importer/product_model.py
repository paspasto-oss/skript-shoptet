from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class UniversalProduct:
    """Univerzalny produkt pre Shoptet aj internu databazu.

    Nie je viazany iba na klimatizacie. Pouzije sa pre zariadenia,
    fitingy, naradie, elektro material, servisne diely aj prislusenstvo.
    """

    code: str
    name: str
    supplier: str = ""
    manufacturer: str = ""
    supplier_code: str = ""
    model: str = ""
    ean: str = ""
    product_type: str = "product"
    category: str = ""
    unit: str = "ks"
    vat_rate: int = 23
    currency: str = "EUR"
    purchase_price: float = 0.0
    sale_price: float = 0.0
    standard_price: float = 0.0
    stock: float = 0.0
    availability_in_stock: str = "Skladom"
    availability_out_of_stock: str = "Na objednavku"
    short_description: str = ""
    description: str = ""
    seo_title: str = ""
    meta_description: str = ""
    image_url: str = ""
    active: bool = True
    source: str = ""
    source_page: int | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["parameters"] = dict(self.parameters or {})
        return data
