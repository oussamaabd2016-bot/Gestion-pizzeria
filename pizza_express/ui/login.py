"""Login panel — staff/admin access only (inside main window)."""

import tkinter as tk
from tkinter import messagebox

from pizza_express.config import LOGIN_ERROR, SESSION_TIMEOUT_SECONDS
from pizza_express.database.db import get_setting
from pizza_express.logic.auth import check_session_timeout, login, register
from pizza_express.ui.theme import get_colors, modern_entry, styled_button
from pizza_express.ui.widgets import PhoneEntry


class LoginFrame(tk.Frame):
    def __init__(self, parent, on_success, on_back=None) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"])
        self.on_success = on_success
        self.on_back = on_back
        self._mode = "login"
        self._build_center()

    def _build_center(self) -> None:
        c = get_colors()
        for w in self.winfo_children():
            w.destroy()
        outer = tk.Frame(self, bg=c["bg"])
        outer.place(relx=0.5, rely=0.5, anchor="center")

        if self.on_back:
            back = tk.Label(
                self, text="← Menu public",
                bg=c["bg"], fg=c["primary"],
                font=("Segoe UI", 10, "underline"), cursor="hand2",
            )
            back.place(x=20, y=20)
            back.bind("<Button-1>", lambda e: self.on_back())

        card = tk.Frame(outer, bg=c["card"], padx=48, pady=40)
        card.pack()
        pizzeria = get_setting("nom_pizzeria", "PizzaExpress")
        tk.Label(
            card, text=pizzeria,
            font=("Segoe UI", 28, "bold"),
            fg=c["primary"], bg=c["card"],
        ).pack(pady=(0, 4))
        tk.Label(
            card, text="Espace personnel",
            font=("Segoe UI", 11),
            fg=c["text_muted"], bg=c["card"],
        ).pack(pady=(0, 24))
        self.inner = tk.Frame(card, bg=c["card"])
        self.inner.pack()
        if self._mode == "login":
            self._build_login()
        else:
            self._build_register()

    def _build_login(self) -> None:
        c = get_colors()
        tk.Label(self.inner, text="Connexion", font=("Segoe UI", 16, "bold"),
                 bg=c["card"], fg=c["text"]).pack(anchor="w")
        tk.Label(self.inner, text="Identifiant ou email",
                 bg=c["card"], fg=c["text_muted"]).pack(anchor="w", pady=(16, 4))
        
        # Identifiants admin par défaut préremplis
        self.login_user = tk.StringVar(value="admin")
        modern_entry(self.inner, textvariable=self.login_user, width=34).pack(fill="x", ipady=6)
        
        tk.Label(self.inner, text="Mot de passe",
                 bg=c["card"], fg=c["text_muted"]).pack(anchor="w", pady=(12, 4))
        
        self.login_pwd = tk.StringVar(value="admin")
        modern_entry(self.inner, textvariable=self.login_pwd, show="*", width=34).pack(fill="x", ipady=6)
        
        self.login_msg = tk.Label(self.inner, text="", bg=c["card"],
                                  fg=c["danger"], font=("Segoe UI", 9))
        self.login_msg.pack(pady=8)
        styled_button(self.inner, "Se connecter", self._do_login).pack(fill="x", pady=6)
        
        tk.Label(
            self.inner,
            text="Identifiant par défaut: admin / admin",
            bg=c["card"], fg=c["text_muted"], font=("Segoe UI", 8),
        ).pack(pady=(4, 0))
        
        link = tk.Label(
            self.inner, text="Créer un compte",
            bg=c["card"], fg=c["primary"],
            font=("Segoe UI", 10, "underline"), cursor="hand2",
        )
        link.pack(pady=12)
        link.bind("<Button-1>", lambda e: self._switch_register())

    def _build_register(self) -> None:
        c = get_colors()
        back = tk.Label(self.inner, text="← Connexion",
                        bg=c["card"], fg=c["primary"],
                        cursor="hand2", font=("Segoe UI", 10))
        back.pack(anchor="w")
        back.bind("<Button-1>", lambda e: self._switch_login())
        tk.Label(self.inner, text="Créer un compte",
                 font=("Segoe UI", 16, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="w", pady=(8, 12))
        self.reg_nom = tk.StringVar()
        self.reg_email = tk.StringVar()
        self.reg_tel = tk.StringVar()
        self.reg_pwd = tk.StringVar()
        self.reg_pwd2 = tk.StringVar()
        for lbl, var, show in [
            ("Nom complet *", self.reg_nom, None),
            ("Email (optionnel)", self.reg_email, None),
            ("Mot de passe (4+ caractères)", self.reg_pwd, "*"),
            ("Confirmer le mot de passe", self.reg_pwd2, "*"),
        ]:
            tk.Label(self.inner, text=lbl, bg=c["card"], fg=c["text_muted"]).pack(anchor="w", pady=(8, 2))
            modern_entry(self.inner, textvariable=var, show=show, width=34).pack(fill="x", ipady=5)
        tk.Label(self.inner, text="Téléphone (9+ chiffres)",
                 bg=c["card"], fg=c["text_muted"]).pack(anchor="w", pady=(8, 2))
        PhoneEntry(self.inner, textvariable=self.reg_tel).pack(fill="x")
        self.reg_msg = tk.Label(self.inner, text="", bg=c["card"],
                                fg=c["danger"], font=("Segoe UI", 9))
        self.reg_msg.pack(pady=6)
        styled_button(self.inner, "Enregistrer", self._do_register).pack(fill="x", pady=8)

    def _switch_register(self) -> None:
        self._mode = "register"
        self._build_center()

    def _switch_login(self) -> None:
        self._mode = "login"
        self._build_center()

    def _do_login(self) -> None:
        user, err = login(self.login_user.get(), self.login_pwd.get())
        if err or not user:
            self.login_msg.config(text=LOGIN_ERROR)
            return
        if check_session_timeout(user, SESSION_TIMEOUT_SECONDS):
            self.login_msg.config(text="Session expirée.")
            return
        self.on_success(user)

    def _do_register(self) -> None:
        if self.reg_pwd.get() != self.reg_pwd2.get():
            self.reg_msg.config(text="Les mots de passe ne correspondent pas.")
            return
        ok, msg = register(self.reg_nom.get(), self.reg_email.get(),
                           self.reg_tel.get(), self.reg_pwd.get())
        if ok:
            messagebox.showinfo("PizzaExpress", msg, parent=self.winfo_toplevel())
            self._switch_login()
        else:
            self.reg_msg.config(text=msg)