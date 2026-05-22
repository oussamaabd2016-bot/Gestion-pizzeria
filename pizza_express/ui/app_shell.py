"""PizzaExpress app shell — welcome → login → dashboard flow."""

import tkinter as tk

from pizza_express.database.db import get_setting
from pizza_express.logic.auth import touch_session
from pizza_express.ui.login import LoginFrame
from pizza_express.ui.main_window import MainShellFrame
from pizza_express.ui.theme import apply_theme, get_colors
from pizza_express.ui.welcome import WelcomeFrame


class PizzaExpressApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PizzaExpress")
        self.geometry("1280x780")
        self.minsize(960, 620)

        mode = get_setting("theme", "light")
        apply_theme(self, mode)

        self._current_frame: tk.Frame | None = None
        self._show_welcome()

    # ── Frame switcher ───────────────────────────────────────────────────────
    def _swap(self, frame: tk.Frame) -> None:
        if self._current_frame:
            self._current_frame.destroy()
        self._current_frame = frame
        frame.pack(fill="both", expand=True)

    # ── Stages ───────────────────────────────────────────────────────────────
    def _show_welcome(self) -> None:
        apply_theme(self)
        self._swap(WelcomeFrame(self, on_login=self._show_login))

    def _show_login(self) -> None:
        apply_theme(self)
        self._swap(LoginFrame(self, on_success=self._on_login_success,
                              on_back=self._show_welcome))

    def _on_login_success(self, user: dict) -> None:
        touch_session(user["id_utilisateur"])
        apply_theme(self)
        shell = MainShellFrame(
            self, user,
            on_logout=self._show_welcome,
            on_theme_change=self._on_theme_change,
        )
        self._swap(shell)

    def _on_theme_change(self) -> None:
        mode = get_setting("theme", "light")
        apply_theme(self, mode)
        # Rebuild current shell — easiest approach is to re-login
        # (user sees a toast in settings before this fires)
