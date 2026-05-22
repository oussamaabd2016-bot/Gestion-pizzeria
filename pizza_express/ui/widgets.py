"""Reusable modern UI widgets."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from pizza_express.logic.validators import normalize_phone
from pizza_express.ui.theme import get_colors


class PhoneEntry(tk.Frame):
    def __init__(self, parent, textvariable: tk.StringVar | None = None, **kwargs) -> None:
        c = get_colors()
        bg = kwargs.pop("bg", c["card"])
        super().__init__(parent, bg=bg)
        self.var = textvariable or tk.StringVar()
        self.entry = tk.Entry(
            self, textvariable=self.var, font=("Segoe UI", 11),
            relief="flat", highlightthickness=1,
            highlightbackground=c["border"], highlightcolor=c["primary"],
            bg=c["card"], fg=c["text"], insertbackground=c["text"],
        )
        self.entry.pack(fill="x", ipady=8)
        self.entry.bind("<KeyRelease>", self._filter)

    def _filter(self, _e=None) -> None:
        d = normalize_phone(self.var.get())
        if self.var.get() != d:
            self.var.set(d)

    def get(self) -> str:
        return self.var.get()


class NumericEntry(tk.Frame):
    def __init__(self, parent, textvariable: tk.StringVar, width: int = 10, **kwargs) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["card"])
        self.var = textvariable
        self.entry = tk.Entry(
            self, textvariable=self.var, width=width, font=("Segoe UI", 11),
            relief="flat", highlightthickness=1,
            highlightbackground=c["border"], highlightcolor=c["primary"],
            bg=c["card"], fg=c["text"], insertbackground=c["text"],
        )
        self.entry.pack(fill="x", ipady=6)
        self.entry.bind("<KeyRelease>", self._validate_numeric)

    def _validate_numeric(self, _e=None) -> None:
        v = self.var.get()
        cleaned = "".join(c for c in v if c.isdigit() or c in ".,")
        if v != cleaned:
            self.var.set(cleaned)


class CollapsibleSection(tk.Frame):
    def __init__(self, parent, title: str, **kwargs) -> None:
        c = get_colors()
        super().__init__(parent, bg=c["bg"], **kwargs)
        self._open = tk.BooleanVar(value=False)
        self.header = tk.Frame(self, bg=c["card"], cursor="hand2")
        self.header.pack(fill="x", pady=4)
        self.arrow = tk.Label(self.header, text="▶", bg=c["card"], fg=c["primary"], font=("Segoe UI", 12))
        self.arrow.pack(side="left", padx=12, pady=12)
        self.title_lbl = tk.Label(
            self.header, text=title, bg=c["card"], fg=c["text"],
            font=("Segoe UI", 12, "bold"), anchor="w",
        )
        self.title_lbl.pack(side="left", fill="x", expand=True, pady=12)
        self.body = tk.Frame(self, bg=c["bg"])
        for w in (self.header, self.arrow, self.title_lbl):
            w.bind("<Button-1>", self._toggle)
        self.header.bind("<Button-1>", self._toggle)

    def _toggle(self, _e=None) -> None:
        if self._open.get():
            self.body.pack_forget()
            self.arrow.config(text="▶")
            self._open.set(False)
        else:
            self.body.pack(fill="x", padx=8, pady=(0, 8))
            self.arrow.config(text="▼")
            self._open.set(True)

    def get_body(self) -> tk.Frame:
        return self.body

    def set_open(self, open_: bool = True) -> None:
        if open_ and not self._open.get():
            self._toggle()


class ScrollableTreePanel(ttk.Frame):
    """Treeview with vertical scrollbar + page navigation."""

    def __init__(
        self, parent, columns: tuple[str, ...], headings: dict[str, str],
        page_size: int = 25, height: int = 16, on_select=None, **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.page_size = page_size
        self._all_rows: list[tuple[str, tuple, tuple]] = []  # iid, values, tags
        self._page = 0
        self._on_select = on_select

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=height)
        for col in columns:
            self.tree.heading(col, text=headings.get(col, col))
            self.tree.column(col, width=headings.get(f"{col}_width", 100), stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda e: on_select())

        pag = tk.Frame(self, bg=get_colors()["bg"])
        pag.pack(fill="x", pady=4)
        c = get_colors()
        self.page_lbl = tk.Label(pag, text="Page 1/1", bg=c["bg"], fg=c["text_muted"])
        self.page_lbl.pack(side="left")
        ttk.Button(pag, text="◀ Precedent", command=self._prev_page).pack(side="right", padx=2)
        ttk.Button(pag, text="Suivant ▶", command=self._next_page).pack(side="right", padx=2)

    def set_rows(self, rows: list[tuple[str, tuple, tuple | None]]) -> None:
        self._all_rows = [(iid, vals, tags or ()) for iid, vals, tags in rows] if rows else []
        self._page = 0
        self._render_page()

    def _render_page(self) -> None:
        self.tree.delete(*self.tree.get_children())
        total = max(1, (len(self._all_rows) + self.page_size - 1) // self.page_size)
        start = self._page * self.page_size
        chunk = self._all_rows[start : start + self.page_size]
        for iid, vals, tags in chunk:
            self.tree.insert("", "end", iid=iid, values=vals, tags=tags)
        self.page_lbl.config(text=f"Page {self._page + 1}/{total} ({len(self._all_rows)} lignes)")

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._render_page()

    def _next_page(self) -> None:
        max_page = (len(self._all_rows) - 1) // self.page_size
        if self._page < max_page:
            self._page += 1
            self._render_page()

    def selection_iid(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None
