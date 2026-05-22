"""Tables plan and reservations."""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from pizza_express.config import MEAL_DURATION_MINUTES, RESERVATION_MIN_ADVANCE_HOURS
from pizza_express.database.db import check_reservation_overlap, get_db
from pizza_express.ui.theme import get_colors, make_card, section_title, styled_button

try:
    from tkcalendar import DateEntry
    HAS_CALENDAR = True
except ImportError:
    HAS_CALENDAR = False


class TablesFrame(tk.Frame):
    def __init__(self, parent) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self.client_labels: list[str] = []
        self.table_labels: list[str] = []
        self.client_map: dict[str, int] = {}
        self.table_map: dict[str, int] = {}
        section_title(self, "Tables & Reservations").pack(anchor="w", padx=20, pady=(12, 8))
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=c["bg"], sashwidth=4)
        paned.pack(fill="both", expand=True, padx=20, pady=8)

        left = make_card(paned)
        paned.add(left, width=480)
        tk.Label(left, text="Plan de salle", font=("Segoe UI", 12, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="w")
        self.canvas = tk.Canvas(left, bg=c["bg_alt"], height=340, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=8)

        right = make_card(paned)
        paned.add(right)
        tk.Label(right, text="Nouvelle reservation", font=("Segoe UI", 12, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="w", pady=(0, 12))

        self.client_var = tk.StringVar()
        self.table_var = tk.StringVar()
        self._load_combos()

        tk.Label(right, text="Client", bg=c["card"], fg=c["text_muted"]).pack(anchor="w")
        self.client_combo = ttk.Combobox(
            right, textvariable=self.client_var, values=self.client_labels,
            state="readonly", width=38,
        )
        self.client_combo.pack(anchor="w", pady=(0, 10))
        tk.Label(right, text="Table", bg=c["card"], fg=c["text_muted"]).pack(anchor="w")
        self.table_combo = ttk.Combobox(
            right, textvariable=self.table_var, values=self.table_labels,
            state="readonly", width=38,
        )
        self.table_combo.pack(anchor="w", pady=(0, 10))

        tk.Label(right, text="Date & heure", bg=c["card"], fg=c["text_muted"]).pack(anchor="w")
        dt_row = tk.Frame(right, bg=c["card"])
        dt_row.pack(anchor="w", pady=(0, 10))
        if HAS_CALENDAR:
            self.date_picker = DateEntry(dt_row, width=14, date_pattern="yyyy-mm-dd")
            self.date_picker.pack(side="left", padx=(0, 8))
        else:
            self.date_manual = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
            tk.Entry(dt_row, textvariable=self.date_manual, width=12).pack(side="left", padx=(0, 8))
        self.time_var = tk.StringVar(value="19:00")
        tk.Entry(dt_row, textvariable=self.time_var, width=8).pack(side="left")

        tk.Label(right, text="Nombre de personnes", bg=c["card"], fg=c["text_muted"]).pack(anchor="w")
        self.nb_var = tk.StringVar(value="2")
        tk.Entry(right, textvariable=self.nb_var, width=8).pack(anchor="w", pady=(0, 12))
        styled_button(right, "Confirmer reservation", self._save_reservation).pack(anchor="w", pady=8)

        tk.Label(right, text="Reservations", font=("Segoe UI", 11, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="w", pady=(16, 4))
        self.rtree = ttk.Treeview(right, columns=("client", "table", "date", "pers", "statut"), show="headings", height=8)
        for col, h in [("client", "Client"), ("table", "Table"), ("date", "Date"), ("pers", "Pers."), ("statut", "Statut")]:
            self.rtree.heading(col, text=h)
        self.rtree.pack(fill="both", expand=True)
        self.refresh()

    def _load_combos(self) -> None:
        self.client_map.clear()
        self.table_map.clear()
        self.client_labels = []
        self.table_labels = []
        with get_db().cursor() as cur:
            cur.execute("SELECT id_client, nom, telephone FROM CLIENT WHERE actif=1 ORDER BY nom")
            for r in cur.fetchall():
                label = f"{r['nom']} — {r['telephone'] or 'sans tel'}"
                self.client_labels.append(label)
                self.client_map[label] = r["id_client"]
            cur.execute("SELECT id_table, numero, zone FROM TABLE_RESTAURANT ORDER BY numero")
            for r in cur.fetchall():
                label = f"Table {r['numero']} ({r['zone']})"
                self.table_labels.append(label)
                self.table_map[label] = r["id_table"]
        if self.client_labels:
            self.client_var.set(self.client_labels[0])
        if self.table_labels:
            self.table_var.set(self.table_labels[0])

    def refresh(self) -> None:
        c = get_colors()
        self.canvas.delete("all")
        colors = {
            "LIBRE": c.get("status_green", "#A8E6CF"),
            "OCCUPEE": c.get("status_red", "#FF8A80"),
            "RESERVEE": c.get("status_orange", "#FFD54F")
        }
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM TABLE_RESTAURANT ORDER BY numero")
            for t in cur.fetchall():
                x, y = t["pos_x"], t["pos_y"]
                color = colors.get(t["statut"], "#DDD")
                self.canvas.create_rectangle(x, y, x + 72, y + 52, fill=color, outline=c["border"], width=1)
                self.canvas.create_text(x + 36, y + 26, text=f"T{t['numero']}\n{t['zone']}", font=("Segoe UI", 9))
            cur.execute(
                """SELECT r.*, t.numero, COALESCE(c.nom, '?') AS nom_client FROM RESERVATION r
                   JOIN TABLE_RESTAURANT t ON t.id_table = r.id_table
                   JOIN CLIENT c ON c.id_client = r.id_client
                   ORDER BY r.date_reservation DESC LIMIT 25"""
            )
            res = cur.fetchall()
        self.rtree.delete(*self.rtree.get_children())
        for r in res:
            self.rtree.insert("", "end", values=(r["nom_client"], r["numero"], r["date_reservation"][:16], r["nb_personnes"], r["statut"]))

    def _save_reservation(self) -> None:
        clabel = self.client_var.get().strip()
        tlabel = self.table_var.get().strip()
        if clabel not in self.client_map or tlabel not in self.table_map:
            messagebox.showerror(
                "Erreur",
                "Choisissez un client et une table dans les listes.",
                parent=self.winfo_toplevel(),
            )
            return
        if HAS_CALENDAR:
            date_s = self.date_picker.get_date().strftime("%Y-%m-%d")
        else:
            date_s = self.date_manual.get()
        dt_str = f"{date_s} {self.time_var.get()}"
        try:
            res_dt = datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Erreur", "Date/heure invalide.", parent=self.winfo_toplevel())
            return
        if res_dt < datetime.now() + timedelta(hours=RESERVATION_MIN_ADVANCE_HOURS):
            messagebox.showerror("Erreur", "Reservation au moins 1h a l'avance.", parent=self.winfo_toplevel())
            return
        id_client = self.client_map[clabel]
        id_table = self.table_map[tlabel]
        fin = (res_dt + timedelta(minutes=MEAL_DURATION_MINUTES)).isoformat()
        with get_db().cursor() as cur:
            if check_reservation_overlap(cur, id_table, res_dt.isoformat()):
                messagebox.showerror("Erreur", "Creneau deja reserve.", parent=self.winfo_toplevel())
                return
            cur.execute(
                """INSERT INTO RESERVATION (id_client, id_table, date_reservation, nb_personnes, statut, fin_prevue)
                   VALUES (?,?,?,?, 'CONFIRMEE', ?)""",
                (id_client, id_table, res_dt.isoformat(), int(self.nb_var.get()), fin),
            )
            cur.execute("UPDATE TABLE_RESTAURANT SET statut='RESERVEE' WHERE id_table=?", (id_table,))
        messagebox.showinfo("PizzaExpress", "Reservation confirmee.", parent=self.winfo_toplevel())
        self.refresh()
