"""Reports export UI."""

import tkinter as tk
from tkinter import messagebox, ttk

from pizza_express.logic.reports import (
    employee_performance,
    export_pdf_report,
    export_sales_csv,
    export_stock_csv,
    sales_summary,
    stock_valorized_report,
)
from pizza_express.ui.theme import styled_button


class ReportsFrame(ttk.Frame):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        ttk.Label(self, text="Rapports", style="Title.TLabel").pack(anchor="w", padx=12, pady=8)
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=8)
        styled_button(btns, "Ventes CSV", self._sales_csv, primary=False).pack(side="left", padx=4)
        styled_button(btns, "Stock CSV", self._stock_csv, primary=False).pack(side="left", padx=4)
        styled_button(btns, "PDF Resume", self._pdf, primary=False).pack(side="left", padx=4)

        self.preview = tk.Text(self, height=20, wrap="word", font=("Consolas", 10))
        self.preview.pack(fill="both", expand=True, padx=12, pady=8)
        self.refresh_preview()

    def refresh_preview(self) -> None:
        sales = sales_summary()
        stock = stock_valorized_report()
        emp = employee_performance()
        lines = [
            "=== VENTES ===",
            f"Periode actuelle: {sales['current']:.2f} MAD",
            f"Meme periode N-1: {sales['previous']:.2f} MAD ({sales['change_pct']:+.1f}%)",
            "",
            "=== STOCK VALORISE ===",
        ]
        total_v = sum(r["valorise"] for r in stock)
        lines.append(f"Total valorise: {total_v:.2f} MAD")
        for s in stock[:8]:
            lines.append(f"  {s['nom']}: {s['valorise']:.2f} MAD")
        lines.append("\n=== EMPLOYES ===")
        for e in emp:
            lines.append(f"  {e['employe']}: {e['nb_commandes']} cmd, CA {e['ca']:.2f}")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(lines))

    def _sales_csv(self) -> None:
        messagebox.showinfo("Export", export_sales_csv())

    def _stock_csv(self) -> None:
        messagebox.showinfo("Export", export_stock_csv())

    def _pdf(self) -> None:
        content = self.preview.get("1.0", "end").strip().split("\n")
        path = export_pdf_report("Rapport PizzaExpress", content)
        messagebox.showinfo("PDF", f"Fichier: {path}")
