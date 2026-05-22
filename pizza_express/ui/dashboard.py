"""Dashboard: daily sales + live pending orders with actions, shortcuts, grouped statuses."""

import tkinter as tk
from tkinter import messagebox
import os

from pizza_express.database.db import get_db
from pizza_express.logic.reports import STATUS_COLORS, export_receipt_pdf, pending_orders, sales_summary
from pizza_express.ui.theme import get_colors, make_card, metric_value_color, section_title, styled_button


# Readable French labels for statuses
_STATUS_LABELS = {
    "EN_ATTENTE":    "En attente",
    "EN_PREPARATION":"En préparation",
    "PRETE":         "Prête",
    "LIVREE":        "Livrée",
    "ANNULEE":       "Annulée",
}

# Display order for status groups (most urgent first)
_STATUS_GROUP_ORDER = ["EN_ATTENTE", "EN_PREPARATION", "PRETE", "LIVREE", "ANNULEE"]


class DashboardFrame(tk.Frame):
    REFRESH_MS = 8000

    def __init__(self, parent, user: dict, on_open_order=None, on_finish_order=None,
                 on_shortcut=None) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self.user = user
        self.on_open_order = on_open_order
        self.on_finish_order = on_finish_order
        self.on_shortcut = on_shortcut   # callable(key) for navigation shortcuts
        self.root = parent.winfo_toplevel()

        section_title(self, "Tableau de bord").pack(anchor="w", padx=20, pady=(16, 8))

        # ── Metric cards ──────────────────────────────────────────────────────
        metrics_row = tk.Frame(self, bg=c["bg"])
        metrics_row.pack(fill="x", padx=20, pady=8)
        self.metric_labels = {}
        for i, key in enumerate(("ventes", "actives", "tables", "stock")):
            card = make_card(metrics_row)
            card.grid(row=0, column=i, padx=8, sticky="nsew")
            metrics_row.columnconfigure(i, weight=1)
            title_lbl = tk.Label(card, text="", font=("Segoe UI", 10),
                                 bg=c["card"], fg=c["text_muted"])
            title_lbl.pack(anchor="w")
            val = tk.Label(card, text="—", font=("Segoe UI", 20, "bold"),
                           bg=c["card"], fg=metric_value_color(key))
            val.pack(anchor="w")
            sub = tk.Label(card, text="", font=("Segoe UI", 9),
                           bg=c["card"], fg=c["text_muted"])
            sub.pack(anchor="w")
            self.metric_labels[key] = (title_lbl, val, sub)

        # ── Shortcut buttons ─────────────────────────────────────────────────
        self._build_shortcuts()

        # ── Bottom split: top products + pending orders ───────────────────────
        bottom = tk.Frame(self, bg=c["bg"])
        bottom.pack(fill="both", expand=True, padx=20, pady=12)
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=2)  # Right section is 2x bigger

        left = make_card(bottom)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(left, text="Top produits (jour)", font=("Segoe UI", 12, "bold"),
                 bg=c["card"], fg=c["text"]).pack(anchor="w", padx=8, pady=(8, 4))
        self.top_box = tk.Frame(left, bg=c["card"])
        self.top_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        right = make_card(bottom)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        hdr = tk.Frame(right, bg=c["card"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="Commandes en cours", font=("Segoe UI", 12, "bold"),
                 bg=c["card"], fg=c["text"]).pack(side="left")
        role = self.user.get("role", "")
        if role in ("PIZZAIOLO", "LIVREUR"):
            tk.Label(hdr, text=f"  (filtre: {role})", font=("Segoe UI", 8),
                     bg=c["card"], fg=c["text_muted"]).pack(side="left")

        scroll_wrap = tk.Frame(right, bg=c["card"])
        scroll_wrap.pack(fill="both", expand=True)
        self.orders_canvas = tk.Canvas(scroll_wrap, bg=c["card"],
                                       highlightthickness=0, height=300)
        self.orders_scroll = tk.Scrollbar(scroll_wrap, orient="vertical",
                                          command=self.orders_canvas.yview)
        self.orders_inner = tk.Frame(self.orders_canvas, bg=c["card"])
        self.orders_inner.bind("<Configure>", self._on_inner_configure)
        self._canvas_win = self.orders_canvas.create_window(
            (0, 0), window=self.orders_inner, anchor="nw")
        self.orders_canvas.configure(yscrollcommand=self.orders_scroll.set)
        self.orders_canvas.pack(side="left", fill="both", expand=True)
        self.orders_scroll.pack(side="right", fill="y")
        self.orders_canvas.bind("<Configure>", self._on_canvas_configure)

        self.refresh()
        self._schedule_refresh()

    # ── Shortcut bar ─────────────────────────────────────────────────────────
    def _build_shortcuts(self) -> None:
        c = get_colors()
        bar = tk.Frame(self, bg=c["bg"])
        bar.pack(fill="x", padx=20, pady=(0, 8))

        shortcuts = [
            ("🧾  Nouvelle Commande", "orders_new",    c["primary"]),
            ("🪑  Gestion Tables",    "tables",        "#2980B9"),
            ("📦  Vérifier Stock",    "stock",         "#27AE60"),
            ("📋  Historique",        "historique",    "#8E44AD"),
        ]
        for i, (text, key, bg) in enumerate(shortcuts):
            bar.columnconfigure(i, weight=1, uniform="shortcuts")
            btn = tk.Button(
                bar, text=text,
                font=("Segoe UI", 10, "bold"),
                bg=bg, fg="white",
                relief="flat", padx=14, pady=9,
                cursor="hand2", bd=0,
                activebackground=c["primary_dark"],
                activeforeground="white",
                command=lambda k=key: self._shortcut(k),
            )
            btn.grid(row=0, column=i, sticky="ew", padx=4)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=c["primary_dark"]))
            btn.bind("<Leave>", lambda e, b=btn, orig_bg=bg: b.config(bg=orig_bg))

    def _shortcut(self, key: str) -> None:
        if self.on_shortcut:
            self.on_shortcut(key)

    def _on_inner_configure(self, _e=None) -> None:
        self.orders_canvas.configure(scrollregion=self.orders_canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.orders_canvas.itemconfig(self._canvas_win, width=event.width)

    def _schedule_refresh(self) -> None:
        try:
            if self.winfo_exists():
                self.refresh()
                self.after(self.REFRESH_MS, self._schedule_refresh)
        except tk.TclError:
            pass

    def refresh(self) -> None:
        c = get_colors()
        sales = sales_summary("day")
        with get_db().cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM COMMANDE WHERE statut NOT IN ('LIVREE','ANNULEE')")
            active = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM TABLE_RESTAURANT WHERE statut='OCCUPEE'")
            occ = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM TABLE_RESTAURANT")
            tot = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM INGREDIENT WHERE stock_actuel < stock_min")
            alerts = cur.fetchone()[0]

        data = {
            "ventes":  ("Ventes du jour",     f"{sales['current']:.2f} MAD",
                        f"{sales['change_pct']:+.1f}% vs N-1"),
            "actives": ("Commandes actives",  str(active), ""),
            "tables":  ("Tables occupées",    f"{occ}/{tot}", ""),
            "stock":   ("Alertes stock",      str(alerts), ""),
        }
        for key, (title, val, sub) in data.items():
            t, v, s = self.metric_labels[key]
            t.config(text=title, fg=c["text_muted"])
            v.config(text=val, fg=metric_value_color(key))
            s.config(text=sub)

        # Top products
        for w in self.top_box.winfo_children():
            w.destroy()
        for i, p in enumerate(sales.get("top_products", [])[:5]):
            row = tk.Frame(self.top_box, bg=c["card"], highlightthickness=1, highlightbackground=c["border"], padx=8, pady=6)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"  {i+1}.", font=("Segoe UI", 11, "bold"),
                     bg=c["card"], fg=c["text_muted"], width=3).pack(side="left")
            prod_lbl = tk.Label(row, text=p["nom"], font=("Segoe UI", 11),
                                bg=c["card"], fg=c["text"], cursor="hand2",
                                anchor="w")
            prod_lbl.pack(side="left", fill="x", expand=True)
            prod_lbl.bind("<Button-1>", lambda e, pn=p["nom"]: self._open_product_order(pn))
            prod_lbl.bind("<Enter>", lambda e, l=prod_lbl: l.config(fg=c["primary"]))
            prod_lbl.bind("<Leave>", lambda e, l=prod_lbl: l.config(fg=c["text"]))
            tk.Label(row, text=f"{p['qty']} ventes", font=("Segoe UI", 10, "bold"),
                     bg=c["card"], fg=c["primary"]).pack(side="right", padx=4)

        # Pending orders — grouped by status
        for w in self.orders_inner.winfo_children():
            w.destroy()

        orders = pending_orders(self.user.get("role"))
        if not orders:
            tk.Label(self.orders_inner, text="  Aucune commande en attente",
                     bg=c["card"], fg=c["text_muted"]).pack(anchor="w", pady=8)
            return

        # Group by status
        by_status: dict[str, list] = {s: [] for s in _STATUS_GROUP_ORDER}
        for o in orders:
            st = o["statut"]
            if st in by_status:
                by_status[st].append(o)
            else:
                by_status.setdefault(st, []).append(o)

        first_group = True
        for status in _STATUS_GROUP_ORDER:
            group = by_status.get(status, [])
            if not group:
                continue
            # Separator between groups
            if not first_group:
                sep = tk.Frame(self.orders_inner, bg=c["border"], height=1)
                sep.pack(fill="x", padx=4, pady=4)
            first_group = False
            # Group label
            dot_color = STATUS_COLORS.get(status, c["text_muted"])
            grp_hdr = tk.Frame(self.orders_inner, bg=c["card"])
            grp_hdr.pack(fill="x", padx=4, pady=(4, 2))
            dot = tk.Canvas(grp_hdr, width=10, height=10, bg=c["card"],
                            highlightthickness=0)
            dot.create_oval(2, 2, 8, 8, fill=dot_color, outline="")
            dot.pack(side="left", padx=(4, 6))
            tk.Label(
                grp_hdr,
                text=f"{_STATUS_LABELS.get(status, status)} ({len(group)})",
                font=("Segoe UI", 9, "bold"),
                bg=c["card"], fg=dot_color,
            ).pack(side="left")
            for o in group:
                self._add_order_row(o)

    def _open_product_order(self, product_name: str) -> None:
        """Navigate to new order with the product pre-noted (best-effort)."""
        if self.on_shortcut:
            self.on_shortcut("orders_product:" + product_name)
        elif self.on_open_order:
            self.on_open_order(None)

    def _add_order_row(self, o: dict) -> None:
        c = get_colors()
        st = o["statut"]
        oid = o["id_commande"]
        type_lbl = o["type_commande"].replace("_", " ")
        client_name = o.get("client_nom") or "Sans client"
        bg = c["card"]
        row = tk.Frame(self.orders_inner, bg=bg, highlightthickness=1, highlightbackground=c["border"], padx=10, pady=8, cursor="hand2")
        row.pack(fill="x", pady=10, padx=6)

        info = tk.Frame(row, bg=bg)
        info.pack(side="left", fill="x", expand=True)
        info.bind("<Button-1>", lambda e, i=oid: self._open(i))
        tk.Label(
            info, text=f"#{oid}  {type_lbl}  •  {client_name}",
            bg=bg, fg=c["text"], font=("Segoe UI", 11, "bold"), cursor="hand2",
        ).pack(anchor="w")

        # Subtitle: amount + time
        sub_txt = f"{o['montant_total']:.0f} MAD  ·  {o['date_commande'][:16]}"
        sub_lbl = tk.Label(info, text=sub_txt, bg=bg, fg=c["text_muted"],
                           font=("Segoe UI", 9), cursor="hand2")
        sub_lbl.pack(anchor="w")
        sub_lbl.bind("<Button-1>", lambda e, i=oid: self._open(i))

        btn_frame = tk.Frame(row, bg=bg)
        btn_frame.pack(side="right", padx=6)
        styled_button(btn_frame, "✓ Terminer", lambda i=oid: self._finish(i)).pack(side="right", padx=2)
        styled_button(btn_frame, "Voir", lambda i=oid: self._open(i), primary=False).pack(side="right", padx=2)

        row.bind("<Enter>", lambda e, r=row: r.config(bg=c["bg_alt"]))
        row.bind("<Leave>", lambda e, r=row: r.config(bg=bg))

    def _open(self, order_id: int) -> None:
        if self.on_open_order:
            self.on_open_order(order_id)

    def _finish(self, order_id: int) -> None:
        try:
            with get_db().cursor() as cur:
                employe_id = self.user.get("id_employe")
                if employe_id:
                    cur.execute("SELECT 1 FROM EMPLOYE WHERE id_employe=? AND actif=1", (employe_id,))
                    if not cur.fetchone():
                        employe_id = None
                if employe_id:
                    cur.execute(
                        "UPDATE COMMANDE SET statut='LIVREE', id_employe=COALESCE(id_employe, ?) WHERE id_commande=?",
                        (employe_id, order_id),
                    )
                else:
                    cur.execute("UPDATE COMMANDE SET statut='LIVREE' WHERE id_commande=?", (order_id,))
            receipt_path = export_receipt_pdf(order_id)
            try:
                os.startfile(receipt_path)
            except Exception:
                pass
            if self.on_finish_order:
                self.on_finish_order(order_id)
                return
            if self.winfo_exists():
                self.refresh()
        except Exception as e:
            messagebox.showerror(
                "Commande",
                f"Impossible de terminer la commande #{order_id}.\n\n{e}",
                parent=self.root,
            )