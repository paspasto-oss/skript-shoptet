from __future__ import annotations

import threading
import traceback
from pathlib import Path
from tkinter import BooleanVar, Button, Checkbutton, Entry, Label, StringVar, Tk, filedialog, messagebox

from shoptet_importer.database import ProductDatabase
from shoptet_importer.db_export import export_db_to_shoptet_csv
from shoptet_importer.import_router import import_file_to_products
from shoptet_importer.validation import validate_products

APP_TITLE = "Spektra Product Manager"


class App:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("760x450")
        self.root.resizable(False, False)

        self.input_path = StringVar()
        self.out_dir = StringVar(value=str(Path("output").resolve()))
        self.db_path = StringVar(value=str(Path("data/products.sqlite").resolve()))
        self.limit_10 = BooleanVar(value=True)
        self.status = StringVar(value="Vyber cennik PDF/Excel/CSV/XML a klikni Importovat do databazy.")

        Label(self.root, text="Spektra Product Manager", font=("Arial", 18, "bold")).place(x=20, y=18)
        Label(self.root, text="PIM jadro: import cennikov, produktova databaza, export Shoptet", font=("Arial", 10)).place(x=22, y=55)

        Label(self.root, text="Cennik:").place(x=22, y=95)
        Entry(self.root, textvariable=self.input_path, width=78).place(x=140, y=95)
        Button(self.root, text="Vybrat", command=self.choose_input).place(x=640, y=91)

        Label(self.root, text="Databaza:").place(x=22, y=135)
        Entry(self.root, textvariable=self.db_path, width=78).place(x=140, y=135)
        Button(self.root, text="Vybrat", command=self.choose_db).place(x=640, y=131)

        Label(self.root, text="Vystup:").place(x=22, y=175)
        Entry(self.root, textvariable=self.out_dir, width=78).place(x=140, y=175)
        Button(self.root, text="Vybrat", command=self.choose_out_dir).place(x=640, y=171)

        Checkbutton(self.root, text="Test iba 10 produktov", variable=self.limit_10).place(x=140, y=215)

        Button(self.root, text="1. IMPORTOVAT CENNIK DO DB", width=30, height=2, command=self.import_to_db).place(x=110, y=260)
        Button(self.root, text="2. EXPORT DB DO SHOPTET CSV", width=30, height=2, command=self.export_db).place(x=410, y=260)

        Label(self.root, textvariable=self.status, wraplength=700, justify="left").place(x=25, y=345)

    def choose_input(self) -> None:
        selected = filedialog.askopenfilename(
            title="Vyber cennik",
            filetypes=[
                ("Podporovane subory", "*.pdf *.csv *.xlsx *.xls *.xml"),
                ("PDF subory", "*.pdf"),
                ("Excel subory", "*.xlsx *.xls"),
                ("CSV subory", "*.csv"),
                ("XML subory", "*.xml"),
                ("Vsetky subory", "*.*"),
            ],
        )
        if selected:
            self.input_path.set(selected)

    def choose_out_dir(self) -> None:
        selected = filedialog.askdirectory(title="Vyber vystupny priecinok")
        if selected:
            self.out_dir.set(selected)

    def choose_db(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="Vyber alebo vytvor databazu",
            defaultextension=".sqlite",
            filetypes=[("SQLite databaza", "*.sqlite"), ("Vsetky subory", "*.*")],
        )
        if selected:
            self.db_path.set(selected)

    def import_to_db(self) -> None:
        input_file = Path(self.input_path.get())
        if not input_file.exists():
            messagebox.showerror(APP_TITLE, "Vyber platny vstupny subor.")
            return
        db_path = Path(self.db_path.get())
        self.status.set("Importujem cennik do produktovej databazy...")
        threading.Thread(target=self._import_worker, args=(input_file, db_path), daemon=True).start()

    def export_db(self) -> None:
        db_path = Path(self.db_path.get())
        if not db_path.exists():
            messagebox.showerror(APP_TITLE, "Databaza este neexistuje. Najprv importuj cennik do DB.")
            return
        out_dir = Path(self.out_dir.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        self.status.set("Exportujem databazu do Shoptet CSV...")
        threading.Thread(target=self._export_worker, args=(db_path, out_dir), daemon=True).start()

    def _import_worker(self, input_file: Path, db_path: Path) -> None:
        try:
            limit = 10 if self.limit_10.get() else None
            products, skipped = import_file_to_products(input_file, limit=limit)
            if not products:
                raise RuntimeError("Importer nenasiel ziadne produkty. Treba doplnit pravidlo pre tento format cennika.")

            errors = validate_products(products)
            blocking_errors = [e for e in errors if e.get("field") in {"code", "name"}]
            if blocking_errors:
                raise RuntimeError(f"Import obsahuje kriticke chyby: {len(blocking_errors)}")

            db = ProductDatabase(db_path)
            try:
                imported = db.upsert_many(products)
                db.log_import(str(input_file), imported, len(skipped))
            finally:
                db.close()

            self.status.set(f"Hotovo: {imported} produktov ulozenych do DB. Preskocene: {len(skipped)}. Varovania: {len(errors)}")
            messagebox.showinfo(
                APP_TITLE,
                f"Import do databazy hotovy.\n\nProdukty: {imported}\nPreskocene riadky: {len(skipped)}\nVarovania: {len(errors)}\nDB: {db_path}",
            )
        except Exception as exc:
            traceback.print_exc()
            self.status.set("Chyba pri importe do databazy.")
            messagebox.showerror(APP_TITLE, str(exc))

    def _export_worker(self, db_path: Path, out_dir: Path) -> None:
        try:
            csv_path = out_dir / "shoptet_products_from_db.csv"
            count = export_db_to_shoptet_csv(db_path, csv_path, active_only=True)
            self.status.set(f"Hotovo: {count} produktov exportovanych do {csv_path}")
            messagebox.showinfo(APP_TITLE, f"Export pre Shoptet hotovy.\n\nProdukty: {count}\nCSV: {csv_path}")
        except Exception as exc:
            traceback.print_exc()
            self.status.set("Chyba pri exporte do Shoptetu.")
            messagebox.showerror(APP_TITLE, str(exc))

    def mainloop(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().mainloop()
