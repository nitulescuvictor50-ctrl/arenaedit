#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArenaEdit — fereastra de navigare printre prompt-urile predefinite.

Este un ecran separat construit cu customtkinter, deschis din aplicația principală
pe butonul „📚 Prompt-uri”. Oferă căutare, filtrare pe categorii și butonul
„Folosește”, după care predă promptul ales tab-ului corespunzător.
"""
from __future__ import annotations

import customtkinter as ctk

from core.prompts import CATEGORIES, PROMPT_LIBRARY, Prompt, search_prompts


class PromptLibraryWindow(ctk.CTkToplevel):
    """Fereastra de selecție a prompt-urilor predefinite."""

    def __init__(self, master, on_use=None):
        super().__init__(master)
        self.on_use = on_use          # apelat cu obiectul Prompt ales

        self.title("Librărie de prompt-uri — ArenaEdit")
        self.geometry("880x600")
        self.minsize(760, 480)
        self.resizable(True, True)
        self.after(10, self._lift)

        self.font_h = ctk.CTkFont(family="Segoe UI", size=15, weight="bold")
        self.font_n = ctk.CTkFont(family="Segoe UI", size=13)
        self.font_small = ctk.CTkFont(family="Segoe UI", size=11)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_list()
        self._build_sidebar()
        self._render(PROMPT_LIBRARY)

    # ------------------------------------------------------------------ ajutor
    def _lift(self):
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    # ------------------------------------------------------------- UI sidebar
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color="#151515")
        sb.grid(row=0, column=0, sticky="nsw")
        sb.grid_propagate(False)

        ctk.CTkLabel(sb, text="📚 Prompt-uri", font=ctk.CTkFont(
            family="Segoe UI", size=20, weight="bold"), text_color="#4f8cff"
        ).pack(padx=16, anchor="w", pady=(18, 0))
        ctk.CTkLabel(sb, text="Propuneri testate pentru generare și editare.",
                     font=self.font_small, text_color="#8a8a8a", wraplength=190,
                     justify="left").pack(padx=16, anchor="w", pady=(2, 12))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        self.search_entry = ctk.CTkEntry(sb, textvariable=self.search_var,
                                         placeholder_text="Caută…",
                                         height=32, font=self.font_n)
        self.search_entry.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(sb, text="Categorie", font=self.font_h, anchor="w"
                     ).pack(fill="x", padx=16, pady=(4, 4))

        self.menu = ctk.CTkScrollableFrame(sb, fg_color="transparent")
        self.menu.pack(fill="both", expand=True, padx=(8, 6), pady=(0, 8))
        self._cat_buttons: dict[str, ctk.CTkButton] = {}

        cats = ["Toate categoriile"] + list(CATEGORIES)
        for cat in cats:
            btn = ctk.CTkButton(
                self.menu, text=cat, font=self.font_n, anchor="w", height=34,
                corner_radius=8, fg_color="transparent", hover_color="#242424",
                command=lambda c=cat: self._set_category(c))
            btn.pack(fill="x", pady=2)
            self._cat_buttons[cat] = btn
        self._set_category("Toate categoriile")

        ctk.CTkLabel(sb, text=f"{len(PROMPT_LIBRARY)} prompt-uri · fereastra se închide cu ×",
                     font=self.font_small, text_color="#5a5a5a", wraplength=190,
                     justify="left").pack(padx=16, pady=(4, 12), anchor="w")

    # ------------------------------------------------------------- UI lista
    def _build_list(self):
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.list_frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------- filtrare
    def _on_search(self):
        self._render(search_prompts(self.search_var.get(), self._category))

    def _set_category(self, cat: str):
        self._category = cat
        for name, btn in self._cat_buttons.items():
            btn.configure(fg_color="#242424" if name == cat else "transparent")
        self._render(search_prompts(self.search_var.get(), cat))

    # ------------------------------------------------------------- randare
    def _render(self, prompts: list[Prompt]):
        for w in self.list_frame.winfo_children():
            w.destroy()

        if not prompts:
            ctk.CTkLabel(self.list_frame, text="Niciun prompt găsit.\n"
                         "Încearcă alt termen de căutare.",
                         font=self.font_n, text_color="#7a7a7a", justify="center"
                         ).pack(pady=40)
            return

        last_cat = None
        for p in prompts:
            if p.categorie != last_cat:
                last_cat = p.categorie
                ctk.CTkLabel(self.list_frame, text=p.categorie.upper(),
                             font=self.font_small, text_color="#4f8cff", anchor="w"
                             ).pack(fill="x", pady=(12, 3), padx=4)
            self._add_card(p)

    def _add_card(self, p: Prompt):
        card = ctk.CTkFrame(self.list_frame, fg_color="#1d1d1d", corner_radius=10)
        card.pack(fill="x", padx=2, pady=4)
        card.grid_columnconfigure(0, weight=1)

        head = f"{p.titlu}"
        if p.target == "editare":
            head += f"   ·   {p.mod}"
        ctk.CTkLabel(card, text=head, font=self.font_h, anchor="w"
                     ).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(card, text=p.descriere, font=self.font_n, text_color="#9a9a9a",
                     wraplength=520, justify="left", anchor="w"
                     ).grid(row=1, column=0, sticky="w", padx=14, pady=(2, 0))
        ctk.CTkLabel(card, text=p.prompt, font=self.font_small, text_color="#6f6f6f",
                     wraplength=520, justify="left", anchor="w"
                     ).grid(row=2, column=0, sticky="w", padx=14, pady=(4, 0))

        btn = ctk.CTkButton(card, text="Folosește  →", width=110, height=30,
                            font=self.font_n,
                            command=lambda pp=p: self._use(pp))
        btn.grid(row=0, column=1, rowspan=3, padx=(12, 14), pady=10)
        if p.negativ:
            ctk.CTkLabel(card, text="✓ include prompt negativ", font=self.font_small,
                         text_color="#4cc38a", anchor="w"
                         ).grid(row=3, column=0, sticky="w", padx=14, pady=(0, 10))

    # ------------------------------------------------------------- aplicare
    def _use(self, p: Prompt):
        if self.on_use:
            self.on_use(p)
        self.destroy()


__all__ = ["PromptLibraryWindow", "search_prompts", "PROMPT_LIBRARY", "CATEGORIES"]
