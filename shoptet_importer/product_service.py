from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .database import ProductDatabase


EDITABLE_FIELDS = {
    "name",
    "supplier",
    "manufacturer",
    "supplier_code",
    "model",
    "ean",
    "product_type",
    "category",
    "unit",
    "vat_rate",
    "currency",
    "purchase_price",
    "sale_price",
    "standard_price",
    "stock",
    "availability_in_stock",
    "availability_out_of_stock",
    "short_description",
    "description",
    "seo_title",
    "meta_description",
    "image_url",
    "active",
}


class ProductService:
    """Aplikacna vrstva pre editor produktov."""

    def __init__(self, db_path: str | Path = "data/products.sqlite") -> None:
        self.db = ProductDatabase(db_path)

    def search(self, text: str = "", limit: int = 500) -> list[sqlite3.Row]:
        text = text.strip()
        sql = "SELECT * FROM products"
        params: list[Any] = []
        if text:
            sql += " WHERE code LIKE ? OR name LIKE ? OR manufacturer LIKE ? OR category LIKE ?"
            like = f"%{text}%"
            params.extend([like, like, like, like])
        sql += " ORDER BY manufacturer, category, name LIMIT ?"
        params.append(limit)
        return list(self.db.conn.execute(sql, params))

    def update_field(self, code: str, field: str, value: Any) -> None:
        if field not in EDITABLE_FIELDS:
            raise ValueError(f"Pole nie je editovatelne: {field}")
        if field == "active":
            value = 1 if str(value).lower() in {"1", "true", "ano", "áno", "yes", "visible"} else 0
        self.db.conn.execute(f"UPDATE products SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE code = ?", (value, code))
        self.db.conn.commit()

    def set_active(self, codes: list[str], active: bool) -> int:
        if not codes:
            return 0
        placeholders = ",".join("?" for _ in codes)
        self.db.conn.execute(f"UPDATE products SET active = ?, updated_at = CURRENT_TIMESTAMP WHERE code IN ({placeholders})", [1 if active else 0, *codes])
        self.db.conn.commit()
        return len(codes)

    def close(self) -> None:
        self.db.close()
