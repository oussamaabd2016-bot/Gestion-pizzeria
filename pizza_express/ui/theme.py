"""Modern commerce-style Tkinter theme (light/dark) — softer palette."""

import tkinter as tk
from tkinter import ttk

# Softer light theme — warm off-whites, muted greys, no aggressive white
THEME_LIGHT = {
    "bg":           "#F8F9FA",   
    "bg_alt":       "#F1F3F5",   
    "card":         "#FFFFFF",   
    "sidebar":      "#1A1C1E",   # modern dark sidebar
    "sidebar_text": "#F0EDE8",
    "primary":      "#E63946",   # vibrant pizza red
    "primary_dark": "#BA2D38",
    "primary_light":"#FFBDBD",
    "accent":       "#FFD166",   # modern gold
    "text":         "#212529",
    "text_muted":   "#6C757D",
    "border":       "#DEE2E6",
    "success":      "#27AE60",
    "danger":       "#E74C3C",
    "warning":      "#F39C12",
    "status_green": "#D4EDDA",
    "status_orange":"#FFD59E",
    "status_red":   "#FFB3B3",
}

THEME_DARK = {
    "bg":           "#1A1814",
    "bg_alt":       "#232019",
    "card":         "#2C2822",
    "sidebar":      "#141210",
    "sidebar_text": "#E8E0D5",
    "primary":      "#E05544",
    "primary_dark": "#B8392A",
    "primary_light":"#7A2E26",
    "accent":       "#5A4A2A",
    "text":         "#FFFFFF",   # High visibility text
    "text_muted":   "#8A8078",
    "border":       "#3C3830",
    "success":      "#27AE60",
    "danger":       "#E74C3C",
    "warning":      "#F39C12",
    "status_green": "#2ECC71",
    "status_orange":"#E67E22",
    "status_red":   "#FF5252",   # Visible red for dark mode
}

_current_mode = "light"
_colors = THEME_LIGHT.copy()


def get_colors() -> dict:
    return _colors


def get_mode() -> str:
    return _current_mode


def set_theme_mode(mode: str) -> None:
    global _current_mode, _colors
    _current_mode = mode
    _colors = (THEME_DARK if mode == "dark" else THEME_LIGHT).copy()


def apply_theme(root: tk.Misc, mode: str | None = None) -> None:
    if mode:
        set_theme_mode(mode)
    c = get_colors()
    root.configure(bg=c["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=c["bg"], foreground=c["text"], font=("Segoe UI", 10))
    style.configure("TFrame", background=c["bg"])
    style.configure("Card.TFrame", background=c["card"])
    style.configure("TLabel", background=c["bg"], foreground=c["text"])
    style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground=c["text"])
    style.configure("Subtitle.TLabel", font=("Segoe UI", 11), foreground=c["text_muted"])
    style.configure(
        "Primary.TButton", background=c["primary"], foreground="white",
        padding=(14, 10), font=("Segoe UI", 10, "bold"),
    )
    style.map("Primary.TButton", 
              background=[("active", c["primary_dark"]), ("disabled", c["border"])],
              foreground=[("disabled", c["text_muted"])])
              
    style.configure("Ghost.TButton", background=c["bg_alt"], foreground=c["text"], padding=(12, 8))
    style.map("Ghost.TButton", 
              background=[("active", c["border"]), ("disabled", c["bg_alt"])],
              foreground=[("disabled", c["text_muted"])])
              

    style.configure(
        "Treeview",
        background=c["card"], fieldbackground=c["card"],
        foreground=c["text"], bordercolor=c["border"], rowheight=30,
        lightcolor=c["border"], darkcolor=c["border"],
    )
    style.configure(
        "Treeview.Heading",
        background=c["bg_alt"], foreground=c["text"],
        bordercolor=c["border"], relief="flat",
    )
    style.map("Treeview", background=[("selected", c["primary"])], foreground=[("selected", "white")])

    style.configure("TNotebook", background=c["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=c["bg_alt"], foreground=c["text"], padding=[14, 8])
    style.map("TNotebook.Tab", background=[("selected", c["card"])], foreground=[("selected", c["text"])])

    style.configure(
        "TCombobox",
        fieldbackground=c["card"], background=c["card"],
        foreground=c["text"], arrowcolor=c["text"],
    )
    style.configure("TEntry", fieldbackground=c["card"], foreground=c["text"])
    style.map(
        "TEntry",
        fieldbackground=[("readonly", c["bg_alt"]), ("disabled", c["bg_alt"])],
        foreground=[("readonly", c["text"]), ("disabled", c["text_muted"])],
    )
    style.configure("Vertical.TScrollbar", background=c["bg_alt"], troughcolor=c["bg"], arrowcolor=c["text"])
    style.configure("Horizontal.TScrollbar", background=c["bg_alt"], troughcolor=c["bg"], arrowcolor=c["text"])


def make_card(parent: tk.Widget, padx=16, pady=12) -> tk.Frame:
    c = get_colors()
    return tk.Frame(parent, bg=c["card"], padx=padx, pady=pady)
    # Note: For true rounded corners in TK, one would typically use a Canvas or custom images.
    # We maintain cleanliness with high-quality padding and thin borders.

def styled_button(parent, text: str, command=None, primary: bool = True) -> ttk.Button:
    style = "Primary.TButton" if primary else "Ghost.TButton"
    return ttk.Button(parent, text=text, command=command, style=style, cursor="hand2")


def section_title(parent, text: str) -> tk.Label:
    c = get_colors()
    return tk.Label(
        parent, text=text, font=("Segoe UI", 20, "bold"),
        fg=c["text"], bg=c["bg"],
    )


def themed_label(parent, text: str, muted: bool = False, bg: str | None = None) -> tk.Label:
    c = get_colors()
    bg = bg or c["bg"]
    fg = c["text_muted"] if muted else c["text"]
    return tk.Label(parent, text=text, bg=bg, fg=fg)


def modern_entry(parent, textvariable=None, show=None, width=30) -> tk.Entry:
    c = get_colors()
    kw = dict(
        textvariable=textvariable, font=("Segoe UI", 11), relief="flat",
        highlightthickness=2, highlightbackground=c["border"],
        highlightcolor=c["primary"], bg=c["card"], fg=c["text"],
        insertbackground=c["text"],
    )
    if show:
        kw["show"] = show
    e = tk.Entry(parent, **kw)
    if width:
        e.config(width=width)
    return e


def metric_value_color(key: str) -> str:
    c = get_colors()
    if key == "stock":
        return c["danger"]
    if get_mode() == "dark":
        return "#FFFFFF"
    return c["primary_dark"]
