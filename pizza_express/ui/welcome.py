"""Welcome page — public-facing menu browser shown before login."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox

from pizza_express.database.db import get_db, get_setting
from pizza_express.ui.theme import get_colors
from pizza_express.ui.theme import styled_button

def _load_photo(path: str, size=(240, 150)):
    if not path or not os.path.isfile(path):
        return None
    try:
        from PIL import Image, ImageTk, ImageOps
        img = Image.open(path).convert("RGBA")
        # pad conserve les proportions et ajoute un fond transparent
        img = ImageOps.pad(img, size, color=(0, 0, 0, 0))
        return ImageTk.PhotoImage(img)
    except Exception:
        return None

# Couleurs adaptatives pour le stock
def _get_stock_colors():
    from pizza_express.ui.theme import get_mode
    mode = get_mode()
    if mode == "dark":
        return {
            "Disponible":  "#2ECC71",
            "Faible Stock": "#F39C12",
            "Rupture":     "#FF5252",  # Brighter red for dark mode
        }
    else:
        return {
            "Disponible":  "#2ECC71",
            "Faible Stock": "#F39C12",
            "Rupture":     "#E74C3C",
        }


def _product_stock_status(prod_row) -> str:
    try:
        with get_db().cursor() as cur:
            cur.execute(
                """SELECT MIN(i.stock_actuel / ri.quantite_requise) AS portions
                   FROM COMPOSITION ri
                   JOIN INGREDIENT i ON i.id_ingredient = ri.id_ingredient
                   WHERE ri.id_produit = ?""",
                (prod_row["id_produit"],),
            )
            row = cur.fetchone()
            portions = row[0] if row and row[0] else 999
    except Exception:
        portions = 999
    if portions <= 0:
        return "Rupture"
    if portions < 5:
        return "Faible Stock"
    return "Disponible"


class WelcomeFrame(tk.Frame):
    """Public welcome page — menu browser + login button + client cart."""

    CARD_W = 280   # Cartes agrandies
    CARD_H = 360

    def __init__(self, parent, on_login) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self._photos: list = []
        self.on_login = on_login
        self._selected_cat: str | None = None
        self._search_after: str | None = None
        self.cart_items = []

        self._build_header()

        # Division de l'écran : Menu (Gauche) / Panier (Droite)
        self.main_content = tk.Frame(self, bg=c["bg"])
        self.main_content.pack(fill="both", expand=True)

        self.left_pane = tk.Frame(self.main_content, bg=c["bg"])
        self.left_pane.pack(side="left", fill="both", expand=True)

        self.right_pane = tk.Frame(
            self.main_content, bg=c["card"], width=420,
            highlightthickness=1, highlightbackground=c["border"]
        )
        self.right_pane.pack(side="right", fill="y")
        self.right_pane.pack_propagate(False)

        self._build_filter_bar(self.left_pane)
        self._build_product_area(self.left_pane)
        self._build_cart_area(self.right_pane)

        self._load_categories()
        self._load_products()

    # ── Header ──────────────────────────────────────────────────────────────
    def _build_header(self) -> None:
        c = get_colors()
        hdr = tk.Frame(self, bg=c["sidebar"], padx=24, pady=14)
        hdr.pack(fill="x")
        hdr.columnconfigure(1, weight=1)

        # Brand & Logo adaptatif
        brand = tk.Frame(hdr, bg=c["sidebar"])
        brand.grid(row=0, column=0, sticky="w")
        
        mode = get_setting("theme", "light")
        # Light mode uses light logo, Dark mode uses dark logo
        logo_path = "logo_light.png" if mode == "light" else "logo_dark.png"
        logo_photo = _load_photo(logo_path, size=(35, 35))
        
        if logo_photo:
            self._logo_img = logo_photo
            tk.Label(brand, image=self._logo_img, bg=c["sidebar"], bd=0).pack(side="left", padx=(0, 6))
        else:
            # Fallback emoji with proper color for dark/light mode
            emoji_color = c["sidebar_text"] if mode == "dark" else c["sidebar_text"]
            tk.Label(brand, text="🍕", font=("Segoe UI Emoji", 22), bg=c["sidebar"], fg=emoji_color).pack(side="left", padx=(0, 6))

        name = get_setting("nom_pizzeria", "PizzaExpress")
        tk.Label(
            brand, text=name,
            font=("Segoe UI", 16, "bold"), fg=c["sidebar_text"], bg=c["sidebar"],
        ).pack(side="left")

        # Search
        search_frame = tk.Frame(hdr, bg=c["sidebar"])
        search_frame.grid(row=0, column=1, padx=40, sticky="ew")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        search_entry = tk.Entry(
            search_frame, textvariable=self._search_var,
            font=("Segoe UI", 11), relief="flat",
            bg=c["bg_alt"], fg=c["text"],
            insertbackground=c["sidebar_text"],
            highlightthickness=1, highlightbackground="#6B5E58",
        )
        search_entry.pack(fill="x", ipady=7, padx=4)
        search_entry.insert(0, "🔍  Rechercher un produit...")
        search_entry.bind("<FocusIn>", lambda e: self._clear_placeholder(search_entry))
        search_entry.bind("<FocusOut>", lambda e: self._restore_placeholder(search_entry))

        # Login button
        login_btn = styled_button(hdr, "Accès Staff →", self.on_login)
        login_btn.grid(row=0, column=2, sticky="e")

    def _clear_placeholder(self, entry: tk.Entry) -> None:
        if entry.get().startswith("🔍"):
            entry.delete(0, "end")

    def _restore_placeholder(self, entry: tk.Entry) -> None:
        if not entry.get().strip():
            entry.insert(0, "🔍  Rechercher un produit...")
            self._search_var.set("")

    def _on_search_change(self, *_) -> None:
        if self._search_after:
            self.after_cancel(self._search_after)
        self._search_after = self.after(300, self._load_products)

    # ── Filter bar ──────────────────────────────────────────────────────────
    def _build_filter_bar(self, parent: tk.Frame) -> None:
        c = get_colors()
        bar_wrap = tk.Frame(parent, bg=c["bg_alt"])
        bar_wrap.pack(fill="x")
        bar_inner = tk.Frame(bar_wrap, bg=c["bg_alt"])
        bar_inner.pack(padx=20, pady=8, anchor="w")

        tk.Label(
            bar_inner, text="Catégories :",
            font=("Segoe UI", 10, "bold"), bg=c["bg_alt"], fg=c["text_muted"],
        ).pack(side="left", padx=(0, 8))

        self._cat_buttons: dict[str | None, tk.Button] = {}
        self._cat_frame = bar_inner

    def _load_categories(self) -> None:
        for btn in self._cat_buttons.values():
            btn.destroy()
        self._cat_buttons.clear()

        with get_db().cursor() as cur:
            cur.execute("""
                SELECT id_categorie, nom FROM CATEGORIE 
                ORDER BY 
                    CASE nom
                        WHEN 'Pizza' THEN 1
                        WHEN 'Desserts' THEN 2
                        WHEN 'Boissons' THEN 3
                        ELSE 4
                    END, nom
            """)
            cats = cur.fetchall()

        self._add_cat_button("Tous", None)
        for cat in cats:
            self._add_cat_button(cat["nom"], cat["nom"])

    def _add_cat_button(self, label: str, key: str | None) -> None:
        c = get_colors()
        active = (key == self._selected_cat)
        bg = c["primary"] if active else c["card"]
        fg = "white" if active else c["text"]
        btn = tk.Button(
            self._cat_frame, text=label,
            font=("Segoe UI", 9, "bold" if active else "normal"),
            bg=bg, fg=fg, relief="flat", padx=12, pady=5,
            cursor="hand2", bd=0,
            activebackground=c["primary_dark"], activeforeground="white",
            command=lambda k=key: self._filter_category(k),
        )
        btn.pack(side="left", padx=4)
        self._cat_buttons[key] = btn

    def _filter_category(self, key: str | None) -> None:
        self._selected_cat = key
        c = get_colors()
        for k, btn in self._cat_buttons.items():
            active = (k == key)
            btn.config(
                bg=c["primary"] if active else c["card"],
                fg="white" if active else c["text"],
                font=("Segoe UI", 9, "bold" if active else "normal"),
            )
        self._load_products()

    # ── Product grid area ────────────────────────────────────────────────────
    def _build_product_area(self, parent: tk.Frame) -> None:
        c = get_colors()
        self._area = tk.Frame(parent, bg=c["bg"])
        self._area.pack(fill="both", expand=True, padx=0, pady=0)

        canvas = tk.Canvas(self._area, bg=c["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(self._area, orient="vertical", command=canvas.yview)
        self._grid_inner = tk.Frame(canvas, bg=c["bg"])
        self._grid_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._canvas_win = canvas.create_window((0, 0), window=self._grid_inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self._canvas_win, width=e.width))
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def _load_products(self) -> None:
        c = get_colors()
        for w in self._grid_inner.winfo_children():
            w.destroy()
        self._photos.clear()

        term = self._search_var.get().strip()
        if term.startswith("🔍"):
            term = ""

        with get_db().cursor() as cur:
            if self._selected_cat:
                cur.execute(
                    """SELECT p.*, cat.nom AS cat_nom FROM PRODUIT p
                       LEFT JOIN CATEGORIE cat ON cat.id_categorie = p.id_categorie
                       WHERE p.deleted=0 AND p.disponible=1 AND cat.nom=?
                       ORDER BY p.nom""", (self._selected_cat,)
                )
            elif term:
                cur.execute(
                    """SELECT p.*, cat.nom AS cat_nom FROM PRODUIT p
                       LEFT JOIN CATEGORIE cat ON cat.id_categorie = p.id_categorie
                       WHERE p.deleted=0 AND p.disponible=1 AND p.nom LIKE ?
                       ORDER BY p.nom""", (f"%{term}%",)
                )
            else:
                cur.execute(
                    """SELECT p.*, cat.nom AS cat_nom FROM PRODUIT p
                       LEFT JOIN CATEGORIE cat ON cat.id_categorie = p.id_categorie
                       WHERE p.deleted=0 AND p.disponible=1
                       ORDER BY 
                            CASE cat.nom
                                WHEN 'Pizza' THEN 1
                                WHEN 'Desserts' THEN 2
                                WHEN 'Boissons' THEN 3
                                ELSE 4
                            END, p.nom"""
                )
            products = cur.fetchall()

        if not products:
            tk.Label(
                self._grid_inner, text="Aucun produit disponible.",
                bg=c["bg"], fg=c["text_muted"], font=("Segoe UI", 13),
            ).pack(pady=40)
            return

        cats_order: list[str] = []
        by_cat: dict[str, list] = {}
        for row in products:
            cn = row["cat_nom"] or "Autres"
            if cn not in by_cat:
                by_cat[cn] = []
                cats_order.append(cn)
            by_cat[cn].append(row)

        for cat_name in cats_order:
            hdr = tk.Frame(self._grid_inner, bg=c["bg"])
            hdr.pack(fill="x", padx=20, pady=(16, 4))
            tk.Label(
                hdr, text=cat_name,
                font=("Segoe UI", 16, "bold"), bg=c["bg"], fg=c["text"],
            ).pack(side="left")
            sep = tk.Frame(hdr, bg=c["border"], height=1)
            sep.pack(side="left", fill="x", expand=True, padx=(12, 0), pady=6)

            # Remplacement par une grille CSS-like pour forcer le wrapping
            flow_frame = tk.Frame(self._grid_inner, bg=c["bg"])
            flow_frame.pack(fill="x", padx=16, pady=(0, 8))
            self._wrap_cards(flow_frame, by_cat[cat_name])

    def _wrap_cards(self, parent: tk.Frame, items: list) -> None:
        """Helper to create a flexible grid layout for cards."""
        col_count = 0
        row_frame = tk.Frame(parent, bg=get_colors()["bg"])
        row_frame.pack(fill="x", anchor="w")
        
        for row in items:
            self._make_product_card(row_frame, row)
            col_count += 1
            if col_count > 3: # 4 cartes max par ligne
                col_count = 0
                row_frame = tk.Frame(parent, bg=get_colors()["bg"])
                row_frame.pack(fill="x", anchor="w", pady=(8,0))

    def _make_product_card(self, parent: tk.Frame, row) -> None:
        c = get_colors()
        W, H = self.CARD_W, self.CARD_H
        card = tk.Frame(
            parent, bg=c["card"], width=W, height=H,
            highlightthickness=1, highlightbackground=c["border"],
        )
        card.pack(side="left", padx=8, pady=4)
        card.pack_propagate(False)

        img_frame = tk.Frame(card, bg=c["bg_alt"], width=W, height=180)
        img_frame.pack(fill="x")
        img_frame.pack_propagate(False)
        photo = _load_photo(row["image_path"] or "", size=(W, 180))
        if photo:
            self._photos.append(photo)
            tk.Label(img_frame, image=photo, bg=c["bg_alt"]).pack(fill="both", expand=True)
        else:
            emoji = "🍕" if "pizza" in (row["cat_nom"] or "").lower() else "🍽️"
            tk.Label(img_frame, text=emoji, font=("Segoe UI Emoji", 40), bg=c["bg_alt"]).pack(expand=True)

        info = tk.Frame(card, bg=c["card"], padx=12, pady=8)
        info.pack(fill="both", expand=True)

        tk.Label(
            info, text=row["nom"],
            font=("Segoe UI", 11, "bold"), bg=c["card"], fg=c["text"],
            anchor="w", wraplength=W - 24,
        ).pack(anchor="w")

        # Stock status indicator
        stock_status = _product_stock_status(row)
        stock_colors = _get_stock_colors()
        stock_color = stock_colors.get(stock_status, "#2ECC71")
        tk.Label(
            info, text=stock_status,
            font=("Segoe UI", 8, "bold"), bg=c["card"], fg=stock_color,
            anchor="w"
        ).pack(anchor="w", pady=(2, 4))

        # Removed "À partir de" text

        # Size Buttons with prices
        action_row = tk.Frame(info, bg=c["card"])
        action_row.pack(fill="x", side="bottom", pady=6)
        
        for t_label, t_val, px in [("S", "Small", row['prix_small']), ("M", "Medium", row['prix_medium']), ("L", "Large", row['prix_large'])]:
            size_frame = tk.Frame(action_row, bg=c["card"])
            size_frame.pack(side="left", padx=2, expand=True, fill="both")
            
            btn = tk.Button(
                size_frame, text=t_label, 
                font=("Segoe UI", 9, "bold"), bg=c["bg_alt"], fg=c["text"], 
                relief="flat", cursor="hand2", pady=6,
                command=lambda r=row, sz=t_val: self._add_to_cart(r, sz)
            )
            btn.pack(fill="both", expand=True)
            
            price_label = tk.Label(
                size_frame, text=f"{px:.0f} MAD",
                font=("Segoe UI", 9, "bold"), bg=c["bg_alt"], fg=c["primary"]
            )
            price_label.pack(fill="x")
            
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=c["primary"], fg="white"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=c["bg_alt"], fg=c["text"]))

        # Hover effect with shadow
        def _enter(e, fr=card): 
            fr.config(highlightbackground=c["primary"], highlightthickness=2)
        def _leave(e, fr=card): 
            fr.config(highlightbackground=c["border"], highlightthickness=1)
        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)

    # ── Cart Area ────────────────────────────────────────────────────────────
    def _build_cart_area(self, parent: tk.Frame) -> None:
        c = get_colors()
        tk.Label(parent, text="🛍️ Mon Panier", font=("Segoe UI", 16, "bold"), 
                 bg=c["card"], fg=c["text"]).pack(pady=(20, 12))

        # Zone de défilement pour les articles du panier
        self.cart_canvas = tk.Canvas(parent, bg=c["card"], highlightthickness=0)
        cart_vsb = ttk.Scrollbar(parent, orient="vertical", command=self.cart_canvas.yview)
        self.cart_inner = tk.Frame(self.cart_canvas, bg=c["card"])
        self.cart_inner.bind("<Configure>", lambda e: self.cart_canvas.configure(scrollregion=self.cart_canvas.bbox("all")))
        self.cart_canvas.create_window((0, 0), window=self.cart_inner, anchor="nw")
        self.cart_canvas.configure(yscrollcommand=cart_vsb.set)
        
        self.cart_canvas.pack(side="top", fill="both", expand=True, padx=(12, 0))
        cart_vsb.pack(side="right", fill="y", padx=(0, 4))

        self.cart_footer = tk.Frame(parent, bg=c["card"])
        self.cart_footer.pack(fill="x", side="bottom", pady=16, padx=16)

        # Client name field
        tk.Label(self.cart_footer, text="Nom du client:", font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="w", pady=(0, 4))
        self.client_name_var = tk.StringVar()
        client_entry = tk.Entry(self.cart_footer, textvariable=self.client_name_var, font=("Segoe UI", 10),
                                bg=c["bg_alt"], fg=c["text"], insertbackground=c["primary"],
                                relief="flat", highlightthickness=1, highlightbackground=c["primary"])
        client_entry.pack(fill="x", pady=(0, 12), ipady=6)

        # Order Type field
        tk.Label(self.cart_footer, text="Type de commande:", font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="w", pady=(8, 4))
        self.order_type_var = tk.StringVar(value="Sur place")
        type_combo = ttk.Combobox(self.cart_footer, textvariable=self.order_type_var, font=("Segoe UI", 10),
                                  values=["Sur place", "Livrée", "À emporter"], state="readonly")
        type_combo.pack(fill="x", pady=(0, 12), ipady=6)
        # Style the combobox
        style = ttk.Style()
        style.configure("TCombobox", fieldbackground=c["bg_alt"], background=c["primary"], 
                       foreground=c["text"], borderwidth=1)

        self.cart_total_lbl = tk.Label(self.cart_footer, text="Total: 0.00 MAD",
                                       font=("Segoe UI", 16, "bold"), bg=c["card"], fg=c["primary"])
        self.cart_total_lbl.pack(anchor="w", pady=(8, 12))
        
        styled_button(self.cart_footer, "✓ Confirmer Commande", self._confirm_order).pack(fill="x")

    def _refresh_cart(self) -> None:
        c = get_colors()
        for w in self.cart_inner.winfo_children():
            w.destroy()

        total = 0
        if not self.cart_items:
            tk.Label(self.cart_inner, text="Votre panier est vide.", bg=c["card"], fg=c["text_muted"], font=("Segoe UI", 10)).pack(pady=40)
        
        for idx, item in enumerate(self.cart_items):
            total += item["prix"] * item["qty"]
            row = tk.Frame(self.cart_inner, bg=c["bg_alt"], padx=8, pady=6, highlightthickness=1, highlightbackground=c["border"])
            row.pack(fill="x", pady=4, padx=8) # Full width stretch

            # Layout stretching to the right
            left_col = tk.Frame(row, bg=c["bg_alt"])
            left_col.pack(side="left", fill="x", expand=True)
            name_lbl = tk.Label(left_col, text=f"{item['prod']['nom']}", bg=c["bg_alt"], fg=c["text"], font=("Segoe UI", 9, "bold"))
            name_lbl.pack(side="left", padx=(4, 8))
            tk.Label(left_col, text=f"({item['taille']})", bg=c["bg_alt"], fg=c["text_muted"], font=("Segoe UI", 8)).pack(side="left")
            
            # Actions and price aligned right
            right_col = tk.Frame(row, bg=c["bg_alt"])
            right_col.pack(side="right", padx=(8, 0))
            
            price_lbl = tk.Label(right_col, text=f"{item['prix'] * item['qty']:.0f} MAD", bg=c["bg_alt"], fg=c["primary"], font=("Segoe UI", 10, "bold"), width=10, anchor="e")
            price_lbl.pack(side="right", padx=(10, 4))
            
            # Quantity controls
            qty_frame = tk.Frame(right_col, bg=c["bg_alt"])
            qty_frame.pack(pady=(4, 0))
            
            btn_minus = tk.Button(qty_frame, text="−", font=("Segoe UI", 10, "bold"),
                                 bg=c["danger"], fg="white", relief="flat", width=2, cursor="hand2",
                                 command=lambda i=idx: self._decrease_qty(i))
            btn_minus.pack(side="left", padx=2)
            
            qty_lbl = tk.Label(qty_frame, text=str(item['qty']), bg=c["bg_alt"], fg=c["text"], font=("Segoe UI", 9, "bold"), width=2)
            qty_lbl.pack(side="left", padx=2)
            
            btn_plus = tk.Button(qty_frame, text="+", font=("Segoe UI", 10, "bold"),
                                bg=c["success"], fg="white", relief="flat", width=2, cursor="hand2",
                                command=lambda i=idx: self._increase_qty(i))
            btn_plus.pack(side="left", padx=2)
            
            btn_del = tk.Button(qty_frame, text="✕", font=("Segoe UI", 9),
                               bg=c["bg"], fg=c["danger"], relief="flat", width=2, cursor="hand2",
                               command=lambda i=idx: self._remove_from_cart(i))
            btn_del.pack(side="left", padx=2)

        self.cart_total_lbl.config(text=f"Total: {total:.2f} MAD")

    def _remove_from_cart(self, idx: int) -> None:
        if 0 <= idx < len(self.cart_items):
            self.cart_items.pop(idx)
            self._refresh_cart()
    
    def _increase_qty(self, idx: int) -> None:
        if 0 <= idx < len(self.cart_items):
            self.cart_items[idx]["qty"] += 1
            self._refresh_cart()
    
    def _decrease_qty(self, idx: int) -> None:
        if 0 <= idx < len(self.cart_items):
            if self.cart_items[idx]["qty"] > 1:
                self.cart_items[idx]["qty"] -= 1
                self._refresh_cart()
            else:
                self._remove_from_cart(idx)

    def _add_to_cart(self, prod: dict, taille: str) -> None:
        prix = prod[f"prix_{taille.lower()}"]
        # Vérifier si l'article existe déjà pour augmenter la quantité
        for item in self.cart_items:
            if item["prod"]["id_produit"] == prod["id_produit"] and item["taille"] == taille:
                item["qty"] += 1
                self._refresh_cart()
                return
                
        self.cart_items.append({"prod": prod, "taille": taille, "qty": 1, "prix": prix})
        self._refresh_cart()

    def _confirm_order(self) -> None:
        if not self.cart_items:
            messagebox.showwarning("Panier vide", "Veuillez ajouter au moins un article.", parent=self.winfo_toplevel())
            return
        
        client_name = self.client_name_var.get().strip()
        if not client_name:
            messagebox.showwarning("Nom manquant", "Veuillez entrer votre nom avant de confirmer la commande.", parent=self.winfo_toplevel())
            return

        type_map = {
            "Sur place": "SUR_PLACE",
            "Livrée": "LIVRAISON",
            "À emporter": "EMPORTER"
        }
        db_type = type_map.get(self.order_type_var.get(), "SUR_PLACE")
        total = sum(item["prix"] * item["qty"] for item in self.cart_items)

        try:
            with get_db().cursor() as cur:
                cur.execute(
                    """INSERT INTO COMMANDE (type_commande, statut, montant_total, nom_client_libre)
                       VALUES (?, 'EN_ATTENTE', ?, ?)""",
                    (db_type, total, client_name)
                )
                cur.execute("SELECT last_insert_rowid()")
                cmd_id = cur.fetchone()[0]

                for item in self.cart_items:
                    cur.execute(
                        """INSERT INTO LIGNE_COMMANDE (id_commande, id_produit, taille, quantite, prix_unitaire)
                           VALUES (?, ?, ?, ?, ?)""",
                        (cmd_id, item["prod"]["id_produit"], item["taille"], item["qty"], item["prix"])
                    )
            messagebox.showinfo("Succès", f"Commande #{cmd_id} reçue, {client_name}!\nVotre commande est en préparation.", parent=self.winfo_toplevel())
            self.cart_items.clear()
            self.client_name_var.set("")
            self._refresh_cart()
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur système : {e}", parent=self.winfo_toplevel())