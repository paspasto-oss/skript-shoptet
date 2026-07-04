from __future__ import annotations

import json
import threading
import traceback
from pathlib import Path
from tkinter import BooleanVar, Button, Checkbutton, Entry, Label, StringVar, Tk, filedialog, messagebox

from shoptet_importer.export import write_csv, write_report
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
        self.root.geometry("620x360")
        self.root.resizable(False, False)

        self.pdf_path = StringVar()
        self.out_dir = StringVar(value=str(Path("output").resolve()))
        self.limit_10 = BooleanVar(value=True)
        self.status = StringVar(value="Vyber PDF cennik Midea a klikni Generovat.")

        Label(self.root, text="Spektra Product Manager", font=("Arial", 18, "bold")).place(x=20, y=18)
        Label(self.root, text="Dodavatel: Midea / Planning & Trading", font=("Arial", 10)).place(x=22, y=55)

        Label(self.root, text="PDF cennik:").place(x=22, y=95)
        Entry(self.root, textvariable=self.pdf_path, width=62).place(x=120, y=95)
        Button(self.root, text="Vybrat PDF", command=self.choose_pdf).place(x=505, y=91)

        Label(self.root, text="Vystupny priecinok:").place(x=22, y=135)
        Entry(self.root, textvariable=self.out_dir, width=62).place(x=120, y=135)
        Button(self.root, text="Vybrat", command=self.choose_out_dir).place(x=505, y=131)

        Checkbutton(self.root, text="Test iba 10 produktov", variable=self.limit_10).place(x=120, y=175)
        Button(self.root, text="GENEROVAT IMPORT", width=24, height=2, command=self.run).place(x=215, y=220)
        Label(self.root, textvariable=self.status, wraplength=560, justify="left").place(x=25, y=295)

    def choose_pdf(self) -> None:
        selected = filedialog.askopenfilename(title="Vyber PDF cennik", filetypes=[("PDF subory", "*.pdf")])
        if selected:
            self.pdf_path.set(selected)

    def choose_out_dir(self) -> None:
        selected = filedialog.askdirectory(title="Vyber vystupny priecinok")
        if selected:
            self.out_dir.set(selected)

    def run(self) -> None:
        pdf = Path(self.pdf_path.get())
        if not pdf.exists():
            messagebox.showerror(APP_TITLE, "Vyber platny PDF subor.")
            return
        out_dir = Path(self.out_dir.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        self.status.set("Spracuvam PDF...")
        threading.Thread(target=self._run_worker, args=(pdf, out_dir), daemon=True).start()

    def _run_worker(self, pdf: Path, out_dir: Path) -> None:
        try:
            config = load_config()
            limit = 10 if self.limit_10.get() else None
            products, skipped = extract_products(pdf, config, limit=limit)
            if not products:
                raise RuntimeError("Parser nenasiel ziadne kompletne sety.")
            codes = [p.code for p in products]
            duplicates = sorted({c for c in codes if codes.count(c) > 1})
            if duplicates:
                raise RuntimeError("Duplicitne kody: " + ", ".join(duplicates[:20]))
            suffix = "test_10" if limit else "full"
            csv_path = out_dir / f"shoptet_midea_{suffix}.csv"
            report_path = out_dir / f"kontrola_midea_{suffix}.csv"
            write_csv(products, csv_path)
            write_report(products, skipped, report_path)
            self.status.set(f"Hotovo: {len(products)} produktov. CSV: {csv_path}")
            messagebox.showinfo(APP_TITLE, f"Import vytvoreny.\n\nProdukty: {len(products)}\nCSV: {csv_path}\nKontrola: {report_path}")
        except Exception as exc:
            traceback.print_exc()
            self.status.set("Chyba pri spracovani.")
            messagebox.showerror(APP_TITLE, str(exc))

    def mainloop(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().mainloop()
