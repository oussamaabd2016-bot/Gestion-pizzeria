"""Orders: list with colors, new order with free-text client + product picker."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk

from pizza_express.config import ORDER_STATUS_COLORS, TAILLES, TYPE_COMMANDE
from pizza_express.database.db import get_db
from pizza_express.database.models import Client, Commande, Produit
from pizza_express.logic.business import compute_order_totals, estimate_prep_minutes
from pizza_express.logic.reports import STATUS_COLORS, STATUS_ORDER_SQL, export_receipt_pdf, status_dot
from pizza_express.logic.validators import validate_quantity
from pizza_express.ui.theme import get_colors, make_card, modern_entry, section_title, styled_button
import re

def _load_photo(path: str, size=(110, 100)):
    if not path or not os.path.isfile(path):
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(path).resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


_STATUS_LABELS = {
    "EN_ATTENTE":    "En attente",
    "EN_PREPARATION":"En préparation",
    "PRETE":         "Prête",
    "LIVREE":        "Livrée",
    "ANNULEE":       "Annulée",
}


class OrdersFrame(tk.Frame):
    def __init__(self, parent, user: dict, highlight_order_id: int | None = None,
                 preset_product_name: str | None = None, open_new_order: bool = False,
                 select_tab: str | None = None) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self.user = user
        self._photos: list = []
        self._product_cards: dict[int, tk.Frame] = {}
        self._selected_card: tk.Frame | None = None
        self.lines: list[dict] = []
        self.selected_product: Produit | None = None
        self.current_cmd_id = None  # Contient l'ID si on modifie une commande existante
        self._highlight_id = highlight_order_id
        self._preset_product = preset_product_name

        section_title(self, "Gestion des Commandes").pack(anchor="w", padx=20, pady=(12, 4))
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=8)
        
        self.list_tab = tk.Frame(self.notebook, bg=c["bg"])
        self.new_tab = tk.Frame(self.notebook, bg=c["bg"])
        self.history_tab = tk.Frame(self.notebook, bg=c["bg"])
        
        self.notebook.add(self.list_tab, text="  Commandes Actives  ")
        self.notebook.add(self.new_tab, text="  Nouvelle Commande  ")
        self.notebook.add(self.history_tab, text="  Historique des Archives  ")
        
        self._build_list()
        self._build_new_order()
        self._build_history()
        
        if open_new_order or self._preset_product:
            self.notebook.select(self.new_tab)
        elif select_tab == "historique":
            self.notebook.select(self.history_tab)
            
        if self._highlight_id:
            self.after(200, lambda: self.focus_order(self._highlight_id))
            
        # If preset product is provided, add it to cart after products are loaded
        if self._preset_product:
            self.after(300, self._add_preset_product_to_cart)

    def _add_preset_product_to_cart(self) -> None:
        """Add the preset product to the cart when navigating from dashboard."""
        if not self._preset_product:
            return
            
        try:
            with get_db().cursor() as cur:
                cur.execute(
                    """SELECT * FROM PRODUIT WHERE nom=? AND deleted=0""",
                    (self._preset_product,)
                )
                product = cur.fetchone()
                
            if product:
                # Convert sqlite3.Row to dict
                prod_dict = dict(product)
                self._add_product_to_cart(prod_dict)
                self._preset_product = None  # Clear after adding
        except Exception as e:
            print(f"Error adding preset product to cart: {e}")

    # ── 1. Onglet Commandes Actives ───────────────────────────────────────
    def _build_list(self) -> None:
        c = get_colors()
        tree_wrap = tk.Frame(self.list_tab, bg=c["bg"])
        tree_wrap.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        
        self.otree = ttk.Treeview(
            tree_wrap,
            columns=("id", "client", "type", "statut", "total", "date"),
            show="tree headings", height=12,
        )
        self.otree.heading("#0", text="")
        self.otree.column("#0", width=40, stretch=False)

        for col, h in [("id", "# ID"), ("client", "Client / Table"), ("type", "Type de Commande"),
                       ("statut", "Statut Actuel"), ("total", "Total (MAD)"), ("date", "Date de commande")]:
            self.otree.heading(col, text=h)
        self.otree.column("id", width=70, stretch=False)
        self.otree.column("total", width=120, stretch=False)
        self.otree.column("statut", width=150, stretch=False)
        
        otree_sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.otree.yview)
        self.otree.configure(yscrollcommand=otree_sb.set)
        self.otree.pack(side="left", fill="both", expand=True)
        otree_sb.pack(side="right", fill="y")
        self.otree.bind("<<TreeviewSelect>>", self._on_order_select)

        # Actions
        action_card = make_card(self.list_tab)
        action_card.pack(fill="x", padx=8, pady=8)
        
        top_row = tk.Frame(action_card, bg=c["card"])
        top_row.pack(fill="x", pady=(0, 6))
        
        self.selected_order_lbl = tk.Label(
            top_row, text="Sélectionnez une commande active",
            bg=c["card"], fg=c["text_muted"], font=("Segoe UI", 11, "bold"),
        )
        self.selected_order_lbl.pack(side="left", anchor="w")
        
        # Bouton Modifier commande si non validée
        self.modify_btn = styled_button(top_row, "✏️ Modifier", self._load_order_for_editing, primary=False)
        self.modify_btn.state(['disabled'])
        self.modify_btn.pack(side="right", padx=4)

        self.action_var = tk.StringVar(value="Avancer statut")
        opts = tk.Frame(action_card, bg=c["card"])
        opts.pack(fill="x", pady=4)
        for choice in ("Avancer statut", "En preparation", "Prete", "Livree", "Annuler"):
            tk.Radiobutton(
                opts, text=choice, value=choice, variable=self.action_var,
                bg=c["card"], fg=c["text"], selectcolor=c["bg_alt"],
                font=("Segoe UI", 10),
            ).pack(side="left", padx=(0, 16))
            
        btns = tk.Frame(action_card, bg=c["card"])
        btns.pack(fill="x", pady=(8, 0))
        styled_button(btns, "Appliquer le statut", self._apply_action).pack(side="left")
        styled_button(btns, "Actualiser la liste", self.refresh_list, primary=False).pack(side="left", padx=8)
        self.refresh_list()

    def _get_selected_order_id(self, tree: ttk.Treeview) -> int | None:
        sel = tree.selection()
        if not sel:
            return None
        item_id = sel[0]
        parent = tree.parent(item_id)
        if parent: # Si un produit est sélectionné, on remonte à la commande
            item_id = parent
        try:
            return int(item_id)
        except (ValueError, TypeError):
            return None

    def _on_order_select(self, _evt=None) -> None:
        oid = self._get_selected_order_id(self.otree)
        if not oid:
            self.selected_order_lbl.config(text="Sélectionnez une commande active")
            self.modify_btn.state(['disabled'])
            return
        vals = self.otree.item(str(oid), "values")
        if vals:
            self.selected_order_lbl.config(text=f"Commande #{vals[0]} – {vals[1]} ({vals[3]})")
            # Activer la modification uniquement si en attente
            statut_clean = vals[3].replace("•", "").strip()
            if "attente" in statut_clean.lower() or "attente" in vals[3].lower():
                self.modify_btn.state(['!disabled'])
            else:
                self.modify_btn.state(['disabled'])

    def refresh_list(self) -> None:
        try:
            with get_db().cursor() as cur:
                cur.execute(
                    """SELECT c.id_commande, c.type_commande, c.statut, c.date_commande,
                       c.montant_total, COALESCE(cl.nom, c.nom_client_libre, 'Sans client') AS client_nom
                       FROM COMMANDE c
                       LEFT JOIN CLIENT cl ON cl.id_client = c.id_client
                       WHERE c.statut NOT IN ('LIVREE', 'ANNULEE')
                       ORDER BY datetime(c.date_commande) DESC"""
                )
                rows = cur.fetchall()
            
            self.otree.delete(*self.otree.get_children())
            for r in rows:
                oid = r["id_commande"]
                date_s = (r["date_commande"] or "")[:16]
                parent = self.otree.insert(
                    "", "end", iid=str(oid),
                    values=(
                        oid, r["client_nom"], r["type_commande"],
                        status_dot(r["statut"]), f"{r['montant_total']:.2f}", date_s,
                    )
                )
                # Chargement des produits de la commande
                with get_db().cursor() as cur2:
                    cur2.execute(
                        """SELECT lc.taille, lc.quantite, lc.prix_unitaire, p.nom 
                           FROM LIGNE_COMMANDE lc
                           JOIN PRODUIT p ON p.id_produit = lc.id_produit
                           WHERE lc.id_commande = ?""", (oid,)
                    )
                    for line in cur2.fetchall():
                        l_total = line["prix_unitaire"] * line["quantite"]
                        self.otree.insert(
                            parent, "end",
                            values=("", f" └ {line['nom']} ({line['taille']})", "", f"x{line['quantite']}", f"{l_total:.2f}", "")
                        )
        except Exception as e:
            print("Erreur refresh list actives:", e)

    # ── 2. Onglet Historique (Archives) ───────────────────────────────────
    def _build_history(self) -> None:
        c = get_colors()
        wrap = tk.Frame(self.history_tab, bg=c["bg"])
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        
        self.htree = ttk.Treeview(
            wrap,
            columns=("id", "client", "type", "statut", "total", "date"),
            show="tree headings", height=14,
        )
        self.htree.heading("#0", text="")
        self.htree.column("#0", width=40, stretch=False)

        for col, h in [("id", "# ID"), ("client", "Client / Table"), ("type", "Type"),
                       ("statut", "Statut Final"), ("total", "Montant Archivé"), ("date", "Date de Clôture")]:
            self.htree.heading(col, text=h)
        self.htree.column("id", width=70, stretch=False)
        self.htree.column("total", width=120, stretch=False)
        
        h_sb = ttk.Scrollbar(wrap, orient="vertical", command=self.htree.yview)
        self.htree.configure(yscrollcommand=h_sb.set)
        self.htree.pack(side="left", fill="both", expand=True)
        h_sb.pack(side="right", fill="y")
        
        ctrls = tk.Frame(self.history_tab, bg=c["bg"])
        ctrls.pack(fill="x", padx=8, pady=(0, 8))
        styled_button(ctrls, "Rafraîchir l'historique", self.refresh_history, primary=False).pack(side="left")
        self.refresh_history()

    def refresh_history(self) -> None:
        try:
            with get_db().cursor() as cur:
                cur.execute(
                    """SELECT c.id_commande, c.type_commande, c.statut, c.date_commande,
                       c.montant_total, COALESCE(cl.nom, c.nom_client_libre, 'Sans client') AS client_nom
                       FROM COMMANDE c
                       LEFT JOIN CLIENT cl ON cl.id_client = c.id_client
                       WHERE c.statut IN ('LIVREE', 'ANNULEE')
                       ORDER BY datetime(c.date_commande) DESC LIMIT 200"""
                )
                rows = cur.fetchall()
            
            self.htree.delete(*self.htree.get_children())
            for r in rows:
                oid = r["id_commande"]
                date_s = (r["date_commande"] or "")[:16]
                parent = self.htree.insert(
                    "", "end", iid=str(oid),
                    values=(
                        oid, r["client_nom"], r["type_commande"],
                        _STATUS_LABELS.get(r["statut"], r["statut"]), f"{r['montant_total']:.2f} MAD", date_s,
                    )
                )
                with get_db().cursor() as cur2:
                    cur2.execute(
                        """SELECT lc.taille, lc.quantite, lc.prix_unitaire, p.nom 
                           FROM LIGNE_COMMANDE lc
                           JOIN PRODUIT p ON p.id_produit = lc.id_produit
                           WHERE lc.id_commande = ?""", (oid,)
                    )
                    for line in cur2.fetchall():
                        l_total = line["prix_unitaire"] * line["quantite"]
                        self.htree.insert(
                            parent, "end",
                            values=("", f" └ {line['nom']} ({line['taille']})", "", f"x{line['quantite']}", f"{l_total:.2f}", "")
                        )
        except Exception as e:
            print("Erreur historique:", e)

    # ── 3. Onglet Nouvelle Commande / Modification (Layout Étié) ──────────
    def _build_new_order(self) -> None:
        c = get_colors()
        
        # Split horizontal principal : Grille de gauche (weight=3) et Panier étiré à droite (weight=2)
        self.new_tab.columnconfigure(0, weight=1)
        self.new_tab.columnconfigure(1, weight=1)
        self.new_tab.rowconfigure(0, weight=1)
        
        # ── CÔTÉ GAUCHE : SÉLECTION DES PRODUITS ──
        left_pane = tk.Frame(self.new_tab, bg=c["bg"])
        left_pane.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left_pane.rowconfigure(1, weight=1)
        left_pane.columnconfigure(0, weight=1)
        
        # Titre & Info Modification active
        self.edit_mode_lbl = tk.Label(
            left_pane, text="Mode : Création d'une nouvelle vente",
            font=("Segoe UI", 10, "italic"), bg=c["bg"], fg=c["primary"]
        )
        self.edit_mode_lbl.pack(anchor="w", pady=(0, 4))
        
        grid_wrap = make_card(left_pane)
        grid_wrap.pack(fill="both", expand=True)
        
        tk.Label(grid_wrap, text="Choisir un produit", font=("Segoe UI", 12, "bold"),
                 bg=c["card"], fg=c["text"]).pack(anchor="w", pady=(0, 8))
                 
        # Simple frame instead of canvas for now to debug
        self.prod_grid = tk.Frame(grid_wrap, bg=c["card"], height=500)
        self.prod_grid.pack(fill="both", expand=True, padx=4, pady=4)
        self.prod_grid.pack_propagate(False)
        
        # ── CÔTÉ DROIT : MON PANIER ÉTIRÉ ET ÉQUILIBRÉ ──
        right_pane = make_card(self.new_tab)
        right_pane.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right_pane.rowconfigure(2, weight=1)
        right_pane.columnconfigure(0, weight=1)
        
        tk.Label(right_pane, text="🛒 Mon Panier", font=("Segoe UI", 13, "bold"),
                 bg=c["card"], fg=c["primary"]).grid(row=0, column=0, sticky="ew", pady=(0, 8))
                 
        # Client & Type form
        form = tk.Frame(right_pane, bg=c["card"])
        form.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        form.columnconfigure(1, weight=1)
        
        tk.Label(form, text="Client/Table:", bg=c["card"], fg=c["text_muted"]).grid(row=0, column=0, sticky="w", pady=2)
        
        # Validation pour n'accepter que des lettres
        def validate_name(P):
            return bool(re.match(r"^[a-zA-Z\s]*$", P))
        vcmd = (self.register(validate_name), '%P')
        
        self.client_name_var = tk.StringVar()
        modern_entry(form, textvariable=self.client_name_var, width=20).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=2)

        tk.Label(form, text="Type:", bg=c["card"], fg=c["text_muted"]).grid(row=1, column=0, sticky="w", pady=4)
        self.type_cmd_var = tk.StringVar(value="SUR_PLACE")
        type_combo = ttk.Combobox(form, textvariable=self.type_cmd_var, values=TYPE_COMMANDE, state="readonly")
        type_combo.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=4)
        
        # Cart Items Table / List Wrap
        self.cart_box = tk.Frame(right_pane, bg=c["bg_alt"], bd=1, relief="flat")
        self.cart_box.grid(row=2, column=0, sticky="nsew", pady=4)
        
        # Sub-container scrollable pour les lignes de commande du panier
        self.cart_canvas = tk.Canvas(self.cart_box, bg=c["bg_alt"], highlightthickness=0)
        self.cart_vsb = ttk.Scrollbar(self.cart_box, orient="vertical", command=self.cart_canvas.yview)
        self.cart_inner = tk.Frame(self.cart_canvas, bg=c["bg_alt"])
        self.cart_inner.bind("<Configure>", lambda e: self.cart_canvas.configure(scrollregion=self.cart_canvas.bbox("all")))
        self._cart_win = self.cart_canvas.create_window((0, 0), window=self.cart_inner, anchor="nw")
        self.cart_canvas.configure(yscrollcommand=self.cart_vsb.set)
        self.cart_canvas.bind("<Configure>", lambda e: self.cart_canvas.itemconfig(self._cart_win, width=e.width))
        self.cart_canvas.pack(side="left", fill="both", expand=True)
        self.cart_vsb.pack(side="right", fill="y")
        
        # Totals Zone
        totals_frame = tk.Frame(right_pane, bg=c["card"])
        totals_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        
        self.total_lbl = tk.Label(totals_frame, text="Total: 0.00 MAD", font=("Segoe UI", 12, "bold"), bg=c["card"], fg=c["text"])
        self.total_lbl.pack(anchor="e", pady=4)
        
        action_row = tk.Frame(totals_frame, bg=c["card"])
        action_row.pack(fill="x", pady=4)
        
        self.submit_btn = styled_button(action_row, "💾 Valider & Enregistrer", self._validate_order)
        self.submit_btn.pack(side="right", padx=2)
        
        self.cancel_edit_btn = styled_button(action_row, "Annuler / Vider", self._clear_order, primary=False)
        self.cancel_edit_btn.pack(side="left", padx=2)
        
        self.refresh_products_grid()

    # ── 4. Remplissage de la Grille de Produits (Strictement Max 6/ligne) ──
    def refresh_products_grid(self) -> None:
        # Clear existing widgets
        for w in self.prod_grid.winfo_children():
            w.destroy()
        self._photos.clear()
        c = get_colors()
        
        MAX_COLS = 4  # Reduced to 4 for larger cards
        for i in range(MAX_COLS):
            self.prod_grid.columnconfigure(i, weight=1)
        
        try:
            with get_db().cursor() as cur:
                # Check if products exist
                cur.execute("SELECT COUNT(*) FROM PRODUIT WHERE deleted=0")
                product_count = cur.fetchone()[0]
                
                if product_count == 0:
                    # Create categories if needed
                    cur.execute("SELECT COUNT(*) FROM CATEGORIE")
                    cat_count = cur.fetchone()[0]
                    
                    if cat_count == 0:
                        cur.executemany(
                            "INSERT INTO CATEGORIE (nom, description) VALUES (?, ?)",
                            [
                                ("Pizzas", "Pizzas classiques et speciales"),
                                ("Boissons", "Boissons fraiches"),
                                ("Desserts", "Desserts maison"),
                            ],
                        )
                    
                    # Create demo products
                    cur.executemany(
                        """INSERT INTO PRODUIT (nom, description, prix_small, prix_medium, prix_large,
                           temps_preparation, allergenes, disponible, id_categorie)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                        [
                            ("Margherita", "Tomate, mozzarella", 45, 65, 85, 12, "Gluten, Lait", 1),
                            ("Regina", "Jambon, champignons", 55, 75, 95, 15, "Gluten, Lait", 1),
                            ("4 Fromages", "Melange de fromages", 60, 80, 100, 14, "Gluten, Lait", 1),
                            ("Coca-Cola", "33cl", 12, 15, 18, 0, "", 2),
                            ("Tiramisu", "Dessert italien", 25, 35, 45, 5, "Gluten, Oeufs, Lait", 3),
                        ],
                    )
                
                cur.execute(
                    """SELECT p.*, COALESCE(cat.nom, 'Produit') AS categorie_nom 
                       FROM PRODUIT p 
                       LEFT JOIN CATEGORIE cat ON cat.id_categorie = p.id_categorie 
                       WHERE p.deleted=0 
                       ORDER BY cat.nom, p.nom"""
                )
                products = cur.fetchall()
                
            if not products:
                tk.Label(self.prod_grid, text="Aucun produit disponible.\nVeuillez ajouter des produits via le Menu.",
                         font=("Segoe UI", 12), bg=c["card"], fg=c["text_muted"]).pack(pady=40)
                return
                
            for index, row in enumerate(products):
                p_id = row["id_produit"]
                p_name = row["nom"]
                p_price = row["prix_medium"]
                p_image = row["image_path"] if "image_path" in row.keys() else ""
                
                # Création de la carte de produit (plus grande)
                card = tk.Frame(self.prod_grid, bg=c["card"], highlightthickness=1, highlightbackground=c["border"], padx=8, pady=8)
                r = index // MAX_COLS
                col = index % MAX_COLS
                card.grid(row=r, column=col, padx=8, pady=8, sticky="nsew")
                
                # Image (larger)
                photo = _load_photo(p_image, size=(140, 120))
                if photo:
                    self._photos.append(photo)
                    img_lbl = tk.Label(card, image=photo, bg=c["card"])
                    img_lbl.pack(pady=4)
                else:
                    img_lbl = tk.Label(card, text="🍕", font=("Segoe UI", 32), bg=c["card"])
                    img_lbl.pack(pady=6)
                    
                tk.Label(card, text=p_name, font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["text"], wraplength=140, justify="center").pack()
                tk.Label(card, text=f"{p_price:.0f} MAD", font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["primary"]).pack(pady=2)
                
                # Click event to add direct to cart
                for widget in (card, img_lbl):
                    widget.bind("<Button-1>", lambda e, r_p=row: self._add_product_to_cart(r_p))
                    widget.config(cursor="hand2")
                    
        except Exception as e:
            import traceback
            print("Erreur grid produits:", e)
            traceback.print_exc()

    # ── 5. Logique d'Ajout et Rendu Dynamique du Panier Étiré ────────────
    def _add_product_to_cart(self, prod_row: dict) -> None:
        # Vérifie si le produit existe déjà dans le panier en taille Medium par défaut
        for item in self.lines:
            if item["id_produit"] == prod_row["id_produit"] and item["taille"] == "Medium":
                item["qty"] += 1
                self._render_cart_items()
                return
                
        self.lines.append({
            "id_produit": prod_row["id_produit"],
            "nom": prod_row["nom"],
            "taille": "Medium",
            "qty": 1,
            "prix_small": prod_row["prix_small"],
            "prix_medium": prod_row["prix_medium"],
            "prix_large": prod_row["prix_large"],
        })
        self._render_cart_items()

    def _render_cart_items(self) -> None:
        c = get_colors()
        for w in self.cart_inner.winfo_children():
            w.destroy()
            
        if not self.lines:
            tk.Label(self.cart_inner, text="Le panier est vide.", font=("Segoe UI", 10, "italic"),
                     bg=c["bg_alt"], fg=c["text_muted"]).pack(anchor="center", pady=40)
            self.total_lbl.config(text="Total: 0.00 MAD")
            return
            
        total_cmd = 0.0
        for index, item in enumerate(self.lines):
            # Détermination du prix selon la taille sélectionnée
            base_p = item["prix_medium"]
            if item["taille"] == "Small": base_p = item["prix_small"]
            elif item["taille"] == "Large": base_p = item["prix_large"]
            
            line_total = base_p * item["qty"]
            total_cmd += line_total
            
            # Ligne de panier étirée
            row_frame = tk.Frame(self.cart_inner, bg=c["card"], padx=10, pady=6, bd=1, relief="flat")
            row_frame.pack(fill="x", padx=6, pady=3)
            
            # Horizontal layout without excessive stretching
            info_col = tk.Frame(row_frame, bg=c["card"])
            info_col.pack(side="left", fill="x", expand=False)
            tk.Label(info_col, text=item["nom"], font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["text"], anchor="w", width=20).pack(side="left")
            
            # Sélecteur de taille (S / M / L) inline
            size_frame = tk.Frame(row_frame, bg=c["card"])
            size_frame.pack(side="left", padx=8)
            for t in ("Small", "Medium", "Large"):
                bg_b = c["primary"] if item["taille"] == t else c["bg_alt"]
                fg_b = "white" if item["taille"] == t else c["text"]
                tk.Button(
                    size_frame, text=t[0], font=("Segoe UI", 8, "bold"), bg=bg_b, fg=fg_b,
                    relief="flat", bd=0, width=2, cursor="hand2",
                    command=lambda idx=index, size_val=t: self._change_item_size(idx, size_val)
                ).pack(side="left", padx=1)
                
            # Contrôle Quantité
            qty_frame = tk.Frame(row_frame, bg=c["card"])
            qty_frame.pack(side="left", padx=15)
            
            tk.Button(qty_frame, text="-", font=("Segoe UI", 9, "bold"), bg=c["bg_alt"], fg=c["text"], width=2, relief="flat",
                      command=lambda idx=index: self._update_qty(idx, -1)).pack(side="left")
                      
            tk.Label(qty_frame, text=str(item["qty"]), font=("Segoe UI", 10, "bold"), bg=c["card"], width=3).pack(side="left")
            
            tk.Button(qty_frame, text="+", font=("Segoe UI", 9, "bold"), bg=c["bg_alt"], fg=c["text"], width=2, relief="flat",
                      command=lambda idx=index: self._update_qty(idx, 1)).pack(side="left")
                      
            # Fixed alignment for price
            tk.Label(row_frame, text=f"{line_total:.0f} MAD", font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["primary"], width=12, anchor="e").pack(side="right", padx=(10, 5))
            
        self.total_lbl.config(text=f"Total: {total_cmd:.2f} MAD")

    def _change_item_size(self, idx: int, size: str) -> None:
        self.lines[idx]["taille"] = size
        self._render_cart_items()

    def _update_qty(self, idx: int, delta: int) -> None:
        self.lines[idx]["qty"] += delta
        if self.lines[idx]["qty"] <= 0:
            self.lines.pop(idx)
        self._render_cart_items()

    # ── 6. Logique de Chargement pour Modification (Avant Validation) ─────
    def _load_order_for_editing(self) -> None:
        order_id = self._get_selected_order_id(self.otree)
        if not order_id: return
        c = get_colors()
        
        try:
            with get_db().cursor() as cur:
                # Récupération de l'en-tête
                cur.execute("SELECT * FROM COMMANDE WHERE id_commande=?", (order_id,))
                cmd = cur.fetchone()
                if not cmd: return
                
                if cmd["statut"] in ("LIVREE", "ANNULEE"):
                    messagebox.showerror("Erreur", "Cette commande est archivée et ne peut plus être modifiée.")
                    return
                    
                self.current_cmd_id = order_id
                self.client_name_var.set(cmd["nom_client_libre"] or "")
                self.type_cmd_var.set(cmd["type_commande"])
                
                # Récupération des lignes existantes
                cur.execute(
                    """SELECT lc.*, p.nom, p.prix_small, p.prix_medium, p.prix_large 
                       FROM LIGNE_COMMANDE lc 
                       JOIN PRODUIT p ON p.id_produit = lc.id_produit 
                       WHERE lc.id_commande=?""", (order_id,)
                )
                db_lines = cur.fetchall()
                
            self.lines.clear()
            for row in db_lines:
                self.lines.append({
                    "id_produit": row["id_produit"],
                    "nom": row["nom"],
                    "taille": row["taille"],
                    "qty": row["quantite"],
                    "prix_small": row["prix_small"],
                    "prix_medium": row["prix_medium"],
                    "prix_large": row["prix_large"],
                })
                
            self.edit_mode_lbl.config(text=f"⚠️ MODIFICATION ACTIVE : Commande #{order_id}", fg=c["warning"])
            self._render_cart_items()
            
            # Rediriger l'utilisateur vers l'onglet du panier
            self.notebook.select(self.new_tab)
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger la commande: {e}")

    # ── 7. Validation finale (Insertion ou Mise à Jour de Commande) ───────
    def _validate_order(self) -> None:
        if not self.lines:
            messagebox.showwarning("Panier vide", "Veuillez ajouter au moins un article au panier.")
            return
            
        c = get_colors()
        client_name = self.client_name_var.get().strip()
        type_cmd = self.type_cmd_var.get()
        
        try:
            db = get_db()
            with db.cursor() as cur:
                # Calcul du montant global
                total_computed = 0.0
                sub_lines = []
                for item in self.lines:
                    bp = item["prix_medium"]
                    if item["taille"] == "Small": bp = item["prix_small"]
                    elif item["taille"] == "Large": bp = item["prix_large"]
                    line_price = bp * item["qty"]
                    total_computed += line_price
                    sub_lines.append((item["id_produit"], item["taille"], item["qty"], bp))
                    
                if self.current_cmd_id is not None:
                    # ── MODE MISE À JOUR (UPDATE) ──
                    cur.execute(
                        """UPDATE COMMANDE 
                           SET nom_client_libre=?, type_commande=?, montant_total=? 
                           WHERE id_commande=?""",
                        (client_name, type_cmd, total_computed, self.current_cmd_id)
                    )
                    # Supprimer les anciennes lignes pour insérer les nouvelles rectifiées
                    cur.execute("DELETE FROM LIGNE_COMMANDE WHERE id_commande=?", (self.current_cmd_id,))
                    cmd_id = self.current_cmd_id
                else:
                    # ── MODE CRÉATION COMPLAIT (INSERT) ──
                    cur.execute(
                        """INSERT INTO COMMANDE (type_commande, statut, montant_total, nom_client_libre, date_commande) 
                           VALUES (?, 'EN_ATTENTE', ?, ?, datetime('now', 'localtime'))""",
                        (type_cmd, total_computed, client_name)
                    )
                    cmd_id = cur.lastrowid
                    
                # Insertion des lignes de commandes
                for p_id, size, qty, price in sub_lines:
                    cur.execute(
                        """INSERT INTO LIGNE_COMMANDE (id_commande, id_produit, taille, quantite, prix_unitaire) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (cmd_id, p_id, size, qty, price)
                    )
            
            msg = f"Commande #{cmd_id} enregistrée avec succès." if self.current_cmd_id is None else f"Commande #{cmd_id} modifiée avec succès."
            messagebox.showinfo("Succès", msg)
            
            self._clear_order()
            self.refresh_list()
            self.refresh_history()
            self.notebook.select(self.list_tab)
            
        except Exception as e:
            import traceback
            messagebox.showerror("Erreur validation", f"Une erreur est survenue: {e}")
            traceback.print_exc()

    def _clear_order(self) -> None:
        self.lines.clear()
        self.current_cmd_id = None
        self.client_name_var.set("")
        self.type_cmd_var.set("SUR_PLACE")
        self.edit_mode_lbl.config(text="Mode : Création d'une nouvelle vente", fg=get_colors()["primary"])
        self._render_cart_items()

    def _apply_action(self) -> None:
        cid = self._get_selected_order_id(self.otree)
        if not cid:
            messagebox.showinfo("PizzaExpress", "Sélectionnez une commande active d'abord.")
            return
        action = self.action_var.get()
        mapping = {
            "En preparation": "EN_PREPARATION",
            "Prete": "PRETE",
            "Livree": "LIVREE",
            "Annuler": "ANNULEE",
        }
        try:
            with get_db().cursor() as cur:
                if action == "Avancer statut":
                    cur.execute("SELECT statut FROM COMMANDE WHERE id_commande=?", (cid,))
                    row = cur.fetchone()
                    if not row: return
                    flow = ["EN_ATTENTE", "EN_PREPARATION", "PRETE", "LIVREE"]
                    if row["statut"] in flow:
                        idx = flow.index(row["statut"])
                        new_s = flow[min(idx + 1, 3)]
                    else:
                        return
                else:
                    new_s = mapping[action]
                    
                cur.execute("UPDATE COMMANDE SET statut=? WHERE id_commande=?", (new_s, cid))
            self.refresh_list()
            self.refresh_history()
            self.selected_order_lbl.config(text="Sélectionnez une commande active")
            self.modify_btn.state(['disabled'])
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def focus_order(self, order_id: int) -> None:
        if self.otree.exists(str(order_id)):
            self.otree.selection_set(str(order_id))
            self.otree.see(str(order_id))