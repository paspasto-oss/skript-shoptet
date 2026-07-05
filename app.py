from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path
from tkinter import BooleanVar, Button, Checkbutton, Entry, Label, StringVar, Tk, filedialog, messagebox

from shoptet_importer.database import ProductDatabase
from shoptet_importer.db_export import export_db_to_shoptet_csv
from shoptet_importer.import_router import import_file_to_products
from shoptet_importer.shoptet_ready import create_shoptet_validation_report
from shoptet_importer.validation import validate_products

APP_TITLE = "Spektra Product Manager"


class App:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("820x500")
        self.root.resizable(False, False)

        self.input_path = StringVar()
        self.out_dir = StringVar(value=str(Path("output").resolve()))
        self.db_path = StringVar(value=str(Path("data/products.sqlite").resolve()))
        self.limit_10 = BooleanVar(value=True)
        self.status = StringVar(value="Vyber cennik PDF/Excel/CSV/XML a klikni Importovat do databazy.")

        Label(self.root, text="Spektra Product Manager", font=("Arial", 18, "bold")).place(x=20, y=18)
        Label(self.root, text="PIM jadro: import cennikov, produktova databaza, export Shoptet", font=("Arial", 10)).place(x=22, y=55)

        Label(self.root, text="Cennik:").place(x=22, y=95)
        Entry(self.root, textvariable=self.input_path, width=82).place(x=140, y=95)
        Button(self.root, text="Vybrat", command=self.choose_input).place(x=690, y=91)

        Label(self.root, text="Databaza:").place(x=22, y=135)
        Entry(self.root, textvariable=self.db_path, width=82).place(x=140, y=135)
        Button(self.root, text="Vybrat", command=self.choose_db).place(x=690, y=131)

        Label(self.root, text="Vystup:").place(x=22, y=175)
        Entry(self.root, textvariable=self.out_dir, width=82).place(x=140, y=175)
        Button(self.root, text="Vybrat", command=self.choose_out_dir).place(x=690, y=171)

        Checkbutton(self.root, text="Test iba 10 produktov", variable=self.limit_10).place(x=140, y=215)

        Button(self.root, text="1. IMPORTOVAT CENNIK DO DB", width=30, height=2, command=self.import_to_db).place(x=55, y=260)
        Button(self.root, text="2. PRODUKTOVY EDITOR", width=26, height=2, command=self.open_editor).place(x=305, y=260)
        Button(self.root, text="3. EXPORT PRE SHOPTET", width=30, height=2, command=self.export_db).place(x=530, y=260)

        Button(self.root, text="KONTROLA SHOPTET IMPORTU", width=34, command=self.validate_shoptet).place(x=290, y=325)

        Label(self.root, textvariable=self.status, wraplength=760, justify="left").place(x=25, y=390)

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

    def open_editor(self) -> None:
        db_path = Path(self.db_path.get())
        if not db_path.exists():
            messagebox.showerror(APP_TITLE, "Databaza este neexistuje. Najprv importuj cennik do DB.")
            return
        from product_editor import ProductEditor

        editor = ProductEditor(db_path)
        editor.mainloop()

    def export_db(self) -> None:
        db_path = Path(self.db_path.get())
        if not db_path.exists():
            messagebox.showerror(APP_TITLE, "Databaza este neexistuje. Najprv importuj cennik do DB.")
            return
        out_dir = Path(self.out_dir.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        self.status.set("Exportujem databazu do Shoptet CSV...")
        threading.Thread(target=self._export_worker, args=(db_path, out_dir), daemon=True).start()

    def validate_shoptet(self) -> None:
        db_path = Path(self.db_path.get())
        if not db_path.exists():
            messagebox.showerror(APP_TITLE, "Databaza este neexistuje. Najprv importuj cennik do DB.")
            return
        out_dir = Path(self.out_dir.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        self.status.set("Kontrolujem pripravenost produktov pre Shoptet import...")
        threading.Thread(target=self._validation_worker, args=(db_path, out_dir), daemon=True).start()

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
            csv_path = out_dir / "shoptet_products_import.csv"
            report_path = out_dir / "shoptet_import_kontrola.csv"
            count = export_db_to_shoptet_csv(db_path, csv_path, active_only=True)
            _, errors = create_shoptet_validation_report(db_path, report_path, active_only=True)
            if errors:
                self.status.set(f"Export hotovy, ale kontrola nasla chyby: {errors}. CSV: {csv_path}. Report: {report_path}")
                messagebox.showwarning(APP_TITLE, f"Export hotovy, ale kontrola nasla chyby.\n\nProdukty: {count}\nChybne produkty: {errors}\nCSV: {csv_path}\nReport: {report_path}")
            else:
                self.status.set(f"Hotovo: {count} produktov pripravenych na import do Shoptetu. CSV: {csv_path}")
                messagebox.showinfo(APP_TITLE, f"Subor pre Shoptet je pripraveny.\n\nProdukty: {count}\nCSV: {csv_path}\nKontrola: bez chyb")
        except Exception as exc:
            traceback.print_exc()
            self.status.set("Chyba pri exporte do Shoptetu.")
            messagebox.showerror(APP_TITLE, str(exc))

    def _validation_worker(self, db_path: Path, out_dir: Path) -> None:
        try:
            report_path = out_dir / "shoptet_import_kontrola.csv"
            count, errors = create_shoptet_validation_report(db_path, report_path, active_only=True)
            self.status.set(f"Kontrola hotova. Produkty: {count}. Chybne: {errors}. Report: {report_path}")
            messagebox.showinfo(APP_TITLE, f"Kontrola Shoptet importu hotova.\n\nProdukty: {count}\nChybne produkty: {errors}\nReport: {report_path}")
        except Exception as exc:
            traceback.print_exc()
            self.status.set("Chyba pri kontrole Shoptet importu.")
            messagebox.showerror(APP_TITLE, str(exc))

    def mainloop(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--editor":
        from product_editor import ProductEditor

        db_arg = sys.argv[2] if len(sys.argv) > 2 else "data/products.sqlite"
        ProductEditor(db_arg).mainloop()
    else:
        App().mainloop()
