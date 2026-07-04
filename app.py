from __future__ import annotations

import json
import threading
import traceback
from pathlib import Path
from tkinter import BooleanVar, Button, Checkbutton, Entry, Label, StringVar, Tk, filedialog, messagebox

from shoptet_importer.adapters import midea_products_to_universal
from shoptet_importer.database import ProductDatabase
from shoptet_importer.db_export import export_db_to_shoptet_csv
from shoptet_importer.export import write_report
from shoptet_importer.midea_pdf import extract_products

APP_TITLE = "Spektra Product Manager"


def load_config() -> dict:
    path = Path("config.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


class App:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("720x430")
        self.root.resizable(False, False)

        self.pdf_path = StringVar()
        self.out_dir = StringVar(value=str(Path("output").resolve()))
        self.db_path = StringVar(value=str(Path("data/products.sqlite").resolve()))
        self.limit_10 = BooleanVar(value=True)
        self.status = StringVar(value="Vyber PDF cennik Midea a klikni Importovat do databazy.")

        Label(self.root, text="Spektra Product Manager", font=("Arial", 18, "bold")).place(x=20, y=18)
        Label(self.root, text="Univerzalny produktovy importer pre Shoptet", font=("Arial", 10)).place(x=22, y=55)

        Label(self.root, text="PDF cennik:").place(x=22, y=95)
        Entry(self.root, textvariable=self.pdf_path, width=74).place(x=140, y=95)
        Button(self.root, text="Vybrat PDF", command=self.choose_pdf).place(x=610, y=91)

        Label(self.root, text="Databaza:").place(x=22, y=135)
        Entry(self.root, textvariable=self.db_path, width=74).place(x=140, y=135)
        Button(self.root, text="Vybrat", command=self.choose_db).place(x=610, y=131)

        Label(self.root, text="Vystup:").place(x=22, y=175)
        Entry(self.root, textvariable=self.out_dir, width=74).place(x=140, y=175)
        Button(self.root, text="Vybrat", command=self.choose_out_dir).place(x=610, y=171)

        Checkbutton(self.root, text="Test iba 10 produktov", variable=self.limit_10).place(x=140, y=215)

        Button(self.root, text="1. IMPORTOVAT PDF DO DB", width=28, height=2, command=self.import_pdf_to_db).place(x=120, y=260)
        Button(self.root, text="2. EXPORT DB DO SHOPTET CSV", width=30, height=2, command=self.export_db).place(x=380, y=260)

        Label(self.root, textvariable=self.status, wraplength=660, justify="left").place(x=25, y=345)

    def choose_pdf(self) -> None:
        selected = filedialog.askopenfilename(title="Vyber PDF cennik", filetypes=[("PDF subory", "*.pdf")])
        if selected:
            self.pdf_path.set(selected)

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

    def import_pdf_to_db(self) -> None:
        pdf = Path(self.pdf_path.get())
        if not pdf.exists():
            messagebox.showerror(APP_TITLE, "Vyber platny PDF subor.")
            return
        db_path = Path(self.db_path.get())
        self.status.set("Spracuvam PDF a zapisujem produkty do databazy...")
        threading.Thread(target=self._import_worker, args=(pdf, db_path), daemon=True).start()

    def export_db(self) -> None:
        db_path = Path(self.db_path.get())
        if not db_path.exists():
            messagebox.showerror(APP_TITLE, "Databaza este neexistuje. Najprv importuj PDF do DB.")
            return
        out_dir = Path(self.out_dir.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        self.status.set("Exportujem databazu do Shoptet CSV...")
        threading.Thread(target=self._export_worker, args=(db_path, out_dir), daemon=True).start()

    def _import_worker(self, pdf: Path, db_path: Path) -> None:
        try:
            config = load_config()
            limit = 10 if self.limit_10.get() else None
            parsed, skipped = extract_products(pdf, config, limit=limit)
            if not parsed:
                raise RuntimeError("Parser nenasiel ziadne kompletne sety.")

            universal_products = midea_products_to_universal(parsed)
            db = ProductDatabase(db_path)
            try:
                imported = db.upsert_many(universal_products)
                db.log_import("Midea/MDV PDF", imported, len(skipped))
            finally:
                db.close()

            out_dir = Path(self.out_dir.get())
            out_dir.mkdir(parents=True, exist_ok=True)
            report_path = out_dir / ("kontrola_midea_test_10.csv" if limit else "kontrola_midea_full.csv")
            write_report(parsed, skipped, report_path)

            self.status.set(f"Hotovo: {imported} produktov ulozenych do DB. Kontrola: {report_path}")
            messagebox.showinfo(APP_TITLE, f"Import do databazy hotovy.\n\nProdukty: {imported}\nPreskocene riadky: {len(skipped)}\nDB: {db_path}")
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
