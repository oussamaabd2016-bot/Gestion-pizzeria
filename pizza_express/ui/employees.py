"""Employees: list all, grey inactive, activate/deactivate toggle, delete."""

import tkinter as tk
from tkinter import messagebox, ttk

from pizza_express.config import POSTE_EMPLOYE
from pizza_express.database.db import get_db
from pizza_express.database.models import Employe
from pizza_express.logic.validators import normalize_phone, validate_phone
from pizza_express.ui.theme import get_colors, make_card, section_title, styled_button
from pizza_express.ui.widgets import ScrollableTreePanel
from pizza_express.ui.widgets import PhoneEntry


class EmployeesFrame(tk.Frame):
    def __init__(self, parent) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self.root = parent.winfo_toplevel()
        section_title(self, "Employes").pack(anchor="w", padx=20, pady=(12, 8))

        bar = tk.Frame(self, bg=c["bg"])
        bar.pack(fill="x", padx=20, pady=4)
        styled_button(bar, "+ Ajouter", self._add).pack(side="left", padx=4)
        styled_button(bar, "Modifier", self._edit, primary=False).pack(side="left", padx=4)
        self.toggle_btn = styled_button(bar, "Desactiver", self._toggle_active, primary=False)
        self.toggle_btn.pack(side="left", padx=4)
        styled_button(bar, "Supprimer", self._delete, primary=False).pack(side="left", padx=4)

        list_card = make_card(self)
        list_card.pack(fill="both", expand=True, padx=20, pady=8)
        self.tree_panel = ScrollableTreePanel(
            list_card,
            columns=("nom", "prenom", "poste", "email", "tel", "statut"),
            headings={
                "nom": "Nom", "prenom": "Prenom", "poste": "Poste",
                "email": "Email", "tel": "Tel", "statut": "Statut",
            },
            page_size=20,
            height=16,
            on_select=self._on_select,
        )
        self.tree_panel.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree_panel.tree.tag_configure("inactive", background="#E8E8E8", foreground="#888888")
        self.refresh()

    def refresh(self) -> None:
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM EMPLOYE ORDER BY actif DESC, nom ASC, prenom ASC")
            rows = cur.fetchall()
        tree_rows = []
        for r in rows:
            statut = "Actif" if r["actif"] else "Inactif"
            tags = () if r["actif"] else ("inactive",)
            tree_rows.append((
                str(r["id_employe"]),
                (r["nom"], r["prenom"], r["poste"], r["email"] or "", r["telephone"] or "", statut),
                tags,
            ))
        self.tree_panel.set_rows(tree_rows)

    def _selected_id(self) -> int | None:
        iid = self.tree_panel.selection_iid()
        return int(iid) if iid else None

    def _on_select(self, _evt=None) -> None:
        eid = self._selected_id()
        if not eid:
            return
        with get_db().cursor() as cur:
            cur.execute("SELECT actif FROM EMPLOYE WHERE id_employe=?", (eid,))
            row = cur.fetchone()
        if row and row["actif"]:
            self.toggle_btn.config(text="Desactiver")
        else:
            self.toggle_btn.config(text="Activer")

    def _add(self) -> None:
        EmployeeForm(self.root, on_save=self.refresh)

    def _edit(self) -> None:
        eid = self._selected_id()
        if not eid:
            messagebox.showinfo("Employes", "Selectionnez un employe.", parent=self.root)
            return
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM EMPLOYE WHERE id_employe=?", (eid,))
            row = cur.fetchone()
        if row:
            emp = Employe(
                id_employe=row["id_employe"], nom=row["nom"], prenom=row["prenom"],
                email=row["email"] or "", telephone=row["telephone"] or "",
                poste=row["poste"], actif=row["actif"],
            )
            EmployeeForm(self.root, employe=emp, on_save=self.refresh)

    def _toggle_active(self) -> None:
        eid = self._selected_id()
        if not eid:
            messagebox.showinfo("Employes", "Selectionnez un employe.", parent=self.root)
            return
        with get_db().cursor() as cur:
            cur.execute("SELECT actif, nom, prenom FROM EMPLOYE WHERE id_employe=?", (eid,))
            row = cur.fetchone()
            if not row:
                return
            if row["actif"]:
                if messagebox.askyesno("Confirmer", f"Desactiver {row['nom']} {row['prenom']} ?", parent=self.root):
                    cur.execute("UPDATE EMPLOYE SET actif=0 WHERE id_employe=?", (eid,))
            else:
                cur.execute("UPDATE EMPLOYE SET actif=1 WHERE id_employe=?", (eid,))
        self.refresh()

    def _delete(self) -> None:
        eid = self._selected_id()
        if not eid:
            messagebox.showinfo("Employes", "Selectionnez un employe.", parent=self.root)
            return
        with get_db().cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM COMMANDE WHERE id_employe=?", (eid,))
            nb = cur.fetchone()[0]
        if nb > 0:
            messagebox.showerror(
                "Suppression impossible",
                f"Cet employe a {nb} commande(s) liee(s). Desactivez-le plutot.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Supprimer definitivement",
            "Supprimer cet employe de la base ? Action irreversible.",
            parent=self.root,
        ):
            return
        with get_db().cursor() as cur:
            cur.execute("DELETE FROM EMPLOYE WHERE id_employe=?", (eid,))
        messagebox.showinfo("Employes", "Employe supprime.", parent=self.root)
        self.refresh()


class EmployeeForm(tk.Toplevel):
    def __init__(self, parent, employe: Employe | None = None, on_save=None) -> None:
        super().__init__(parent)
        self.transient(parent)
        self.e = employe or Employe()
        self.on_save = on_save
        self.title("Employe")
        self.geometry("400x420")
        c = get_colors()
        self.configure(bg=c["bg"])
        f = tk.Frame(self, padx=20, pady=16, bg=c["bg"])
        f.pack(fill="both", expand=True)
        self.nom = tk.StringVar(value=self.e.nom or "")
        self.prenom = tk.StringVar(value=self.e.prenom or "")
        self.email = tk.StringVar(value=self.e.email or "")
        self.tel = tk.StringVar(value=self.e.telephone or "")
        self.poste = tk.StringVar(value=self.e.poste or "CAISSIER")

        for lbl, var in [("Nom *", self.nom), ("Prenom *", self.prenom), ("Email (optionnel)", self.email)]:
            tk.Label(f, text=lbl, bg=c["bg"], fg=c["text"]).pack(anchor="w", pady=(6, 2))
            tk.Entry(f, textvariable=var, width=36).pack(fill="x", ipady=4)
        tk.Label(f, text="Telephone", bg=c["bg"]).pack(anchor="w", pady=(6, 2))
        PhoneEntry(f, textvariable=self.tel).pack(fill="x")
        tk.Label(f, text="Poste", bg=c["bg"]).pack(anchor="w", pady=(6, 2))
        ttk.Combobox(f, textvariable=self.poste, values=list(POSTE_EMPLOYE), state="readonly", width=34).pack(fill="x")

        def save():
            if not self.nom.get().strip() or not self.prenom.get().strip():
                messagebox.showerror("Erreur", "Nom et prenom obligatoires.", parent=self)
                return
            tel = normalize_phone(self.tel.get())
            if tel:
                ok, msg = validate_phone(tel, required=False)
                if not ok:
                    messagebox.showerror("Erreur", msg, parent=self)
                    return
            self.e.nom = self.nom.get().strip()
            self.e.prenom = self.prenom.get().strip()
            self.e.email = self.email.get().strip()
            self.e.telephone = tel
            self.e.poste = self.poste.get()
            try:
                self.e.save()
            except Exception as ex:
                messagebox.showerror("Erreur", str(ex), parent=self)
                return
            messagebox.showinfo("PizzaExpress", "Employe enregistre.", parent=self)
            self.destroy()
            if self.on_save:
                self.on_save()

        styled_button(f, "Enregistrer", save).pack(fill="x", pady=14)
        self.grab_set()
