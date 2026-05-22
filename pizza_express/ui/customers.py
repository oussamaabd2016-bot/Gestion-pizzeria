"""Customer management — fixed form panel + scrollable paginated list."""

import tkinter as tk
from tkinter import messagebox

from pizza_express.config import LOYALTY_DISCOUNT_THRESHOLD, LOYALTY_FREE_PIZZA_POINTS
from pizza_express.database.db import get_db
from pizza_express.database.models import Client
from pizza_express.logic.validators import normalize_phone, validate_email, validate_phone
from pizza_express.ui.theme import get_colors, make_card, modern_entry, section_title, styled_button
from pizza_express.ui.widgets import PhoneEntry, ScrollableTreePanel

FORM_WIDTH = 320


class CustomersFrame(tk.Frame):
    def __init__(self, parent) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self.selected_id: int | None = None
        self._loading = False
        self.root = parent.winfo_toplevel()

        section_title(self, "Clients").pack(anchor="w", padx=20, pady=(12, 8))

        top = tk.Frame(self, bg=c["bg"])
        top.pack(fill="x", padx=20, pady=4)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._search())
        modern_entry(top, textvariable=self.search_var, width=28).pack(side="left", ipady=4)
        tk.Label(top, text="  Rechercher (nom, tel, email)", bg=c["bg"], fg=c["text_muted"]).pack(side="left")

        body = tk.Frame(self, bg=c["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=8)

        # --- Form panel RIGHT (fixed width, always visible) ---
        form_outer = tk.Frame(body, bg=c["card"], width=FORM_WIDTH)
        form_outer.pack(side="right", fill="y", padx=(12, 0))
        form_outer.pack_propagate(False)

        tk.Label(
            form_outer, text="Fiche client", font=("Segoe UI", 14, "bold"),
            bg=c["card"], fg=c["text"],
        ).pack(anchor="w", padx=16, pady=(14, 4))

        self.mode_lbl = tk.Label(
            form_outer, text="Mode: nouveau client", bg=c["card"],
            fg=c["primary"], font=("Segoe UI", 9),
        )
        self.mode_lbl.pack(anchor="w", padx=16, pady=(0, 10))

        self.nom = tk.StringVar()
        self.email = tk.StringVar()
        self.tel = tk.StringVar()

        def field(lbl: str, widget) -> None:
            tk.Label(form_outer, text=lbl, bg=c["card"], fg=c["text_muted"], anchor="w").pack(
                anchor="w", padx=16, pady=(8, 2),
            )
            widget.pack(fill="x", padx=16)

        field("Nom *", modern_entry(form_outer, textvariable=self.nom, width=30))
        field("Email (optionnel)", modern_entry(form_outer, textvariable=self.email, width=30))
        tk.Label(form_outer, text="Telephone * (9+ chiffres)", bg=c["card"], fg=c["text_muted"], anchor="w").pack(
            anchor="w", padx=16, pady=(8, 2),
        )
        PhoneEntry(form_outer, textvariable=self.tel, bg=c["card"]).pack(fill="x", padx=16)

        self.points_lbl = tk.Label(
            form_outer, text="Points: 0", bg=c["card"], fg=c["primary"], font=("Segoe UI", 10),
        )
        self.points_lbl.pack(anchor="w", padx=16, pady=12)

        btn_frame = tk.Frame(form_outer, bg=c["card"])
        btn_frame.pack(fill="x", padx=16, pady=(4, 16))
        styled_button(btn_frame, "Creer client", self._create_client).pack(fill="x", pady=4)
        styled_button(btn_frame, "Enregistrer modifications", self._save, primary=False).pack(fill="x", pady=4)
        styled_button(btn_frame, "Nouveau / effacer", self._clear_form, primary=False).pack(fill="x", pady=4)
        styled_button(btn_frame, "Historique commandes", self._history, primary=False).pack(fill="x", pady=4)
        styled_button(btn_frame, "Desactiver", self._deactivate, primary=False).pack(fill="x", pady=4)

        # --- List LEFT with scroll + pages ---
        list_card = make_card(body)
        list_card.pack(side="left", fill="both", expand=True)
        self.tree_panel = ScrollableTreePanel(
            list_card,
            columns=("nom", "email", "tel", "points"),
            headings={"nom": "Nom", "email": "Email", "tel": "Telephone", "points": "Points",
                      "nom_width": 140, "email_width": 130, "tel_width": 100, "points_width": 60},
            page_size=20,
            height=18,
            on_select=self._on_select,
        )
        self.tree_panel.pack(fill="both", expand=True, padx=4, pady=4)

        self._clear_form()
        self._load_all()

    def _set_mode_label(self) -> None:
        if self.selected_id:
            self.mode_lbl.config(text=f"Mode: modification (#{self.selected_id})")
        else:
            self.mode_lbl.config(text="Mode: nouveau client")

    def _rows_from_db(self, rows) -> list:
        return [
            (str(r["id_client"]), (r["nom"], r["email"] or "", r["telephone"] or "", r["points_fidelite"]), ())
            for r in rows
        ]

    def _load_all(self) -> None:
        self._loading = True
        try:
            with get_db().cursor() as cur:
                cur.execute(
                    "SELECT id_client, nom, email, telephone, points_fidelite FROM CLIENT WHERE actif=1 ORDER BY nom"
                )
                rows = cur.fetchall()
            self.tree_panel.set_rows(self._rows_from_db(rows))
        finally:
            self._loading = False

    def _search(self) -> None:
        if self._loading:
            return
        term = self.search_var.get().strip()
        if not term:
            self._load_all()
            return
        clients = Client.search(term)
        self.tree_panel.set_rows([
            (str(c.id_client), (c.nom, c.email or "", c.telephone or "", c.points_fidelite), ())
            for c in clients
        ])

    def _on_select(self) -> None:
        iid = self.tree_panel.selection_iid()
        if not iid:
            return
        self.selected_id = int(iid)
        c = Client.get(self.selected_id)
        if not c:
            return
        self.nom.set(c.nom or "")
        self.email.set(c.email or "")
        self.tel.set(c.telephone or "")
        self._update_points_label(c.points_fidelite)
        self._set_mode_label()

    def _update_points_label(self, pts: int) -> None:
        hint = ""
        if pts >= LOYALTY_FREE_PIZZA_POINTS:
            hint = " — Pizza offerte"
        if pts > LOYALTY_DISCOUNT_THRESHOLD:
            hint += " — -5%"
        self.points_lbl.config(text=f"Points: {pts}{hint}")

    def _clear_form(self) -> None:
        self.selected_id = None
        self.nom.set("")
        self.email.set("")
        self.tel.set("")
        self.points_lbl.config(text="Points: 0")
        self._set_mode_label()

    def _validate_form(self) -> tuple[bool, str]:
        if not self.nom.get().strip():
            return False, "Nom obligatoire."
        ok, msg = validate_email(self.email.get(), required=False)
        if not ok:
            return False, msg
        ok, msg = validate_phone(self.tel.get(), required=True)
        if not ok:
            return False, msg
        return True, ""

    def _create_client(self) -> None:
        ok, msg = self._validate_form()
        if not ok:
            messagebox.showerror("Erreur", msg, parent=self.root)
            return
        client = Client()
        client.nom = self.nom.get().strip()
        client.email = self.email.get().strip()
        client.telephone = normalize_phone(self.tel.get())
        try:
            new_id = client.save()
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err.upper():
                messagebox.showerror("Erreur", "Email ou telephone deja utilise.", parent=self.root)
            else:
                messagebox.showerror("Erreur", f"Creation impossible: {err}", parent=self.root)
            return
        messagebox.showinfo("PizzaExpress", f"Client cree (#{new_id}).", parent=self.root)
        self.selected_id = new_id
        self._load_all()
        self.tree_panel.tree.selection_set(str(new_id))
        self._set_mode_label()

    def _save(self) -> None:
        if not self.selected_id:
            messagebox.showinfo("PizzaExpress", "Selectionnez un client ou « Creer client ».", parent=self.root)
            return
        ok, msg = self._validate_form()
        if not ok:
            messagebox.showerror("Erreur", msg, parent=self.root)
            return
        client = Client.get(self.selected_id)
        if not client:
            messagebox.showerror("Erreur", "Client introuvable.", parent=self.root)
            return
        client.nom = self.nom.get().strip()
        client.email = self.email.get().strip()
        client.telephone = normalize_phone(self.tel.get())
        try:
            client.save()
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err.upper():
                messagebox.showerror("Erreur", "Email ou telephone deja utilise.", parent=self.root)
            else:
                messagebox.showerror("Erreur", f"Enregistrement impossible: {err}", parent=self.root)
            return
        messagebox.showinfo("PizzaExpress", "Client mis a jour.", parent=self.root)
        self._load_all()

    def _history(self) -> None:
        if not self.selected_id:
            messagebox.showinfo("PizzaExpress", "Selectionnez un client.", parent=self.root)
            return
        with get_db().cursor() as cur:
            cur.execute(
                """SELECT id_commande, date_commande, statut, montant_total, frais_livraison, type_commande
                   FROM COMMANDE WHERE id_client=? ORDER BY date_commande DESC""",
                (self.selected_id,),
            )
            rows = cur.fetchall()
        if not rows:
            messagebox.showinfo("Historique", "Aucune commande.", parent=self.root)
            return
        lines = [
            f"#{r['id_commande']} {r['date_commande'][:16]} {r['type_commande']} {r['statut']} {(r['montant_total'] + r['frais_livraison']):.2f} MAD"
            for r in rows
        ]
        total = sum((r["montant_total"] + r["frais_livraison"]) for r in rows)
        shown = lines[:20]
        if len(lines) > 20:
            shown.append(f"... {len(lines) - 20} commande(s) de plus")
        shown.extend(["", f"Total: {total:.2f} MAD"])
        messagebox.showinfo("Historique commandes", "\n".join(shown), parent=self.root)

    def _deactivate(self) -> None:
        if not self.selected_id:
            messagebox.showinfo("PizzaExpress", "Selectionnez un client.", parent=self.root)
            return
        if messagebox.askyesno("Confirmer", "Desactiver ce client ?", parent=self.root):
            c = Client.get(self.selected_id)
            if c:
                c.deactivate()
                self._clear_form()
                self._load_all()
