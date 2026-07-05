from __future__ import annotations

from pathlib import Path
from tkinter import Button, Entry, Label, StringVar, Tk, Toplevel, messagebox
from tkinter.ttk import Treeview

from shoptet_importer.product_service import ProductService


COLUMNS = ["code", "name", "manufacturer", "category", "purchase_price", "sale_price", "stock"]


class ProductEditor:
    def __init__(self, db_path: str | Path = "data/products.sqlite") -> None:
        self.db_path = Path(db_path)
        self.root = Tk()
        self.root.title("Spektra Product Manager - Produkty")
        self.root.geometry("1100x650")

        self.search_text = StringVar()
        self.status = StringVar(value="Produktovy editor")

        Label(self.root, text="Produkty", font=("Arial", 18, "bold")).pack(anchor="w", padx=12, pady=8)

        toolbar = Toplevel
        Label(self.root, text="Hladat:").place(x=12, y=55)
        Entry(self.root, textvariable=self.search_text, width=50).place(x=70, y=55)
        Button(self.root, text="Hladat", command=self.load_products).place(x=390, y=51)
        Button(self.root, text="Obnovit", command=self.load_products).place(x=455, y=51)
        Button(self.root, text="Editovat vybrane", command=self.edit_selected).place(x=535, y=51)
        Button(self.root, text="Deaktivovat", command=lambda: self.set_selected_active(False)).place(x=670, y=51)
        Button(self.root, text="Aktivovat", command=lambda: self.set_selected_active(True)).place(x=770, y=51)

        self.tree = Treeview(self.root, columns=COLUMNS, show="headings", height=24)
        for col in COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150 if col in {"name", "category"} else 110)
        self.tree.place(x=12, y=90, width=1070, height=500)
        self.tree.bind("<Double-1>", lambda _event: self.edit_selected())

        Label(self.root, textvariable=self.status).place(x=12, y=605)
        self.load_products()

    def load_products(self) -> None:
        try:
            service = ProductService(self.db_path)
            try:
                rows = service.search(self.search_text.get(), limit=1000)
            finally:
                service.close()

            for item in self.tree.get_children():
                self.tree.delete(item)
            for row in rows:
                values = [row[col] for col in COLUMNS]
                self.tree.insert("", "end", values=values)
            self.status.set(f"Nacitane produkty: {len(rows)}")
        except Exception as exc:
            messagebox.showerror("Chyba", str(exc))

    def selected_code(self) -> str | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Vyber produkt", "Najprv vyber produkt v tabulke.")
            return None
        values = self.tree.item(selected[0], "values")
        return str(values[0])

    def set_selected_active(self, active: bool) -> None:
        code = self.selected_code()
        if not code:
            return
        service = ProductService(self.db_path)
        try:
            service.set_active([code], active)
        finally:
            service.close()
        self.load_products()

    def edit_selected(self) -> None:
        code = self.selected_code()
        if not code:
            return
        service = ProductService(self.db_path)
        try:
            row = service.db.get_product(code)
        finally:
            service.close()
        if not row:
            return
        ProductEditWindow(self, row)

    def mainloop(self) -> None:
        self.root.mainloop()


class ProductEditWindow:
    FIELDS = ["name", "manufacturer", "supplier", "category", "purchase_price", "sale_price", "stock", "seo_title", "meta_description", "image_url"]

    def __init__(self, editor: ProductEditor, row) -> None:
        self.editor = editor
        self.code = row["code"]
        self.window = Toplevel(editor.root)
        self.window.title(f"Editacia produktu {self.code}")
        self.window.geometry("760x520")
        self.values: dict[str, StringVar] = {}

        Label(self.window, text=f"Kod: {self.code}", font=("Arial", 12, "bold")).place(x=12, y=12)
        y = 50
        for field in self.FIELDS:
            Label(self.window, text=field).place(x=12, y=y)
            var = StringVar(value=str(row[field] if row[field] is not None else ""))
            self.values[field] = var
            Entry(self.window, textvariable=var, width=80).place(x=160, y=y)
            y += 38

        Button(self.window, text="Ulozit", width=18, command=self.save).place(x=300, y=455)
        Button(self.window, text="Zavriet", width=18, command=self.window.destroy).place(x=450, y=455)

    def save(self) -> None:
        service = ProductService(self.editor.db_path)
        try:
            for field, var in self.values.items():
                service.update_field(self.code, field, var.get())
        finally:
            service.close()
        self.editor.load_products()
        self.window.destroy()


if __name__ == "__main__":
    ProductEditor().mainloop()
