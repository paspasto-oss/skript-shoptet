from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .product_model import UniversalProduct


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    supplier TEXT,
    manufacturer TEXT,
    supplier_code TEXT,
    model TEXT,
    ean TEXT,
    product_type TEXT,
    category TEXT,
    unit TEXT,
    vat_rate INTEGER,
    currency TEXT,
    purchase_price REAL,
    sale_price REAL,
    standard_price REAL,
    stock REAL,
    availability_in_stock TEXT,
    availability_out_of_stock TEXT,
    short_description TEXT,
    description TEXT,
    seo_title TEXT,
    meta_description TEXT,
    image_url TEXT,
    active INTEGER,
    source TEXT,
    source_page INTEGER,
    parameters_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    imported_count INTEGER,
    skipped_count INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class ProductDatabase:
    def __init__(self, path: str | Path = "data/products.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_product(self, product: UniversalProduct) -> None:
        data = product.to_dict()
        data["active"] = 1 if product.active else 0
        data["parameters_json"] = json.dumps(product.parameters or {}, ensure_ascii=False)
        del data["parameters"]

        columns = list(data.keys())
        placeholders = ", ".join([":" + c for c in columns])
        updates = ", ".join([f"{c}=excluded.{c}" for c in columns if c != "code"])

        sql = f"""
        INSERT INTO products ({', '.join(columns)}, updated_at)
        VALUES ({placeholders}, CURRENT_TIMESTAMP)
        ON CONFLICT(code) DO UPDATE SET
            {updates},
            updated_at=CURRENT_TIMESTAMP
        """
        self.conn.execute(sql, data)
        self.conn.commit()

    def upsert_many(self, products: Iterable[UniversalProduct]) -> int:
        count = 0
        for product in products:
            self.upsert_product(product)
            count += 1
        return count

    def list_products(self, active_only: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM products"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY manufacturer, category, name"
        return list(self.conn.execute(sql))

    def get_product(self, code: str) -> sqlite3.Row | None:
        row = self.conn.execute("SELECT * FROM products WHERE code = ?", (code,)).fetchone()
        return row

    def log_import(self, source: str, imported_count: int, skipped_count: int) -> None:
        self.conn.execute(
            "INSERT INTO import_log (source, imported_count, skipped_count) VALUES (?, ?, ?)",
            (source, imported_count, skipped_count),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
