from __future__ import annotations


def calculate_sale_price(purchase_price: float, rules: list[dict] | None = None, fallback_multiplier: float = 1.35) -> float:
    """Vypocet predajnej ceny z nakupnej ceny.

    Rules priklad:
    [
      {"max": 500, "multiplier": 1.35},
      {"max": 1000, "multiplier": 1.30},
      {"max": 2000, "multiplier": 1.25},
      {"max": null, "multiplier": 1.20}
    ]
    """
    if purchase_price <= 0:
        return 0.0

    for rule in rules or []:
        max_value = rule.get("max")
        multiplier = float(rule.get("multiplier", fallback_multiplier))
        if max_value is None or purchase_price <= float(max_value):
            return round(purchase_price * multiplier, 2)

    return round(purchase_price * fallback_multiplier, 2)
