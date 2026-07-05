from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .db_export import product_row_to_shoptet


REQUIRED_FIELDS = ["code", "name", "price", "defaultCategory", "manufacturer", "supplier", "percentVat", "unit"]


def validate_shoptet_row(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if not str(row.get(field, "")).strip():
            errors.append(f"Chyba povinne pole: {field}")
    try:
        if float(str(row.get("price", "0")).replace(",", ".")) <= 0:
            errors.append("Cena musi byt vacsia ako 0")
    except ValueError:
        errors.append("Cena nie je cislo")
    if row.get("includingVat") not in {"0", "1"}:
        errors.append("includingVat musi byt 0 alebo 1")
    if row.get("productVisibility") not in {"visible", "hidden"}:
        errors.append("productVisibility musi byt visible alebo hidden")
    return errors


def create_shoptet_validation_report(db_path: str | Path, report_path: str | Path, active_only: bool = True) -> tuple[int, int]:
    db_path = Path(db_path)
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM products"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY manufacturer, category, name"
        rows = list(conn.execute(sql))

        errors_count = 0
        with report_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["code", "name", "status", "errors"], delimiter=";")
            writer.writeheader()
            for db_row in rows:
                shoptet_row = product_row_to_shoptet(db_row)
                errors = validate_shoptet_row(shoptet_row)
                if errors:
                    errors_count += 1
                writer.writerow({
                    "code": shoptet_row.get("code", ""),
                    "name": shoptet_row.get("name", ""),
                    "status": "ERROR" if errors else "OK",
                    "errors": " | ".join(errors),
                })
        return len(rows), errors_count
    finally:
        conn.close()
