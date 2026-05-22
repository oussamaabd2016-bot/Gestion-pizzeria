"""Main shell frame (sidebar + modules) inside the single app window."""

import tkinter as tk
from tkinter import messagebox

from pizza_express.config import ROLE_ACCESS, SESSION_TIMEOUT_SECONDS
from pizza_express.database.db import get_setting
from pizza_express.logic.auth import check_session_timeout, touch_session
from pizza_express.ui.customers import CustomersFrame
from pizza_express.ui.dashboard import DashboardFrame
from pizza_express.ui.employees import EmployeesFrame
from pizza_express.ui.menu_mgmt import MenuFrame
from pizza_express.ui.orders import OrdersFrame
from pizza_express.ui.reports_ui import ReportsFrame
from pizza_express.ui.settings import SettingsFrame
from pizza_express.ui.stock import StockFrame
from pizza_express.ui.tables import TablesFrame
from pizza_express.ui.theme import get_colors

MODULE_MAP = {
    "dashboard": ("Tableau de bord", DashboardFrame),
    "customers": ("Clients", CustomersFrame),
    "orders": ("Commandes", OrdersFrame),
    "menu": ("Menu", MenuFrame),
    "stock": ("Stock", StockFrame),
    "employees": ("Employés", EmployeesFrame),
    "tables": ("Tables", TablesFrame),
    "reports": ("Rapports", ReportsFrame),
    "settings": ("Paramètres", SettingsFrame),
}

# Sidebar icons (emoji shorthand)
_MODULE_ICONS = {
    "dashboard": "📊",
    "customers": "👥",
    "orders":    "🧾",
    "menu":      "🍕",
    "stock":     "📦",
    "employees": "👤",
    "tables":    "🪑",
    "reports":   "📈",
    "settings":  "⚙️",
}


class MainShellFrame(tk.Frame):
    def __init__(self, parent, user: dict, on_logout, on_theme_change,
                 initial_module: str = "dashboard") -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self.user = user
        self.on_logout = on_logout
        self.on_theme_change = on_theme_change
        self.current_module = initial_module
        self._pending_order_id: int | None = None
        self._pending_product: str | None = None
        self._open_new_order: bool = False
        self._select_tab: str | None = None
        self._current_frame = None
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        self.content = tk.Frame(self, bg=c["bg"])
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)
        self.show_module(initial_module)
        self._check_session()

    def _allowed_modules(self) -> set[str]:
        role = self.user.get("role", "CAISSIER")
        if role == "MANAGER":
            return set(MODULE_MAP.keys())
        return ROLE_ACCESS.get(role, ROLE_ACCESS["CAISSIER"])

    def _build_sidebar(self) -> None:
        c = get_colors()
        sidebar = tk.Frame(self, bg=c["sidebar"], width=220)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        # Header
        tk.Label(
            sidebar,
            text=get_setting("nom_pizzeria", "PizzaExpress"),
            font=("Segoe UI", 13, "bold"), fg=c["sidebar_text"], bg=c["sidebar"],
        ).pack(pady=(24, 2), padx=16, anchor="w")
        tk.Label(sidebar, text=self.user.get("nom", ""),
                 font=("Segoe UI", 9), fg=c["text_muted"], bg=c["sidebar"]).pack(padx=16, anchor="w")
        tk.Label(sidebar, text=self.user.get("role", ""),
                 font=("Segoe UI", 8), fg=c["primary_light"], bg=c["sidebar"]).pack(
            padx=16, pady=(0, 16), anchor="w")

        # Separator
        tk.Frame(sidebar, bg=c["border"], height=1).pack(fill="x", padx=16, pady=(0, 8))

        for key, (label, _) in MODULE_MAP.items():
            if key not in self._allowed_modules():
                continue
            icon = _MODULE_ICONS.get(key, "•")
            btn = tk.Label(
                sidebar, text=f"  {icon}  {label}",
                font=("Segoe UI", 10),
                fg=c["sidebar_text"], bg=c["sidebar"],
                anchor="w", cursor="hand2", pady=9,
            )
            btn.pack(fill="x", padx=8)
            btn.bind("<Button-1>", lambda e, k=key: self.show_module(k))
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=c["primary_dark"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=c["sidebar"]))

        logout = tk.Label(
            sidebar, text="  ↩  Déconnexion",
            font=("Segoe UI", 10),
            fg=c["danger"], bg=c["sidebar"],
            anchor="w", cursor="hand2", pady=10,
        )
        logout.pack(side="bottom", fill="x", padx=8, pady=16)
        logout.bind("<Button-1>", lambda e: self._logout())

    def show_module(self, key: str, order_id: int | None = None,
                    product_name: str | None = None, open_new_order: bool = False,
                    select_tab: str | None = None) -> None:
        if order_id is not None:
            self._pending_order_id = order_id
        if product_name is not None:
            self._pending_product = product_name
        if open_new_order:
            self._open_new_order = True
        if select_tab is not None:
            self._select_tab = select_tab

        if self._current_frame:
            self._current_frame.destroy()
        self.current_module = key
        touch_session(self.user["id_utilisateur"])
        _, cls = MODULE_MAP[key]

        if key == "settings":
            self._current_frame = cls(self.content, self.user,
                                      on_theme_change=self.on_theme_change)
        elif key == "dashboard":
            self._current_frame = cls(
                self.content, self.user,
                on_open_order=self._navigate_to_order,
                on_finish_order=lambda _oid: self.show_module("dashboard"),
                on_shortcut=self._handle_shortcut,
            )
        elif key == "orders":
            highlight = self._pending_order_id
            preset_product = self._pending_product
            ono = self._open_new_order
            stab = self._select_tab
            
            # Consume parameters
            self._pending_order_id = None
            self._pending_product = None
            self._open_new_order = False
            self._select_tab = None
            
            self._current_frame = cls(
                self.content, self.user,
                highlight_order_id=highlight,
                preset_product_name=preset_product,
                open_new_order=ono,
                select_tab=stab,
            )
            if highlight and hasattr(self._current_frame, "focus_order"):
                oid = highlight
                self.after(150, lambda o=oid, f=self._current_frame: f.focus_order(o))
        else:
            self._current_frame = cls(self.content)

        self._current_frame.grid(row=0, column=0, sticky="nsew")

    def _handle_shortcut(self, key: str) -> None:
        if key.startswith("orders_product:"):
            product_name = key.split(":", 1)[1]
            self.show_module("orders", product_name=product_name)
        elif key == "orders_new":
            self.show_module("orders", open_new_order=True)
        elif key == "historique":
            self.show_module("orders", select_tab="historique")
        else:
            self.show_module(key)

    def _navigate_to_order(self, order_id: int | None) -> None:
        if order_id:
            self.show_module("orders", order_id=order_id)
        else:
            self.show_module("orders")

    def _check_session(self) -> None:
        if check_session_timeout(self.user, SESSION_TIMEOUT_SECONDS):
            messagebox.showwarning("Session", "Session expirée (2h).",
                                   parent=self.winfo_toplevel())
            self._logout()
            return
        touch_session(self.user["id_utilisateur"])
        self.after(60_000, self._check_session)

    def _logout(self) -> None:
        self.on_logout()