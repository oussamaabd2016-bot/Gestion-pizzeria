"""Stock management with edit and supplier reorder export."""

import tkinter as tk
from tkinter import messagebox, ttk

from pizza_express.database.db import get_db
from pizza_express.database.models import Ingredient
from pizza_express.logic.reports import export_reorder_slip, export_stock_csv
from pizza_express.ui.theme import get_colors, section_title, styled_button
from pizza_express.ui.widgets import NumericEntry


class StockFrame(tk.Frame):
    def __init__(self, parent) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        section_title(self, "Stock & ingredients").pack(anchor="w", padx=20, pady=(12, 8))
        bar = tk.Frame(self, bg=c["bg"])
        bar.pack(fill="x", padx=20, pady=4)
        styled_button(bar, "Exporter CSV", self._export_csv, primary=False).pack(side="left", padx=4)
        styled_button(bar, "Exporter bon de commande fournisseur", self._reorder, primary=False).pack(side="left", padx=4)
        styled_button(bar, "Modifier selection", self._edit).pack(side="right", padx=4)
        styled_button(bar, "Supprimer", self._delete).pack(side="right", padx=4)
        styled_button(bar, "+ Ingredient", self._add).pack(side="right", padx=4)

        self.tree = ttk.Treeview(
            self,
            columns=("nom", "stock", "min", "alerte", "prix", "valorise", "fournisseur"),
            show="headings", height=16,
        )
        for col, h in [("nom", "Ingredient"), ("stock", "Stock"), ("min", "Min"), ("alerte", "Alerte"),
                       ("prix", "Prix/u"), ("valorise", "Valorise MAD"), ("fournisseur", "Fournisseur")]:
            self.tree.heading(col, text=h)
        self.tree.pack(fill="both", expand=True, padx=20, pady=8)
        self.refresh()

    def refresh(self) -> None:
        with get_db().cursor() as cur:
            cur.execute(
                """SELECT i.*, f.nom AS fnom FROM INGREDIENT i
                   LEFT JOIN FOURNISSEUR f ON f.id_fournisseur = i.id_fournisseur ORDER BY i.nom"""
            )
            rows = cur.fetchall()
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            ing = Ingredient(
                id_ingredient=r["id_ingredient"], nom=r["nom"],
                stock_actuel=r["stock_actuel"], stock_min=r["stock_min"],
                prix_unitaire=r["prix_unitaire"], id_fournisseur=r["id_fournisseur"],
            )
            alert = ing.alert_level
            tag = "red" if alert == "RED" else ("orange" if alert == "ORANGE" else "")
            self.tree.insert(
                "", "end", iid=r["id_ingredient"],
                values=(
                    r["nom"], f"{r['stock_actuel']:.1f}", f"{r['stock_min']:.1f}",
                    alert, f"{r['prix_unitaire']:.2f}", f"{ing.valorized:.2f}", r["fnom"] or "—",
                ),
                tags=(tag,),
            )
        self.tree.tag_configure("red", background="#FFCDD2")
        self.tree.tag_configure("orange", background="#FFE0B2")

    def _export_csv(self) -> None:
        messagebox.showinfo("Export", f"Fichier: {export_stock_csv()}")

    def _reorder(self) -> None:
        """Export CSV des ingredients a commander chez le fournisseur."""
        path = export_reorder_slip()
        if path:
            messagebox.showinfo(
                "Bon de commande",
                f"Liste des ingredients sous le seuil minimum.\n\nFichier:\n{path}",
            )
        else:
            messagebox.showinfo("Bon de commande", "Tous les stocks sont au-dessus du minimum.")

    def _add(self) -> None:
        IngredientForm(self, on_save=self.refresh)

    def _edit(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Stock", "Selectionnez un ingredient.")
            return
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM INGREDIENT WHERE id_ingredient=?", (int(sel[0]),))
            row = cur.fetchone()
        if row:
            IngredientForm(self, row=dict(row), on_save=self.refresh)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Stock", "Selectionnez un ingredient.")
            return
        iid = int(sel[0])
        try:
            with get_db().cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM COMPOSITION WHERE id_ingredient=?", (iid,))
                if cur.fetchone()[0] > 0:
                    messagebox.showerror("Erreur", "Cet ingredient est utilise dans des recettes. Supprimez les compositions d'abord.")
                    return
                
                if not messagebox.askyesno("Confirmer", "Supprimer definitivement cet ingredient ?"):
                    return
                
                cur.execute("DELETE FROM INGREDIENT WHERE id_ingredient=?", (iid,))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de supprimer l'ingredient: {e}")


class IngredientForm(tk.Toplevel):
    def __init__(self, parent, row: dict | None = None, on_save=None) -> None:
        super().__init__(parent)
        self.row = row
        self.on_save = on_save
        self.title("Ingredient")
        c = get_colors()
        self.configure(bg=c["bg"])
        f = tk.Frame(self, padx=20, pady=16, bg=c["bg"])
        f.pack()
        self.nom = tk.StringVar(value=row["nom"] if row else "")
        self.stock = tk.StringVar(value=str(row["stock_actuel"] if row else 0))
        self.smin = tk.StringVar(value=str(row["stock_min"] if row else 10))
        self.prix = tk.StringVar(value=str(row["prix_unitaire"] if row else 1))
        self.fourn = tk.StringVar(value=str(row["id_fournisseur"] if row and row.get("id_fournisseur") else 1))

        # Name field - Accepts letters and text
        tk.Label(f, text="Nom", bg=c["bg"], fg=c["text"]).pack(anchor="w")
        tk.Entry(f, textvariable=self.nom, font=("Segoe UI", 11)).pack(fill="x", pady=(2, 8))

        # Numeric fields
        for lbl, var in [("Stock actuel", self.stock), ("Stock minimum", self.smin), ("Prix unitaire", self.prix), ("ID Fournisseur", self.fourn)]:
            tk.Label(f, text=lbl, bg=c["bg"], fg=c["text"]).pack(anchor="w")
            NumericEntry(f, textvariable=var).pack(fill="x", pady=(2, 8))

        def save():
            with get_db().cursor() as cur:
                if row:
                    cur.execute(
                        """UPDATE INGREDIENT SET nom=?, stock_actuel=?, stock_min=?, prix_unitaire=?, id_fournisseur=?
                           WHERE id_ingredient=?""",
                        (self.nom.get(), float(self.stock.get()), float(self.smin.get()),
                         float(self.prix.get()), int(self.fourn.get() or 1), row["id_ingredient"]),
                    )
                else:
                    cur.execute(
                        """INSERT INTO INGREDIENT (nom, stock_actuel, stock_min, prix_unitaire, id_fournisseur)
                           VALUES (?,?,?,?,?)""",
                        (self.nom.get(), float(self.stock.get()), float(self.smin.get()),
                         float(self.prix.get()), int(self.fourn.get() or 1)),
                    )
            self.destroy()
            if on_save:
                on_save()

        styled_button(f, "Enregistrer", save).pack(pady=12)
        self.grab_set()
