"""Menu: products with images, activate/deactivate toggle, category carousel."""

from __future__ import annotations

import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pizza_express.config import IMAGES_DIR
from pizza_express.database.db import get_db
from pizza_express.database.models import Categorie, Produit
from pizza_express.logic.validators import validate_positive_number
from pizza_express.ui.theme import get_colors, make_card, section_title, styled_button
from pizza_express.ui.widgets import NumericEntry


class MenuFrame(tk.Frame):
    def __init__(self, parent) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        section_title(self, "Menu").pack(anchor="w", padx=20, pady=(12, 8))
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=8)
        self.prod_tab = tk.Frame(nb, bg=c["bg"])
        self.cat_tab = tk.Frame(nb, bg=c["bg"])
        nb.add(self.prod_tab, text="Produits")
        nb.add(self.cat_tab, text="Categories")
        self._build_products()
        self._build_categories()

    def _build_products(self) -> None:
        bar = tk.Frame(self.prod_tab, bg=get_colors()["bg"])
        bar.pack(fill="x", padx=8, pady=4)
        styled_button(bar, "+ Ajouter", self._add_prod).pack(side="left", padx=4)
        styled_button(bar, "Modifier", self._edit_prod).pack(side="left", padx=4)
        styled_button(bar, "Supprimer", self._delete_prod).pack(side="left", padx=4)
        self.ptree = ttk.Treeview(
            self.prod_tab,
            columns=("nom", "s", "m", "l", "statut"),
            show="headings", height=12,
        )
        for col, h in [("nom", "Nom"), ("s", "S"), ("m", "M"), ("l", "L"), ("statut", "Statut")]:
            self.ptree.heading(col, text=h)
        self.ptree.tag_configure("inactive", background="#E8E8E8", foreground="#888888")
        self.ptree.pack(fill="both", expand=True, padx=8, pady=4)
        self._load_products()

    def _load_products(self) -> None:
        self.ptree.delete(*self.ptree.get_children())
        with get_db().cursor() as cur:
            cur.execute(
                """SELECT * FROM PRODUIT
                   ORDER BY deleted ASC, disponible DESC, nom ASC"""
            )
            for r in cur.fetchall():
                statut = "Actif" if r["deleted"] == 0 and r["disponible"] else "Inactif"
                tags = () if statut == "Actif" else ("inactive",)
                self.ptree.insert(
                    "", "end", iid=str(r["id_produit"]),
                    values=(r["nom"], r["prix_small"], r["prix_medium"], r["prix_large"], statut),
                    tags=tags,
                )

    def _selected_pid(self) -> int | None:
        sel = self.ptree.selection()
        return int(sel[0]) if sel else None

    def _add_prod(self) -> None:
        ProductForm(self.winfo_toplevel(), on_save=self._load_products)

    def _edit_prod(self) -> None:
        pid = self._selected_pid()
        if not pid:
            messagebox.showinfo("Menu", "Selectionnez un produit.", parent=self.winfo_toplevel())
            return
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM PRODUIT WHERE id_produit=?", (pid,))
            row = cur.fetchone()
        if row:
            p = Produit(**{k: row[k] for k in Produit.__dataclass_fields__ if k in row.keys()})
            ProductForm(self.winfo_toplevel(), produit=p, on_save=self._load_products)

    def _delete_prod(self) -> None:
        pid = self._selected_pid()
        if not pid:
            messagebox.showinfo("Menu", "Selectionnez un produit.", parent=self.winfo_toplevel())
            return
        
        try:
            with get_db().cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM LIGNE_COMMANDE WHERE id_produit=?", (pid,))
                if cur.fetchone()[0] > 0:
                    messagebox.showerror("Erreur", "Ce produit est present dans des commandes. Desactivez-le plutot.", parent=self.winfo_toplevel())
                    return

                if not messagebox.askyesno("Confirmer", "Supprimer definitivement ce produit ?", parent=self.winfo_toplevel()):
                    return
                
                # Nettoyage de la composition avant suppression du produit
                cur.execute("DELETE FROM COMPOSITION WHERE id_produit=?", (pid,))
                cur.execute("DELETE FROM PRODUIT WHERE id_produit=?", (pid,))
            
            self._load_products()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de supprimer le produit: {e}", parent=self.winfo_toplevel())

    def _build_categories(self) -> None:
        c = get_colors()
        top = tk.Frame(self.cat_tab, bg=c["bg"])
        top.pack(fill="x", padx=8, pady=4)
        styled_button(top, "+ Categorie", self._add_cat, primary=False).pack(side="right")
        self.cat_carousel = tk.Frame(self.cat_tab, bg=c["bg"])
        self.cat_carousel.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_carousel()

    def _refresh_carousel(self) -> None:
        c = get_colors()
        for w in self.cat_carousel.winfo_children():
            w.destroy()
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM CATEGORIE ORDER BY nom")
            cats = cur.fetchall()
        canvas = tk.Canvas(self.cat_carousel, bg=c["bg"], highlightthickness=0, height=320)
        hscroll = ttk.Scrollbar(self.cat_carousel, orient="horizontal", command=canvas.xview)
        inner = tk.Frame(canvas, bg=c["bg"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(xscrollcommand=hscroll.set)
        canvas.pack(fill="both", expand=True)
        hscroll.pack(fill="x")
        for i, cat in enumerate(cats):
            card = make_card(inner, padx=12, pady=10)
            card.grid(row=0, column=i, padx=10, sticky="n")
            tk.Label(card, text=cat["nom"], font=("Segoe UI", 12, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="w")
            with get_db().cursor() as cur:
                cur.execute(
                    "SELECT nom, prix_medium FROM PRODUIT WHERE id_categorie=? AND deleted=0 ORDER BY nom",
                    (cat["id_categorie"],),
                )
                prods = cur.fetchall()
            for p in prods[:6]:
                tk.Label(card, text=f"  • {p['nom']} ({p['prix_medium']:.0f} MAD)", bg=c["card"], fg=c["text"]).pack(anchor="w")

    def _add_cat(self) -> None:
        root = self.winfo_toplevel()
        dlg = tk.Toplevel(root)
        dlg.transient(root)
        dlg.title("Categorie")
        nom, desc = tk.StringVar(), tk.StringVar()
        f = tk.Frame(dlg, padx=16, pady=16)
        f.pack()
        tk.Label(f, text="Nom").pack(anchor="w")
        tk.Entry(f, textvariable=nom).pack(fill="x", pady=4)
        tk.Label(f, text="Description").pack(anchor="w")
        tk.Entry(f, textvariable=desc).pack(fill="x", pady=4)

        def save():
            if not nom.get().strip():
                messagebox.showerror("Erreur", "Nom obligatoire.", parent=dlg)
                return
            Categorie(nom=nom.get().strip(), description=desc.get()).save()
            dlg.destroy()
            self._refresh_carousel()

        styled_button(f, "OK", save).pack(pady=8)
        dlg.grab_set()


class ProductForm(tk.Toplevel):
    def __init__(self, parent, produit: Produit | None = None, on_save=None) -> None:
        super().__init__(parent)
        self.transient(parent)
        self.p = produit or Produit()
        self.on_save = on_save
        self.title("Produit")
        self.geometry("440x560")
        c = get_colors()
        self.configure(bg=c["bg"])
        f = tk.Frame(self, padx=20, pady=16, bg=c["bg"])
        f.pack(fill="both", expand=True)
        self.nom = tk.StringVar(value=self.p.nom or "")
        self.desc = tk.StringVar(value=self.p.description or "")
        self.ps = tk.StringVar(value=str(self.p.prix_small or "10"))
        self.pm = tk.StringVar(value=str(self.p.prix_medium or "15"))
        self.pl = tk.StringVar(value=str(self.p.prix_large or "20"))
        self.prep = tk.StringVar(value=str(self.p.temps_preparation or 10))
        self.allerg = tk.StringVar(value=self.p.allergenes or "")
        self.cat_var = tk.StringVar()
        self.image_path = self.p.image_path or ""
        with get_db().cursor() as cur:
            cur.execute("SELECT id_categorie, nom FROM CATEGORIE")
            self.cats = cur.fetchall()
        if self.cats:
            self.cat_var.set(str(self.cats[0]["id_categorie"]))
        if self.p.id_categorie:
            for x in self.cats:
                if x["id_categorie"] == self.p.id_categorie:
                    self.cat_var.set(f"{x['id_categorie']} - {x['nom']}")
                    break

        for lbl, var in [("Nom *", self.nom), ("Description", self.desc), ("Allergenes", self.allerg)]:
            tk.Label(f, text=lbl, bg=c["bg"], fg=c["text"]).pack(anchor="w", pady=(6, 0))
            tk.Entry(f, textvariable=var).pack(fill="x", ipady=4)
        for lbl, var in [("Prix Small (MAD)", self.ps), ("Prix Medium", self.pm), ("Prix Large", self.pl)]:
            tk.Label(f, text=lbl, bg=c["bg"], fg=c["text"]).pack(anchor="w", pady=(6, 0))
            NumericEntry(f, textvariable=var).pack(fill="x")
        tk.Label(f, text="Temps preparation (min)", bg=c["bg"], fg=c["text"]).pack(anchor="w", pady=(6, 0))
        NumericEntry(f, textvariable=self.prep).pack(fill="x")
        tk.Label(f, text="Categorie", bg=c["bg"], fg=c["text"]).pack(anchor="w", pady=(6, 0))
        ttk.Combobox(
            f, textvariable=self.cat_var,
            values=[f"{x['id_categorie']} - {x['nom']}" for x in self.cats],
            width=28, state="readonly",
        ).pack(anchor="w")
        styled_button(f, "Choisir image", self._pick_image, primary=False).pack(anchor="w", pady=8)
        self.img_lbl = tk.Label(f, text=os.path.basename(self.image_path) if self.image_path else "Aucune image", bg=c["bg"], fg=c["text_muted"])
        self.img_lbl.pack(anchor="w")
        styled_button(f, "Enregistrer", self._save).pack(fill="x", pady=12)
        styled_button(f, "Gérer Composition", self._manage_composition, primary=False).pack(fill="x", pady=4)
        self.grab_set()

    def _pick_image(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.gif")])
        if path:
            os.makedirs(IMAGES_DIR, exist_ok=True)
            dest = os.path.join(IMAGES_DIR, os.path.basename(path))
            shutil.copy2(path, dest)
            self.image_path = dest
            self.img_lbl.config(text=os.path.basename(dest))

    def _save(self) -> None:
        nom = self.nom.get().strip()
        if not nom:
            messagebox.showerror("Erreur", "Nom obligatoire.", parent=self)
            return
        for var, name in [(self.ps, "Small"), (self.pm, "Medium"), (self.pl, "Large")]:
            ok, msg, _ = validate_positive_number(var.get(), name)
            if not ok:
                messagebox.showerror("Erreur", msg, parent=self)
                return
        try:
            prep = int(self.prep.get() or 10)
        except ValueError:
            prep = 10
        cat_raw = self.cat_var.get().split(" - ")[0].strip()
        self.p.nom = nom
        self.p.description = self.desc.get()
        self.p.prix_small = float(self.ps.get().replace(",", "."))
        self.p.prix_medium = float(self.pm.get().replace(",", "."))
        self.p.prix_large = float(self.pl.get().replace(",", "."))
        self.p.temps_preparation = prep
        self.p.allergenes = self.allerg.get()
        self.p.id_categorie = int(cat_raw) if cat_raw.isdigit() else None
        self.p.image_path = self.image_path
        self.p.save()
        if self.on_save:
            self.on_save()
        self.destroy()

    def _manage_composition(self) -> None:
        if not self.p.id_produit:
            messagebox.showwarning("Attention", "Veuillez enregistrer le produit d'abord pour gérer sa composition.", parent=self)
            return
        CompositionForm(self, self.p.id_produit)


class CompositionForm(tk.Toplevel):
    def __init__(self, parent, product_id: int) -> None:
        super().__init__(parent)
        self.transient(parent)
        self.product_id = product_id
        self.title(f"Composition du produit #{product_id}")
        self.geometry("500x400")
        c = get_colors()
        self.configure(bg=c["bg"])

        main_frame = tk.Frame(self, padx=20, pady=16, bg=c["bg"])
        main_frame.pack(fill="both", expand=True)

        # Input for adding/editing ingredients
        input_frame = tk.Frame(main_frame, bg=c["bg"])
        input_frame.pack(fill="x", pady=(0, 10))

        tk.Label(input_frame, text="Ingrédient:", bg=c["bg"], fg=c["text"]).pack(side="left")
        self.ingredient_var = tk.StringVar()
        self.ingredients_data = self._load_all_ingredients()
        self.ingredient_combo = ttk.Combobox(
            input_frame, textvariable=self.ingredient_var,
            values=[f"{ing['id_ingredient']} - {ing['nom']}" for ing in self.ingredients_data],
            state="readonly", width=25
        )
        self.ingredient_combo.pack(side="left", padx=(5, 15))

        tk.Label(input_frame, text="Quantité requise:", bg=c["bg"], fg=c["text"]).pack(side="left")
        self.qty_var = tk.StringVar(value="0.0")
        self.qty_entry = NumericEntry(input_frame, textvariable=self.qty_var, width=10)
        self.qty_entry.pack(side="left", padx=(5, 0))

        # Buttons for actions
        btn_frame = tk.Frame(main_frame, bg=c["bg"])
        btn_frame.pack(fill="x", pady=(0, 10))
        styled_button(btn_frame, "Ajouter", self._add_composition).pack(side="left", padx=2)
        styled_button(btn_frame, "Modifier", self._update_composition, primary=False).pack(side="left", padx=2)
        styled_button(btn_frame, "Supprimer", self._delete_composition, primary=False).pack(side="left", padx=2)

        # Treeview for displaying composition
        self.tree = ttk.Treeview(
            main_frame,
            columns=("ingredient_name", "quantity"),
            show="headings", height=8,
        )
        self.tree.heading("ingredient_name", text="Ingrédient")
        self.tree.heading("quantity", text="Quantité requise")
        self.tree.column("quantity", width=120, stretch=False)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_composition)

        self._load_composition()
        self.grab_set()

    def _load_all_ingredients(self) -> list[dict]:
        with get_db().cursor() as cur:
            cur.execute("SELECT id_ingredient, nom FROM INGREDIENT ORDER BY nom")
            return cur.fetchall()

    def _load_composition(self) -> None:
        self.tree.delete(*self.tree.get_children())
        with get_db().cursor() as cur:
            cur.execute(
                """SELECT c.id_composition, i.nom, c.quantite_requise, i.id_ingredient
                   FROM COMPOSITION c JOIN INGREDIENT i ON c.id_ingredient = i.id_ingredient
                   WHERE c.id_produit=?""",
                (self.product_id,)
            )
            for row in cur.fetchall():
                self.tree.insert("", "end", iid=str(row["id_composition"]),
                                 values=(row["nom"], f"{row['quantite_requise']:.2f}"),
                                 tags=(row["id_ingredient"],)) # Store ingredient ID in tags

    def _on_select_composition(self, _evt=None) -> None:
        sel = self.tree.selection()
        if sel:
            item = self.tree.item(sel[0])
            ing_name = item["values"][0]
            qty = item["values"][1]
            ing_id = item["tags"][0] # Retrieve ingredient ID from tags
            self.ingredient_var.set(f"{ing_id} - {ing_name}")
            self.qty_var.set(qty)

    def _get_selected_ingredient_id(self) -> int | None:
        selected_text = self.ingredient_var.get()
        if selected_text:
            return int(selected_text.split(" - ")[0])
        return None

    def _add_composition(self) -> None:
        ing_id = self._get_selected_ingredient_id()
        if not ing_id:
            messagebox.showwarning("Erreur", "Veuillez sélectionner un ingrédient.", parent=self)
            return
        try:
            qty = float(self.qty_var.get())
            if qty <= 0:
                messagebox.showerror("Erreur", "La quantité requise doit être un nombre positif.", parent=self)
                return
        except ValueError:
            messagebox.showerror("Erreur", "Quantité invalide.", parent=self)
            return

        with get_db().cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO COMPOSITION (id_produit, id_ingredient, quantite_requise)
                       VALUES (?, ?, ?)""",
                    (self.product_id, ing_id, qty)
                )
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'ajouter la composition. Peut-être existe-t-elle déjà ? ({e})", parent=self)
        self._load_composition()

    def _update_composition(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Erreur", "Veuillez sélectionner une ligne à modifier.", parent=self)
            return
        comp_id = int(sel[0])
        ing_id = self._get_selected_ingredient_id()
        if not ing_id:
            messagebox.showwarning("Erreur", "Veuillez sélectionner un ingrédient.", parent=self)
            return
        try:
            qty = float(self.qty_var.get())
            if qty <= 0:
                messagebox.showerror("Erreur", "La quantité requise doit être un nombre positif.", parent=self)
                return
        except ValueError:
            messagebox.showerror("Erreur", "Quantité invalide.", parent=self)
            return

        with get_db().cursor() as cur:
            cur.execute(
                """UPDATE COMPOSITION SET id_ingredient=?, quantite_requise=?
                   WHERE id_composition=?""",
                (ing_id, qty, comp_id)
            )
        self._load_composition()

    def _delete_composition(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Erreur", "Veuillez sélectionner une ligne à supprimer.", parent=self)
            return
        comp_id = int(sel[0])
        if messagebox.askyesno("Confirmer", "Supprimer cette composition ?", parent=self):
            with get_db().cursor() as cur:
                cur.execute("DELETE FROM COMPOSITION WHERE id_composition=?", (comp_id,))
            self._load_composition()
