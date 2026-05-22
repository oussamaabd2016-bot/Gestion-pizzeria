"""Paramètres: compte, thème, sections manager + gestion tables."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pizza_express.config import ACCOUNT_ROLES, BACKUPS_DIR
from pizza_express.database.db import get_db, get_setting, set_setting
from pizza_express.logic.auth import (
    change_email_optional,
    change_identifiant,
    change_password,
    create_staff_account,
)
from pizza_express.logic.backup import create_backup, restore_backup
from pizza_express.logic.validators import validate_email, validate_phone
from pizza_express.ui.theme import get_colors, make_card, modern_entry, section_title, styled_button
from pizza_express.ui.widgets import CollapsibleSection, PhoneEntry

# Zone types allowed for tables
_TABLE_ZONES = ["Salle", "Terrasse", "VIP", "Bar", "Autre"]


class SettingsFrame(tk.Frame):
    def __init__(self, parent, user: dict, on_theme_change=None) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self.user = user
        self.on_theme_change = on_theme_change
        self.is_manager = user.get("role") == "MANAGER"
        self.root = parent.winfo_toplevel()

        canvas = tk.Canvas(self, bg=c["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        outer = tk.Frame(canvas, bg=c["bg"])
        outer.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=outer, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=12)
        scrollbar.pack(side="right", fill="y", padx=(0, 12), pady=12)
        canvas.bind("<Configure>",
                    lambda e, item=canvas_window: canvas.itemconfigure(item, width=e.width))
        canvas.bind("<Enter>",
                    lambda _e: canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        self._settings_canvas = canvas
        section_title(outer, "Paramètres").pack(anchor="w", pady=(0, 12))

        # ── Mon compte ────────────────────────────────────────────────────────
        sec_account = CollapsibleSection(outer, "Mon compte")
        sec_account.pack(fill="x")
        sec_account.set_open(True)
        body = sec_account.get_body()

        tk.Label(body, text="Nouvel identifiant", bg=c["bg"], fg=c["text_muted"]).pack(
            anchor="w", pady=(6, 2))
        self.new_ident = tk.StringVar(value=user.get("nom", ""))
        modern_entry(body, textvariable=self.new_ident, width=36).pack(fill="x", ipady=3)
        tk.Label(body, text="Ancien mot de passe (pour changer identifiant)",
                 bg=c["bg"], fg=c["text_muted"]).pack(anchor="w", pady=(8, 2))
        self.old_pwd_id = tk.StringVar()
        modern_entry(body, textvariable=self.old_pwd_id, show="*", width=36).pack(fill="x", ipady=3)
        styled_button(body, "Changer identifiant", self._change_ident, primary=False).pack(
            anchor="w", pady=6)

        tk.Label(body, text="—" * 20, bg=c["bg"], fg=c["border"]).pack(anchor="w", pady=8)
        tk.Label(body, text="Nouveau mot de passe (4+ caractères)",
                 bg=c["bg"], fg=c["text_muted"]).pack(anchor="w", pady=(4, 2))
        self.new_pwd = tk.StringVar()
        modern_entry(body, textvariable=self.new_pwd, show="*", width=36).pack(fill="x", ipady=3)
        tk.Label(body, text="Ancien mot de passe", bg=c["bg"], fg=c["text_muted"]).pack(
            anchor="w", pady=(8, 2))
        self.old_pwd = tk.StringVar()
        modern_entry(body, textvariable=self.old_pwd, show="*", width=36).pack(fill="x", ipady=3)
        styled_button(body, "Changer mot de passe", self._change_pwd, primary=False).pack(
            anchor="w", pady=6)

        tk.Label(body, text="Email (optionnel)", bg=c["bg"], fg=c["text_muted"]).pack(
            anchor="w", pady=(12, 2))
        self.new_email = tk.StringVar(value=user.get("email", ""))
        modern_entry(body, textvariable=self.new_email, width=36).pack(fill="x", ipady=3)
        tk.Label(body, text="Ancien mot de passe (pour email)",
                 bg=c["bg"], fg=c["text_muted"]).pack(anchor="w", pady=(6, 2))
        self.old_pwd_email = tk.StringVar()
        modern_entry(body, textvariable=self.old_pwd_email, show="*", width=36).pack(
            fill="x", ipady=3)
        styled_button(body, "Enregistrer email", self._change_email, primary=False).pack(
            anchor="w", pady=8)

        # ── Apparence ─────────────────────────────────────────────────────────
        sec_theme = CollapsibleSection(outer, "Apparence")
        sec_theme.pack(fill="x")
        tb = sec_theme.get_body()
        self.theme_var = tk.StringVar(value=get_setting("theme", "light"))
        tk.Label(tb, text="Mode clair / sombre", bg=c["bg"], fg=c["text"]).pack(anchor="w", pady=4)
        ttk.Combobox(tb, textvariable=self.theme_var, values=["light", "dark"],
                     state="readonly", width=12).pack(anchor="w")
        styled_button(tb, "Appliquer le thème", self._apply_theme).pack(anchor="w", pady=8)

        if self.is_manager:
            # ── Gestion tables ─────────────────────────────────────────────────
            sec_tables = CollapsibleSection(outer, "Gestion des tables")
            sec_tables.pack(fill="x")
            tb2 = sec_tables.get_body()
            self._build_table_management(tb2)

            # ── Créer compte employé ────────────────────────────────────────────
            sec_staff = CollapsibleSection(outer, "Créer un compte employé")
            sec_staff.pack(fill="x")
            sb = sec_staff.get_body()
            self.st_nom = tk.StringVar()
            self.st_email = tk.StringVar()
            self.st_tel = tk.StringVar()
            self.st_pwd = tk.StringVar()
            self.st_role = tk.StringVar(value="CAISSIER")
            for lbl, var in [("Nom *", self.st_nom), ("Email (optionnel)", self.st_email),
                              ("Mot de passe", self.st_pwd)]:
                tk.Label(sb, text=lbl, bg=c["bg"]).pack(anchor="w", pady=(4, 2))
                modern_entry(sb, textvariable=var,
                             show="*" if "passe" in lbl else None, width=34).pack(fill="x", ipady=3)
            tk.Label(sb, text="Téléphone", bg=c["bg"]).pack(anchor="w")
            PhoneEntry(sb, textvariable=self.st_tel).pack(fill="x")
            ttk.Combobox(sb, textvariable=self.st_role, values=list(ACCOUNT_ROLES),
                         state="readonly").pack(anchor="w", pady=4)
            styled_button(sb, "Créer le compte", self._create_staff).pack(anchor="w", pady=10)

            # ── Infos pizzeria ──────────────────────────────────────────────────
            sec_pizza = CollapsibleSection(outer, "Informations pizzeria")
            sec_pizza.pack(fill="x")
            pb = sec_pizza.get_body()
            self.piz_nom = tk.StringVar(value=get_setting("nom_pizzeria", "PizzaExpress"))
            self.piz_tel = tk.StringVar(value=get_setting("pizzeria_telephone", ""))
            self.piz_email = tk.StringVar(value=get_setting("pizzeria_email", ""))
            for lbl, var in [("Nom", self.piz_nom), ("Téléphone", self.piz_tel),
                              ("Email (optionnel)", self.piz_email)]:
                tk.Label(pb, text=lbl, bg=c["bg"]).pack(anchor="w", pady=(6, 2))
                modern_entry(pb, textvariable=var, width=34).pack(fill="x", ipady=3)
            styled_button(pb, "Enregistrer", self._save_pizzeria).pack(anchor="w", pady=8)

            # ── Sauvegarde ──────────────────────────────────────────────────────
            sec_backup = CollapsibleSection(outer, "Sauvegarde & restauration")
            sec_backup.pack(fill="x")
            bb = sec_backup.get_body()
            styled_button(bb, "Créer une sauvegarde", self._backup, primary=False).pack(
                anchor="w", pady=4)
            styled_button(bb, "Restaurer...", self._restore, primary=False).pack(anchor="w", pady=4)

        self._style_text_for_theme()

    # ── Table management UI ──────────────────────────────────────────────────
    def _build_table_management(self, parent: tk.Frame) -> None:
        c = get_colors()
        tk.Label(parent, text="Tables du restaurant",
                 font=("Segoe UI", 11, "bold"), bg=c["bg"], fg=c["text"]).pack(
            anchor="w", pady=(0, 8))

        # Table list
        self.tables_tree = ttk.Treeview(
            parent,
            columns=("numero", "zone", "capacite", "statut"),
            show="headings", height=8,
        )
        for col, h, w in [("numero", "N°", 60), ("zone", "Zone", 100),
                           ("capacite", "Capacité", 80), ("statut", "Statut", 100)]:
            self.tables_tree.heading(col, text=h)
            self.tables_tree.column(col, width=w)
        self.tables_tree.pack(fill="x", pady=(0, 8))
        self._refresh_tables_tree()

        # Add/edit form
        form = make_card(parent, padx=12, pady=8)
        form.pack(fill="x", pady=(0, 8))
        tk.Label(form, text="Ajouter / Modifier une table",
                 font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="w", pady=(0, 8))

        row_f = tk.Frame(form, bg=c["card"])
        row_f.pack(fill="x")

        tk.Label(row_f, text="N° table", bg=c["card"], fg=c["text_muted"]).grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        self.t_num = tk.StringVar()
        tk.Entry(row_f, textvariable=self.t_num, width=6,
                 bg=c["card"], fg=c["text"], relief="flat",
                 highlightthickness=1, highlightbackground=c["border"]).grid(
            row=1, column=0, sticky="w", padx=(0, 8), ipady=4)

        tk.Label(row_f, text="Zone", bg=c["card"], fg=c["text_muted"]).grid(
            row=0, column=1, sticky="w", padx=(0, 8))
        self.t_zone = tk.StringVar(value="Salle")
        ttk.Combobox(row_f, textvariable=self.t_zone, values=_TABLE_ZONES,
                     state="readonly", width=12).grid(
            row=1, column=1, sticky="w", padx=(0, 8))

        tk.Label(row_f, text="Capacité", bg=c["card"], fg=c["text_muted"]).grid(
            row=0, column=2, sticky="w", padx=(0, 8))
        self.t_cap = tk.StringVar(value="4")
        tk.Entry(row_f, textvariable=self.t_cap, width=6,
                 bg=c["card"], fg=c["text"], relief="flat",
                 highlightthickness=1, highlightbackground=c["border"]).grid(
            row=1, column=2, sticky="w", padx=(0, 8), ipady=4)

        tk.Label(row_f, text="Position X", bg=c["card"], fg=c["text_muted"]).grid(
            row=0, column=3, sticky="w", padx=(0, 8))
        self.t_x = tk.StringVar(value="50")
        tk.Entry(row_f, textvariable=self.t_x, width=6,
                 bg=c["card"], fg=c["text"], relief="flat",
                 highlightthickness=1, highlightbackground=c["border"]).grid(
            row=1, column=3, sticky="w", padx=(0, 8), ipady=4)

        tk.Label(row_f, text="Position Y", bg=c["card"], fg=c["text_muted"]).grid(
            row=0, column=4, sticky="w")
        self.t_y = tk.StringVar(value="50")
        tk.Entry(row_f, textvariable=self.t_y, width=6,
                 bg=c["card"], fg=c["text"], relief="flat",
                 highlightthickness=1, highlightbackground=c["border"]).grid(
            row=1, column=4, sticky="w", ipady=4)

        btn_row = tk.Frame(form, bg=c["card"])
        btn_row.pack(fill="x", pady=(8, 0))
        styled_button(btn_row, "+ Ajouter table", self._add_table).pack(side="left", padx=(0, 8))
        styled_button(btn_row, "Supprimer sélection",
                      self._delete_table, primary=False).pack(side="left")

        self.tables_tree.bind("<<TreeviewSelect>>", self._on_table_select)

    def _refresh_tables_tree(self) -> None:
        self.tables_tree.delete(*self.tables_tree.get_children())
        with get_db().cursor() as cur:
            cur.execute(
                "SELECT id_table, numero, zone, capacite, statut FROM TABLE_RESTAURANT ORDER BY zone, numero"
            )
            for r in cur.fetchall():
                self.tables_tree.insert(
                    "", "end", iid=str(r["id_table"]),
                    values=(r["numero"], r["zone"], r["capacite"], r["statut"]),
                )

    def _on_table_select(self, _evt=None) -> None:
        sel = self.tables_tree.selection()
        if not sel:
            return
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM TABLE_RESTAURANT WHERE id_table=?", (int(sel[0]),))
            row = cur.fetchone()
        if row:
            self.t_num.set(str(row["numero"]))
            self.t_zone.set(row["zone"])
            self.t_cap.set(str(row["capacite"] or 4))
            self.t_x.set(str(row["pos_x"] or 50))
            self.t_y.set(str(row["pos_y"] or 50))

    def _add_table(self) -> None:
        try:
            num = int(self.t_num.get())
            cap = int(self.t_cap.get() or 4)
            px = int(self.t_x.get() or 50)
            py = int(self.t_y.get() or 50)
            zone = self.t_zone.get()
        except ValueError:
            messagebox.showerror("Erreur",
                                 "Numéro et capacité doivent être des nombres entiers.",
                                 parent=self.root)
            return
        sel = self.tables_tree.selection()
        with get_db().cursor() as cur:
            if sel:
                # Update
                cur.execute(
                    """UPDATE TABLE_RESTAURANT
                       SET numero=?, zone=?, capacite=?, pos_x=?, pos_y=?
                       WHERE id_table=?""",
                    (num, zone, cap, px, py, int(sel[0])),
                )
                messagebox.showinfo("Tables", "Table mise à jour.", parent=self.root)
            else:
                # Check unique
                cur.execute("SELECT 1 FROM TABLE_RESTAURANT WHERE numero=?", (num,))
                if cur.fetchone():
                    messagebox.showerror("Erreur",
                                         f"Table n°{num} existe déjà.", parent=self.root)
                    return
                cur.execute(
                    """INSERT INTO TABLE_RESTAURANT (numero, zone, capacite, statut, pos_x, pos_y)
                       VALUES (?, ?, ?, 'LIBRE', ?, ?)""",
                    (num, zone, cap, px, py),
                )
                messagebox.showinfo("Tables", f"Table n°{num} ajoutée.", parent=self.root)
        self._refresh_tables_tree()

    def _delete_table(self) -> None:
        sel = self.tables_tree.selection()
        if not sel:
            messagebox.showinfo("Tables", "Sélectionnez une table.", parent=self.root)
            return
        tid = int(sel[0])
        with get_db().cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM RESERVATION WHERE id_table=?", (tid,))
            nb = cur.fetchone()[0]
        if nb > 0:
            messagebox.showerror("Erreur",
                                 f"Table liée à {nb} réservation(s). Suppression impossible.",
                                 parent=self.root)
            return
        if messagebox.askyesno("Confirmer", "Supprimer cette table ?", parent=self.root):
            with get_db().cursor() as cur:
                cur.execute("DELETE FROM TABLE_RESTAURANT WHERE id_table=?", (tid,))
            self._refresh_tables_tree()

    # ── Theme helpers ─────────────────────────────────────────────────────────
    def _style_text_for_theme(self) -> None:
        c = get_colors()
        for widget in self.winfo_children():
            self._style_child(widget, c)

    def _on_mousewheel(self, event) -> None:
        try:
            self._settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            pass

    def _style_child(self, widget, c: dict) -> None:
        if isinstance(widget, tk.Label):
            bg = widget.cget("bg")
            if bg in (c["bg"], c["card"], "SystemButtonFace", "SystemWindow"):
                current_fg = str(widget.cget("fg"))
                if current_fg in ("black", "#000000", "SystemButtonText"):
                    widget.config(fg=c["text"])
        for child in widget.winfo_children():
            self._style_child(child, c)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _change_ident(self) -> None:
        ok, msg = change_identifiant(self.user["id_utilisateur"],
                                     self.old_pwd_id.get(), self.new_ident.get())
        if ok:
            self.user["nom"] = self.new_ident.get()
            messagebox.showinfo("Paramètres", msg, parent=self.root)
        else:
            messagebox.showerror("Erreur", msg, parent=self.root)

    def _change_pwd(self) -> None:
        ok, msg = change_password(self.user["id_utilisateur"],
                                  self.old_pwd.get(), self.new_pwd.get())
        if ok:
            messagebox.showinfo("Paramètres", msg, parent=self.root)
        else:
            messagebox.showerror("Erreur", msg, parent=self.root)

    def _change_email(self) -> None:
        email = self.new_email.get().strip()
        if email:
            ok, msg = validate_email(email, required=False)
            if not ok:
                messagebox.showerror("Erreur", msg, parent=self.root)
                return
        ok, msg = change_email_optional(self.user["id_utilisateur"],
                                        self.old_pwd_email.get(), email)
        if ok:
            if email:
                self.user["email"] = email
            messagebox.showinfo("Paramètres", msg or "OK", parent=self.root)
        else:
            messagebox.showerror("Erreur", msg, parent=self.root)

    def _apply_theme(self) -> None:
        set_setting("theme", self.theme_var.get())
        if self.on_theme_change:
            self.on_theme_change()
        else:
            messagebox.showinfo("Thème",
                                "Thème enregistré. Reconnectez-vous pour voir tous les changements.",
                                parent=self.root)

    def _create_staff(self) -> None:
        ok, msg = create_staff_account(
            self.st_nom.get(), self.st_email.get(), self.st_tel.get(),
            self.st_pwd.get(), self.st_role.get(),
        )
        if ok:
            messagebox.showinfo("Compte", msg, parent=self.root)
        else:
            messagebox.showerror("Erreur", msg, parent=self.root)

    def _save_pizzeria(self) -> None:
        tel = self.piz_tel.get().strip()
        if tel:
            ok, msg = validate_phone(tel, required=False)
            if not ok:
                messagebox.showerror("Erreur", msg, parent=self.root)
                return
        email = self.piz_email.get().strip()
        if email:
            ok, msg = validate_email(email, required=False)
            if not ok:
                messagebox.showerror("Erreur", msg, parent=self.root)
                return
        set_setting("nom_pizzeria", self.piz_nom.get())
        set_setting("pizzeria_telephone", tel)
        set_setting("pizzeria_email", email)
        messagebox.showinfo("Pizzeria", "Informations enregistrées.", parent=self.root)

    def _backup(self) -> None:
        messagebox.showinfo("Sauvegarde", f"Backup:\n{create_backup()}", parent=self.root)

    def _restore(self) -> None:
        path = filedialog.askopenfilename(initialdir=BACKUPS_DIR,
                                          filetypes=[("SQLite", "*.db")])
        if path:
            ok, msg = restore_backup(path)
            messagebox.showinfo("Restauration", msg, parent=self.root)
