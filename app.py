#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArenaEdit — Studio AI local pentru imagini (Windows 11)
=======================================================
* Generare imagini din text (Stable Diffusion, local)
* Editare prin instrucțiuni în limbaj natural (InstructPix2Pix)
* Operații de bază: redimensionare, rotire, decupare, ajustări, conversie
* Totul rulează 100% local, pe calculatorul tău.

Rulează:  python app.py   (sau ArenaEdit.exe construit cu BUILD_EXE.bat)
"""
from __future__ import annotations

import json
import os
import platform
import random
import re
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime

# ------------------------------------------------------------------ căi
if getattr(sys, "frozen", False):          # rulat din .exe (PyInstaller)
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    RES_DIR = sys._MEIPASS                 # noqa: SLF001
else:                                      # rulat din sursă
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RES_DIR = APP_DIR

MODELS_DIR = os.path.join(APP_DIR, "models")
SETTINGS_FILE = os.path.join(APP_DIR, "setari.json")

# cache-ul Hugging Face trebuie setat ÎNAINTE de importul huggingface_hub
os.environ.setdefault("HF_HOME", MODELS_DIR)
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from PIL import Image, ImageTk            # noqa: E402
import tkinter as tk                       # noqa: E402
from tkinter import filedialog, messagebox  # noqa: E402
import customtkinter as ctk                # noqa: E402

from core import basics                    # noqa: E402
from core.models import (                  # noqa: E402
    CATALOG, ModelInfo, ModelManager, find_model, get_models, human_gb,
)
from core.prompts import PROMPT_LIBRARY    # noqa: E402
from core.prompt_ui import PromptLibraryWindow  # noqa: E402

APP_NAME = "ArenaEdit"
VERSION = "1.1.0"
PREVIEW_BOX = (640, 560)

CUSTOM_LABEL = "Alt model (ID Hugging Face)…"
SIZE_OPTIONS = ["512×512", "768×768", "768×512", "512×768",
                "1024×1024 (SDXL)", "1024×768 (SDXL)", "768×1024 (SDXL)"]


# ------------------------------------------------------------------ utilitare
def resource_path(rel: str) -> str:
    return os.path.join(RES_DIR, rel)


def default_output_dir() -> str:
    if platform.system() == "Windows":
        try:
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x27, None, 0, buf)  # Poze mele
            return os.path.join(buf.value, "ArenaEdit")
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Pictures", "ArenaEdit")


def load_settings() -> dict:
    defaults = {
        "device_pref": "auto",
        "output_dir": default_output_dir(),
        "auto_save": True,
    }
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        defaults.update({k: v for k, v in data.items() if k in defaults})
    except Exception:
        pass
    return defaults


def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def open_path(path: str):
    try:
        if platform.system() == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Nu pot deschide {path}: {e}")


# ================================================================== aplicația
class ArenaEditApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.settings = load_settings()
        os.makedirs(self.settings["output_dir"], exist_ok=True)

        self.mgr = ModelManager(MODELS_DIR)
        self.engine = None                    # se inițializează asincron (import torch lent)
        self.custom_models: list[ModelInfo] = []

        self._task_running = False
        self._cancel_event = threading.Event()
        self._busy_widgets: list = []
        self._img_refs: dict[str, object] = {}
        self._gen_results: list[Image.Image] = []
        self._gen_idx = 0
        self._gen_last_seed: int | None = None

        # --- fereastră
        self.title(f"{APP_NAME} — Studio AI pentru imagini")
        self.geometry("1280x800")
        self.minsize(1140, 720)
        try:
            self.iconbitmap(resource_path(os.path.join("assets", "icon.ico")))
        except Exception:
            pass

        self.font_title = ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        self.font_h = ctk.CTkFont(family="Segoe UI", size=15, weight="bold")
        self.font_n = ctk.CTkFont(family="Segoe UI", size=13)
        self.font_small = ctk.CTkFont(family="Segoe UI", size=11)
        self.font_btn = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")

        # --- schelet: sidebar | conținut | bară de status
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_statusbar()

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.tabs: dict[str, ctk.CTkFrame] = {}
        self._build_generate_tab()
        self._build_edit_tab()
        self._build_basic_tab()
        self._build_history_tab()
        self._build_settings_tab()
        self._select_tab("generare")

        # --- scurtături globale
        self.bind_all("<Control-v>", lambda e: self._global_paste())
        self.bind_all("<Control-V>", lambda e: self._global_paste())
        self.bind_all("<Control-Return>", lambda e: self._global_action())
        self.bind_all("<Control-KP_Enter>", lambda e: self._global_action())
        self.bind_all("<Control-z>", lambda e: self._global_undo())
        self.bind_all("<Control-Z>", lambda e: self._global_undo())

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # pornim motorul AI în fundal (import torch ~5–10 s prima dată)
        self.set_status("Se pornește motorul AI… (prima încărcare durează câteva secunde)")
        threading.Thread(target=self._engine_import_thread, daemon=True).start()

    # ================================================================ infrastructură
    def _post(self, fn):
        """Programează o funcție pe firul interfeței (thread-safe)."""
        try:
            self.after(0, fn)
        except RuntimeError:
            pass

    def set_status(self, text: str):
        try:
            self.status_label.configure(text=text)
        except Exception:
            pass

    def set_progress(self, frac: float | None):
        """frac 0..1 determinate; None = ascuns/indeterminat."""
        try:
            if frac is None:
                self.progress.stop()
                self.progress.set(0)
            else:
                self.progress.set(max(0.0, min(1.0, frac)))
        except Exception:
            pass

    def _set_busy(self, busy: bool, extra: list | None = None):
        widgets = list(self._busy_widgets) + list(extra or [])
        for w in widgets:
            try:
                w.configure(state="disabled" if busy else "normal")
            except Exception:
                pass
        try:
            self.btn_cancel.configure(state="normal" if busy else "disabled")
        except Exception:
            pass
        if not busy:
            self._cancel_event.clear()

    def _run_task(self, work, on_done=None, busy_widgets: list | None = None):
        """Rulează work() într-un fir; on_done(ok, data, msg) pe firul UI."""
        if self._task_running:
            messagebox.showwarning(APP_NAME, "Există deja o operațiune în curs.")
            return False
        self._task_running = True
        self._busy_widgets = busy_widgets or []
        self._cancel_event.clear()
        self._set_busy(True)

        def wrapper():
            ok, data, msg = True, None, ""
            try:
                ok, data, msg = work()
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                ok, msg = False, str(e)

            def finish():
                self._task_running = False
                self._set_busy(False)
                self.set_progress(None)
                if on_done:
                    try:
                        on_done(ok, data, msg)
                    except Exception:
                        traceback.print_exc()
            self._post(finish)

        threading.Thread(target=wrapper, daemon=True).start()
        return True

    def _engine_import_thread(self):
        try:
            from core.engine import AIEngine
            eng = AIEngine(MODELS_DIR, self.settings.get("device_pref", "auto"))
            self._post(lambda: self._engine_ready(eng))
        except Exception as e:
            err = str(e)
            self._post(lambda: self.set_status(f"Eroare la pornirea motorului AI: {err}"))

    def _engine_ready(self, eng):
        self.engine = eng
        self._update_device_chip()
        self._refresh_model_dropdowns()
        self._refresh_model_rows()
        self._update_first_run_hint()

    def _update_device_chip(self):
        if not self.engine:
            return
        d = self.engine.device
        if d["kind"] == "cuda":
            txt = f"🖥  GPU: {d['name']}"
            if d.get("vram_gb"):
                txt += f" · {d['vram_gb']:.1f} GB"
            color = "#4cc38a"
        else:
            txt = "⚙  CPU — generare lentă (fără CUDA)"
            color = "#e5a50a"
        try:
            self.device_label.configure(text=txt, text_color=color)
        except Exception:
            pass
        if d.get("warning"):
            self.set_status(d["warning"])

    # ================================================================ bara laterală
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=216, corner_radius=0, fg_color="#151515")
        sb.grid(row=0, column=0, rowspan=2, sticky="nsw")
        sb.grid_propagate(False)

        ctk.CTkLabel(sb, text="Arena", font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
                     text_color="#4f8cff").pack(padx=22, anchor="w", pady=(22, 0))
        ctk.CTkLabel(sb, text="STUDIO AI PENTRU IMAGINI", font=self.font_small,
                     text_color="#8a8a8a").pack(padx=22, anchor="w", pady=(0, 18))

        nav = [
            ("generare", "✦  Generare", "Imagini noi din text"),
            ("editare", "✎  Editare AI", "Modifică o imagine prin prompt"),
            ("de_baza", "⌗  Editare de bază", "Redimensionare, rotire, decupare"),
            ("istoric", "⊞  Istoric", "Imaginile salvate"),
            ("setari", "⚙  Setări", "Modele, dispozitiv, foldere"),
        ]
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for name, label, sub in nav:
            box = ctk.CTkFrame(sb, fg_color="transparent")
            box.pack(fill="x", padx=12, pady=3)
            btn = ctk.CTkButton(
                box, text=label, font=self.font_h, anchor="w", height=42,
                corner_radius=10, fg_color="transparent", hover_color="#242424",
                command=lambda n=name: self._select_tab(n))
            btn.pack(fill="x")
            ctk.CTkLabel(box, text=sub, font=self.font_small, text_color="#6f6f6f",
                         anchor="w").pack(fill="x", padx=(16, 0))
            self._nav_buttons[name] = btn

        # buton librărie de prompt-uri (nu e tab, deschide o fereastră)
        box = ctk.CTkFrame(sb, fg_color="transparent")
        box.pack(fill="x", padx=12, pady=3)
        ctk.CTkButton(
            box, text="📚  Prompt-uri", font=self.font_h, anchor="w", height=42,
            corner_radius=10, fg_color="transparent", hover_color="#242424",
            command=self._open_prompt_library
        ).pack(fill="x")
        ctk.CTkLabel(box, text="Propuneri de prompt gata făcute", font=self.font_small,
                     text_color="#6f6f6f", anchor="w").pack(fill="x", padx=(16, 0))

        # chip dispozitiv
        self.device_label = ctk.CTkLabel(sb, text="… se detectează dispozitivul",
                                         font=self.font_small, text_color="#8a8a8a",
                                         wraplength=180, justify="left")
        self.device_label.pack(side="bottom", padx=18, pady=(4, 8), anchor="w")
        ctk.CTkLabel(sb, text=f"v{VERSION} · 100% local · datele nu părăsesc PC-ul",
                     font=self.font_small, text_color="#5a5a5a", wraplength=180,
                     justify="left").pack(side="bottom", padx=18, pady=(2, 4), anchor="w")

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color="#101010")
        bar.grid(row=2, column=0, columnspan=2, sticky="sew")
        bar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(bar, text="Gata.", font=self.font_small,
                                         anchor="w", text_color="#bdbdbd")
        self.status_label.grid(row=0, column=0, sticky="w", padx=14)

        self.progress = ctk.CTkProgressBar(bar, width=180, height=8)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, padx=(0, 10), pady=12)

        self.btn_cancel = ctk.CTkButton(
            bar, text="Anulează", width=84, height=26, font=self.font_small,
            fg_color="#c0392b", hover_color="#e74c3c", state="disabled",
            command=self._cancel_current)
        self.btn_cancel.grid(row=0, column=2, padx=(0, 12), pady=10)

    def _cancel_current(self):
        self._cancel_event.set()
        self.set_status("Se anulează…")

    def _select_tab(self, name: str):
        for key, frame in self.tabs.items():
            frame.grid_remove()
        self.tabs[name].grid(row=0, column=0, sticky="nsew")
        for key, btn in self._nav_buttons.items():
            btn.configure(fg_color="#242424" if key == name else "transparent")
        if name == "istoric":
            self._refresh_history()
        if name == "setari":
            self._refresh_model_rows()

    # ================================================================ librărie prompt-uri
    def _open_prompt_library(self):
        if getattr(self, "_prompt_win", None) is not None and self._prompt_win.winfo_exists():
            self._prompt_win.lift()
            self._prompt_win.focus_force()
            return
        self._prompt_win = PromptLibraryWindow(self, on_use=self._apply_prompt)
        self.set_status("Librărie de prompt-uri deschisă — alege unul și apasă „Folosește”.")

    def _apply_prompt(self, p):
        """Aplică promptul ales în tab-ul potrivit, apoi comută pe el."""
        if p.target == "generare":
            self.gen_prompt.delete("1.0", "end")
            self.gen_prompt.insert("1.0", p.prompt)
            self.gen_negative.delete(0, "end")
            if p.negativ:
                self.gen_negative.insert(0, p.negativ)
            self._select_tab("generare")
            self.set_status(f"Prompt aplicat: „{p.titlu}” — apasă „Generează”.")
        else:
            self._set_edit_mode(p.mod)
            self.edit_prompt.delete("1.0", "end")
            self.edit_prompt.insert("1.0", p.prompt)
            self.edit_negative.delete(0, "end")
            if p.negativ:
                self.edit_negative.insert(0, p.negativ)
            self._select_tab("editare")
            self.set_status(f"Prompt aplicat: „{p.titlu}” — încarcă o imagine și apasă "
                            "„Editează imaginea”.")

    # ================================================================ tab GENERARE
    def _build_generate_tab(self):
        tab = ctk.CTkFrame(self.container, fg_color="transparent")
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        self.tabs["generare"] = tab

        # --- mesaj prima rulare (modelul lipsește)
        self.hint_frame = ctk.CTkFrame(tab, fg_color="#2b2340", corner_radius=12)
        ctk.CTkLabel(self.hint_frame,
                     text="Bine ai venit! Înainte de prima generare, descarcă un model AI "
                          "(o singură dată, ~2,7 GB pentru SD Turbo).",
                     font=self.font_n, text_color="#d9d2f0", wraplength=560,
                     justify="left").pack(side="left", padx=16, pady=12)
        self.hint_btn = ctk.CTkButton(
            self.hint_frame, text="Descarcă SD Turbo", font=self.font_btn,
            command=lambda: self._download_model("stabilityai/sd-turbo"))
        self.hint_btn.pack(side="right", padx=14)
        self.hint_frame.grid_forget()

        # --- coloana de comenzi (stânga)
        left = ctk.CTkFrame(tab, width=360, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsw", padx=(16, 8), pady=(8, 12))
        left.grid_columnconfigure(0, weight=1)

        def L(text, row):
            ctk.CTkLabel(left, text=text, font=self.font_h, anchor="w").grid(
                row=row, column=0, sticky="w", pady=(12, 2))
        r = 0
        L("Model", r); r += 1
        self.gen_model_menu = ctk.CTkOptionMenu(left, values=["…"], height=34,
                                                font=self.font_n,
                                                command=self._on_gen_model_change)
        self.gen_model_menu.grid(row=r, column=0, sticky="ew"); r += 1
        self.gen_custom_label = ctk.CTkLabel(left, text="ID model (ex.: stabilityai/sd-turbo):",
                                             font=self.font_small, text_color="#9a9a9a", anchor="w")
        self.gen_custom_entry = ctk.CTkEntry(left, placeholder_text="organizatie/model",
                                             height=30, font=self.font_n)
        self.gen_custom_label.grid(row=r, column=0, sticky="ew", pady=(6, 0)); r += 1
        self.gen_custom_entry.grid(row=r, column=0, sticky="ew"); r += 1
        self.gen_custom_label.grid_remove(); self.gen_custom_entry.grid_remove()

        L("Descriere (prompt)", r); r += 1
        self.gen_prompt = ctk.CTkTextbox(left, height=104, font=self.font_n)
        self.gen_prompt.grid(row=r, column=0, sticky="ew"); r += 1
        ctk.CTkLabel(left, text="Descre ce imagine vrei — poți scrie în română sau engleză.",
                     font=self.font_small, text_color="#8a8a8a", anchor="w",
                     justify="left").grid(row=r, column=0, sticky="w"); r += 1

        L("Prompt negativ (ce să NU apară)", r); r += 1
        self.gen_negative = ctk.CTkEntry(left, height=30, font=self.font_n)
        self.gen_negative.grid(row=r, column=0, sticky="ew"); r += 1

        L("Dimensiune", r); r += 1
        self.gen_size = ctk.CTkOptionMenu(left, values=SIZE_OPTIONS, height=32, font=self.font_n)
        self.gen_size.set("512×512")
        self.gen_size.grid(row=r, column=0, sticky="ew"); r += 1

        # pași + guidance
        row = ctk.CTkFrame(left, fg_color="transparent"); row.grid(row=r, column=0, sticky="ew"); r += 1
        row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(row, text="Pași", font=self.font_n).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(row, text="Ghidaj (CFG)", font=self.font_n).grid(row=0, column=1, sticky="w")
        self.gen_steps_val = ctk.CTkLabel(row, text="4", font=self.font_n, text_color="#4f8cff")
        self.gen_steps_val.grid(row=1, column=0, sticky="w")
        self.gen_guid_val = ctk.CTkLabel(row, text="0.0", font=self.font_n, text_color="#4f8cff")
        self.gen_guid_val.grid(row=1, column=1, sticky="w")
        self.gen_steps = ctk.CTkSlider(row, from_=1, to=50, number_of_steps=49, width=150,
                                       command=lambda v: self.gen_steps_val.configure(text=str(int(v))))
        self.gen_steps.set(4)
        self.gen_steps.grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.gen_guid = ctk.CTkSlider(row, from_=0, to=15, number_of_steps=30, width=150,
                                      command=lambda v: self.gen_guid_val.configure(text=f"{v:.1f}"))
        self.gen_guid.set(0.0)
        self.gen_guid.grid(row=2, column=1, sticky="w", pady=(0, 8))

        # semință + lot
        row2 = ctk.CTkFrame(left, fg_color="transparent"); row2.grid(row=r, column=0, sticky="ew"); r += 1
        row2.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row2, text="Semință", font=self.font_n).grid(row=0, column=0, sticky="w")
        self.gen_seed_entry = ctk.CTkEntry(row2, width=110, height=28, font=self.font_n,
                                           placeholder_text="aleatorie")
        self.gen_seed_entry.grid(row=0, column=1, sticky="w", padx=(8, 12))
        self.gen_seed_lock = ctk.CTkCheckBox(row2, text="repetă", font=self.font_small)
        self.gen_seed_lock.grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(row2, text="Câte imagini", font=self.font_n).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.gen_count = ctk.CTkSegmentedButton(row2, values=["1", "2", "3", "4"], height=28,
                                                font=self.font_small)
        self.gen_count.set("1")
        self.gen_count.grid(row=1, column=1, columnspan=2, sticky="w", pady=(8, 0))

        self.gen_seed_lbl = ctk.CTkLabel(left, text="", font=self.font_small, text_color="#8a8a8a")
        self.gen_seed_lbl.grid(row=r, column=0, sticky="w", pady=(8, 0)); r += 1

        self.btn_generate = ctk.CTkButton(left, text="✦  Generează", height=44, font=self.font_btn,
                                          command=self._on_generate)
        self.btn_generate.grid(row=r, column=0, sticky="ew", pady=(14, 0)); r += 1
        ctk.CTkLabel(left, text="Scurtătură: Ctrl+Enter", font=self.font_small,
                     text_color="#6f6f6f").grid(row=r, column=0, sticky="w", pady=(4, 0)); r += 1

        # --- zona de previzualizare (dreapta)
        right = ctk.CTkFrame(tab, fg_color="#1a1a1a", corner_radius=14)
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=(8, 12))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        self.gen_preview = ctk.CTkLabel(right, text="\n\nÎncă nicio imagine generată.\n"
                                       "Scrie o descriere și apasă „Generează”.",
                                       font=ctk.CTkFont(family="Segoe UI", size=16),
                                       text_color="#7a7a7a", justify="center")
        self.gen_preview.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        nav = ctk.CTkFrame(right, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        nav.grid_columnconfigure(1, weight=1)
        self.gen_nav_label = ctk.CTkLabel(nav, text="", font=self.font_n, text_color="#9a9a9a")
        self.gen_nav_label.grid(row=0, column=1)
        self.btn_gen_prev = ctk.CTkButton(nav, text="◀", width=44, height=34,
                                          command=lambda: self._show_gen_idx(self._gen_idx - 1))
        self.btn_gen_prev.grid(row=0, column=0, sticky="w")
        self.btn_gen_next = ctk.CTkButton(nav, text="▶", width=44, height=34,
                                          command=lambda: self._show_gen_idx(self._gen_idx + 1))
        self.btn_gen_next.grid(row=0, column=2, sticky="e")
        self.btn_gen_save = ctk.CTkButton(nav, text="Salvează ca…", width=120, height=34,
                                          command=self._save_gen_current, state="disabled")
        self.btn_gen_save.grid(row=0, column=3, padx=(12, 0))

    # ------------------------------------------------ acces la modele (dropdown-uri)
    def _model_items(self, purpose: str) -> list[tuple[str, str]]:
        items = []
        for m in get_models(purpose):
            mark = "  ✓" if self.mgr.is_installed(m.repo_id) else f"  · ~{m.approx_gb:.1f} GB"
            items.append((f"{m.name}{mark}", m.repo_id))
        for m in self.custom_models:
            if m.purpose == purpose or purpose == "edit":
                mark = "  ✓" if self.mgr.is_installed(m.repo_id) else ""
                items.append((f"{m.name} (custom){mark}", m.repo_id))
        if purpose == "edit":  # orice model poate fi folosit pentru „reimaginare”
            for m in get_models("generate"):
                if m.repo_id not in [i[1] for i in items]:
                    mark = "  ✓" if self.mgr.is_installed(m.repo_id) else f"  · ~{m.approx_gb:.1f} GB"
                    items.append((f"{m.name} (reimaginare){mark}", m.repo_id))
        return items

    def _refresh_model_dropdowns(self):
        for menu, items, custom_lbl, custom_entry, purpose in (
            (self.gen_model_menu, self._model_items("generate"),
             self.gen_custom_label, self.gen_custom_entry, "generate"),
            (self.edit_model_menu, self._model_items("edit"),
             self.edit_custom_label, self.edit_custom_entry, "edit"),
        ):
            current = menu.get()
            values = [lbl for lbl, _ in items] + [CUSTOM_LABEL]
            menu.configure(values=values)
            # păstrează selecția dacă mai există
            if current in values:
                menu.set(current)
            else:
                menu.set(values[0])
                self._on_model_menu_set(purpose, values[0])

    def _on_gen_model_change(self, _label=None):
        self._on_model_menu_set("generate", self.gen_model_menu.get())
        self._update_first_run_hint()

    def _on_edit_model_change(self, _label=None):
        self._on_model_menu_set("edit", self.edit_model_menu.get())

    def _on_model_menu_set(self, purpose: str, label: str):
        if purpose == "generate":
            menu, custom_lbl, custom_entry = self.gen_model_menu, self.gen_custom_label, self.gen_custom_entry
            sliders = (self.gen_steps, self.gen_guid, self.gen_steps_val, self.gen_guid_val)
        else:
            menu, custom_lbl, custom_entry = self.edit_model_menu, self.edit_custom_label, self.edit_custom_entry
            sliders = None
        if label == CUSTOM_LABEL:
            custom_lbl.grid(); custom_entry.grid()
            return
        custom_lbl.grid_remove(); custom_entry.grid_remove()

        repo = None
        for lbl, rid in self._model_items(purpose):
            if lbl == label:
                repo = rid
                break
        m = find_model(repo) if repo else None
        if m is None:
            return
        if purpose == "generate" and sliders:
            if m.turbo:
                sliders[0].set(4); sliders[1].set(0.0)
                sliders[2].configure(text="4"); sliders[3].configure(text="0.0")
                if "1024" in self.gen_size.get() and "SDXL" in self.gen_size.get():
                    self.gen_size.set("512×512")
            else:
                sliders[0].set(30); sliders[1].set(7.5)
                sliders[2].configure(text="30"); sliders[3].configure(text="7.5")
                if m.repo_id.startswith("stabilityai/stable-diffusion-xl"):
                    self.gen_size.set("1024×1024 (SDXL)")
        if purpose == "edit" and m.pix2pix:
            self._set_edit_mode("Instrucțiune")

    def _selected_repo(self, purpose: str) -> tuple[str | None, str]:
        """Returnează (repo_id, eroare)."""
        if purpose == "generate":
            menu, entry = self.gen_model_menu, self.gen_custom_entry
        else:
            menu, entry = self.edit_model_menu, self.edit_custom_entry
        label = menu.get()
        if label != CUSTOM_LABEL:
            for lbl, rid in self._model_items(purpose):
                if lbl == label:
                    return rid, ""
        raw = entry.get().strip()
        if not re.fullmatch(r"[\w.\-]+/[\w.\-]+", raw):
            return None, "Scrie un ID de model valid (ex.: stabilityai/sd-turbo)."
        return raw, ""

    def _update_first_run_hint(self):
        installed = self.mgr.is_installed("stabilityai/sd-turbo") or \
            any(self.mgr.is_installed(m.repo_id) for m in CATALOG)
        if installed or not self.engine:
            self.hint_frame.grid_forget()
        else:
            self.hint_frame.grid(row=0, column=0, columnspan=2, sticky="ew",
                                 padx=16, pady=(12, 0))

    # ------------------------------------------------ acțiune: GENERARE
    def _on_generate(self):
        if self.engine is None:
            messagebox.showinfo(APP_NAME, "Motorul AI încă se pornește — mai așteaptă câteva secunde.")
            return
        repo, err = self._selected_repo("generate")
        if not repo:
            messagebox.showwarning(APP_NAME, err)
            return
        prompt = self.gen_prompt.get("1.0", "end-1c").strip()
        if not prompt:
            messagebox.showwarning(APP_NAME, "Scrie întâi o descriere (prompt).")
            return
        negative = self.gen_negative.get().strip()
        try:
            w, h = [int(x) for x in self.gen_size.get().split("(")[0].strip().split("×")]
        except Exception:
            w, h = 512, 512
        steps = int(float(self.gen_steps.get()))
        guidance = float(self.gen_guid.get())
        count = int(self.gen_count.get() or "1")
        seed_txt = self.gen_seed_entry.get().strip()
        if self.gen_seed_lock.get() and self._gen_last_seed is not None and not seed_txt:
            seed = self._gen_last_seed
        elif seed_txt.isdigit():
            seed = int(seed_txt)
        else:
            seed = random.randint(0, 2**31 - 1)
        model = find_model(repo)
        variant = model.variant if model else None

        def progress(frac, msg):
            self._post(lambda: (self.set_progress(frac), self.set_status(msg)))

        def work():
            if not self.mgr.is_installed(repo):
                self._post(lambda: self.set_status(
                    f"Se descarcă modelul {repo} (doar data aceasta)…"))
                if not self._download_blocking(repo, progress):
                    return False, None, f"Descărcarea modelului {repo} a eșuat."
            self._post(lambda: self.set_status("Se încarcă modelul în memorie…"))
            self.engine.load("generate", repo, variant, progress)
            t0 = time.time()
            images = self.engine.generate(
                prompt=prompt, negative=negative, width=w, height=h, steps=steps,
                guidance=guidance, seed=seed, count=count,
                progress=progress, cancel=self._cancel_event)
            if self._cancel_event.is_set() and not images:
                return False, None, "__CANCELLED__"
            return True, (images, seed), f"{len(images)} imagini în {time.time() - t0:.1f} s"

        def done(ok, data, msg):
            if not ok:
                if msg == "__CANCELLED__":
                    self.set_status("Generare anulată.")
                    return
                messagebox.showerror(APP_NAME, msg)
                self.set_status("Eroare la generare.")
                return
            images, used_seed = data
            self._gen_results = images
            self._gen_idx = 0
            self._gen_last_seed = used_seed
            self.gen_seed_lbl.configure(text=f"Semința folosită: {used_seed} "
                                        "(bifează „repetă” pentru a o refolosi)")
            if self.settings.get("auto_save", True):
                for i, img in enumerate(images):
                    self._auto_save(img, "gen", i if len(images) > 1 else None)
            self._show_gen_idx(0)
            self.set_status(f"Gata — {msg}.")

        self._run_task(work, done, busy_widgets=[self.btn_generate, self.btn_gen_save])

    def _download_blocking(self, repo: str, progress=None) -> bool:
        """Descarcă modelul așteptând finalizarea (se apelează din fir de lucru)."""
        evt = threading.Event()
        result = {"ok": False}

        def on_prog(done_b, total_b):
            if total_b:
                frac = min(0.98, done_b / total_b)
                msg = f"Se descarcă modelul… {human_gb(done_b)} / {human_gb(total_b)}"
            else:
                frac, msg = None, f"Se descarcă modelul… {human_gb(done_b)}"
            if progress:
                progress(frac if frac is not None else 0.5, msg)

        def on_done(ok, err):
            result["ok"], result["err"] = ok, err
            evt.set()

        if not self.mgr.start_download(repo, on_prog, on_done):
            # deja o descărcare rulează — așteaptă să se termine
            while self.mgr.busy:
                time.sleep(0.4)
            return self.mgr.is_installed(repo)
        evt.wait()
        self._post(lambda: (self._refresh_model_dropdowns(), self._refresh_model_rows(),
                            self._update_first_run_hint()))
        return result["ok"] and self.mgr.is_installed(repo)

    def _show_gen_idx(self, idx: int):
        if not self._gen_results:
            return
        idx = max(0, min(len(self._gen_results) - 1, idx))
        self._gen_idx = idx
        img = self._gen_results[idx]
        w, h = basics.fit_size(img.width, img.height, *PREVIEW_BOX)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
        self.gen_preview.configure(image=ctk_img, text="")
        self._img_refs["gen"] = ctk_img
        self.gen_nav_label.configure(text=f"{idx + 1} / {len(self._gen_results)} · "
                                     f"{img.width}×{img.height} px")
        self.btn_gen_save.configure(state="normal")

    def _save_gen_current(self):
        if not self._gen_results:
            return
        self._save_as_dialog(self._gen_results[self._gen_idx],
                             f"imagine_{datetime.now():%Y%m%d_%H%M%S}")

    # ================================================================ tab EDITARE AI
    def _build_edit_tab(self):
        tab = ctk.CTkFrame(self.container, fg_color="transparent")
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.tabs["editare"] = tab

        # --- stânga: sursă + comenzi
        left = ctk.CTkFrame(tab, width=380, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsw", padx=(16, 8), pady=(8, 12))
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Imaginea sursă", font=self.font_h, anchor="w").grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        src_row = ctk.CTkFrame(left, fg_color="transparent")
        src_row.grid(row=1, column=0, sticky="ew")
        self.btn_edit_load = ctk.CTkButton(src_row, text="Încarcă imagine…", height=32,
                                           font=self.font_n, command=self._edit_load_dialog)
        self.btn_edit_load.grid(row=0, column=0, sticky="w")
        self.btn_edit_paste = ctk.CTkButton(src_row, text="Lipire (Ctrl+V)", height=32,
                                            font=self.font_n, command=self._edit_paste)
        self.btn_edit_paste.grid(row=0, column=1, padx=(8, 0))

        self.edit_src_label = ctk.CTkLabel(left, text="Nicio imagine încărcată.\n"
                                           "Încarcă un fișier sau lipește din clipboard.",
                                           font=ctk.CTkFont(family="Segoe UI", size=14),
                                           text_color="#7a7a7a", justify="center")
        self.edit_src_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.edit_src_info = ctk.CTkLabel(left, text="", font=self.font_small, text_color="#8a8a8a")
        self.edit_src_info.grid(row=3, column=0, sticky="w")
        self._edit_source: Image.Image | None = None

        ctk.CTkLabel(left, text="Model", font=self.font_h, anchor="w").grid(
            row=4, column=0, sticky="w", pady=(14, 2))
        self.edit_model_menu = ctk.CTkOptionMenu(left, values=["…"], height=34, font=self.font_n,
                                                 command=self._on_edit_model_change)
        self.edit_model_menu.grid(row=5, column=0, sticky="ew")
        self.edit_custom_label = ctk.CTkLabel(left, text="ID model (ex.: timbrooks/instruct-pix2pix):",
                                              font=self.font_small, text_color="#9a9a9a", anchor="w")
        self.edit_custom_entry = ctk.CTkEntry(left, placeholder_text="organizatie/model",
                                              height=30, font=self.font_n)
        self.edit_custom_label.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        self.edit_custom_entry.grid(row=7, column=0, sticky="ew")
        self.edit_custom_label.grid_remove(); self.edit_custom_entry.grid_remove()

        ctk.CTkLabel(left, text="Mod de editare", font=self.font_h, anchor="w").grid(
            row=8, column=0, sticky="w", pady=(14, 2))
        self.edit_mode = ctk.CTkSegmentedButton(left, values=["Instrucțiune", "Reimaginare"],
                                                height=32, font=self.font_n,
                                                command=lambda _v: self._update_edit_ui())
        self.edit_mode.set("Instrucțiune")
        self.edit_mode.grid(row=9, column=0, sticky="ew")

        ctk.CTkLabel(left, text="Instrucțiune / prompt", font=self.font_h, anchor="w").grid(
            row=10, column=0, sticky="w", pady=(12, 2))
        self.edit_prompt = ctk.CTkTextbox(left, height=76, font=self.font_n)
        self.edit_prompt.grid(row=11, column=0, sticky="ew")
        self.edit_negative = ctk.CTkEntry(left, placeholder_text="Prompt negativ (doar Reimaginare)",
                                          height=28, font=self.font_n)
        self.edit_negative.grid(row=12, column=0, sticky="ew", pady=(6, 0))

        chips = ctk.CTkFrame(left, fg_color="transparent")
        chips.grid(row=13, column=0, sticky="ew", pady=(6, 0))
        for i, ex in enumerate(["șterge fundalul", "pune apus de soare", "stil desen pix",
                                "fă-o iarnă"]):
            ctk.CTkButton(chips, text=ex, width=118, height=26, font=self.font_small,
                          fg_color="#2a2a2a", hover_color="#3a3a3a",
                          command=lambda e=ex: self._edit_add_example(e)
                          ).grid(row=0, column=i, padx=(0, 6))

        # slideri
        sl = ctk.CTkFrame(left, fg_color="transparent")
        sl.grid(row=14, column=0, sticky="ew", pady=(8, 0))
        sl.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(sl, text="Pași", font=self.font_n).grid(row=0, column=0, sticky="w")
        self.edit_steps_val = ctk.CTkLabel(sl, text="25", font=self.font_n, text_color="#4f8cff")
        self.edit_steps_val.grid(row=0, column=1, sticky="w")
        self.edit_steps = ctk.CTkSlider(sl, from_=2, to=50, number_of_steps=48, width=300,
                                        command=lambda v: self.edit_steps_val.configure(text=str(int(v))))
        self.edit_steps.set(25)
        self.edit_steps.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self.edit_guid_row_lbl = ctk.CTkLabel(sl, text="Ghidaj text", font=self.font_n)
        self.edit_guid_row_lbl.grid(row=2, column=0, sticky="w")
        self.edit_guid_val = ctk.CTkLabel(sl, text="7.5", font=self.font_n, text_color="#4f8cff")
        self.edit_guid_val.grid(row=2, column=1, sticky="w")
        self.edit_guid = ctk.CTkSlider(sl, from_=1, to=15, number_of_steps=28, width=300,
                                       command=lambda v: self.edit_guid_val.configure(text=f"{v:.1f}"))
        self.edit_guid.set(7.5)
        self.edit_guid.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self.edit_img_guid_row_lbl = ctk.CTkLabel(sl, text="Ghidaj imagine (păstrează structura)",
                                                  font=self.font_n)
        self.edit_img_guid_row_lbl.grid(row=4, column=0, sticky="w")
        self.edit_img_guid_val = ctk.CTkLabel(sl, text="1.5", font=self.font_n, text_color="#4f8cff")
        self.edit_img_guid_val.grid(row=4, column=1, sticky="w")
        self.edit_img_guid = ctk.CTkSlider(sl, from_=1, to=3, number_of_steps=20, width=300,
                                           command=lambda v: self.edit_img_guid_val.configure(text=f"{v:.1f}"))
        self.edit_img_guid.set(1.5)
        self.edit_img_guid.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self.edit_strength_row_lbl = ctk.CTkLabel(sl, text="Intensitate schimbare", font=self.font_n)
        self.edit_strength_row_lbl.grid(row=6, column=0, sticky="w")
        self.edit_strength_val = ctk.CTkLabel(sl, text="0.7", font=self.font_n, text_color="#4f8cff")
        self.edit_strength_val.grid(row=6, column=1, sticky="w")
        self.edit_strength = ctk.CTkSlider(sl, from_=0.05, to=1.0, number_of_steps=19, width=300,
                                           command=lambda v: self.edit_strength_val.configure(text=f"{v:.2f}"))
        self.edit_strength.set(0.7)
        self.edit_strength.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        seed_row = ctk.CTkFrame(left, fg_color="transparent")
        seed_row.grid(row=15, column=0, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(seed_row, text="Semință:", font=self.font_n).pack(side="left")
        self.edit_seed_entry = ctk.CTkEntry(seed_row, width=110, height=28, font=self.font_n,
                                            placeholder_text="aleatorie")
        self.edit_seed_entry.pack(side="left", padx=8)

        self.btn_edit_run = ctk.CTkButton(left, text="✎  Editează imaginea", height=44,
                                          font=self.font_btn, command=self._on_edit)
        self.btn_edit_run.grid(row=16, column=0, sticky="ew", pady=(14, 0))

        # --- dreapta: rezultat
        right = ctk.CTkFrame(tab, fg_color="#1a1a1a", corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(8, 12))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        self.edit_result_label = ctk.CTkLabel(right, text="\n\nRezultatul va apărea aici.",
                                              font=ctk.CTkFont(family="Segoe UI", size=16),
                                              text_color="#7a7a7a", justify="center")
        self.edit_result_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        acts = ctk.CTkFrame(right, fg_color="transparent")
        acts.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.btn_edit_compare = ctk.CTkButton(acts, text="Compară (ține apăsat)", width=160,
                                              height=34, state="disabled",
                                              command=lambda: None)
        self.btn_edit_compare.bind("<ButtonPress-1>", lambda _e: self._edit_show_before(True))
        self.btn_edit_compare.bind("<ButtonRelease-1>", lambda _e: self._edit_show_before(False))
        self.btn_edit_compare.grid(row=0, column=0)
        self.btn_edit_use = ctk.CTkButton(acts, text="Continuă de aici ↻", width=150, height=34,
                                          state="disabled", command=self._edit_use_result)
        self.btn_edit_use.grid(row=0, column=1, padx=(10, 0))
        self.btn_edit_save = ctk.CTkButton(acts, text="Salvează ca…", width=120, height=34,
                                           state="disabled", command=self._save_edit_result)
        self.btn_edit_save.grid(row=0, column=2, padx=(10, 0))

        self._edit_result: Image.Image | None = None
        self._update_edit_ui()

    def _set_edit_mode(self, mode: str):
        self.edit_mode.set(mode)
        self._update_edit_ui()

    def _update_edit_ui(self):
        pix_mode = self.edit_mode.get() == "Instrucțiune"
        if pix_mode:
            self.edit_strength_row_lbl.grid_remove(); self.edit_strength.grid_remove()
            self.edit_strength_val.grid_remove()
            self.edit_img_guid_row_lbl.grid(); self.edit_img_guid.grid()
            self.edit_img_guid_val.grid()
            self.edit_negative.grid_remove()
        else:
            self.edit_img_guid_row_lbl.grid_remove(); self.edit_img_guid.grid_remove()
            self.edit_img_guid_val.grid_remove()
            self.edit_strength_row_lbl.grid(); self.edit_strength.grid()
            self.edit_strength_val.grid()
            self.edit_negative.grid()

    def _edit_add_example(self, text: str):
        cur = self.edit_prompt.get("1.0", "end-1c").strip()
        self.edit_prompt.delete("1.0", "end")
        self.edit_prompt.insert("1.0", (cur + ", " if cur else "") + text)

    def _edit_set_source(self, img: Image.Image):
        self._edit_source = basics.auto_orient(img)
        w, h = basics.fit_size(self._edit_source.width, self._edit_source.height, 330, 240)
        ctk_img = ctk.CTkImage(light_image=self._edit_source, dark_image=self._edit_source,
                               size=(w, h))
        self.edit_src_label.configure(image=ctk_img, text="")
        self._img_refs["edit_src"] = ctk_img
        self.edit_src_info.configure(
            text=f"{self._edit_source.width}×{self._edit_source.height} px")

    def _edit_load_dialog(self):
        path = filedialog.askopenfilename(
            title="Alege imaginea de editat",
            filetypes=[("Imagini", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                       ("Toate fișierele", "*.*")])
        if path:
            try:
                img = basics.load_image(path)
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Nu pot deschide imaginea:\n{e}")
                return
            self._edit_set_source(img)
            self.set_status(f"Încărcată: {os.path.basename(path)}")

    def _edit_paste(self):
        img = basics.paste_from_clipboard()
        if img is None:
            messagebox.showinfo(APP_NAME, "Clipboard-ul nu conține o imagine.")
            return
        self._edit_set_source(img)
        self.set_status("Imagine lipită din clipboard.")

    def _on_edit(self):
        if self.engine is None:
            messagebox.showinfo(APP_NAME, "Motorul AI încă se pornește — mai așteaptă câteva secunde.")
            return
        if self._edit_source is None:
            messagebox.showwarning(APP_NAME, "Încarcă întâi o imagine sursă.")
            return
        repo, err = self._selected_repo("edit")
        if not repo:
            messagebox.showwarning(APP_NAME, err)
            return
        instruction = self.edit_prompt.get("1.0", "end-1c").strip()
        if not instruction:
            messagebox.showwarning(APP_NAME, "Scrie o instrucțiune (ce să se schimbe).")
            return
        mode = self.edit_mode.get()
        model = find_model(repo)
        if mode == "Instrucțiune" and model is not None and not model.pix2pix:
            messagebox.showwarning(
                APP_NAME,
                "Modelul ales nu suportă instrucțiuni.\n"
                "Alege InstructPix2Pix sau comută pe modul „Reimaginare”.")
            return
        negative = self.edit_negative.get().strip()
        steps = int(float(self.edit_steps.get()))
        guidance = float(self.edit_guid.get())
        img_guidance = float(self.edit_img_guid.get())
        strength = float(self.edit_strength.get())
        seed_txt = self.edit_seed_entry.get().strip()
        seed = int(seed_txt) if seed_txt.isdigit() else -1
        variant = model.variant if model else None
        purpose = "edit"

        def progress(frac, msg):
            self._post(lambda: (self.set_progress(frac), self.set_status(msg)))

        def work():
            if not self.mgr.is_installed(repo):
                self._post(lambda: self.set_status(
                    f"Se descarcă modelul {repo} (doar data aceasta)…"))
                if not self._download_blocking(repo, progress):
                    return False, None, f"Descărcarea modelului {repo} a eșuat."
            self._post(lambda: self.set_status("Se încarcă modelul în memorie…"))
            self.engine.load(purpose, repo, variant, progress)
            t0 = time.time()
            if mode == "Instrucțiune":
                result = self.engine.edit_pix2pix(
                    image=self._edit_source, instruction=instruction, steps=steps,
                    image_guidance=img_guidance, guidance=guidance, seed=seed,
                    progress=progress, cancel=self._cancel_event)
            else:
                result = self.engine.edit_img2img(
                    image=self._edit_source, prompt=instruction, negative=negative,
                    strength=strength, steps=steps, guidance=guidance, seed=seed,
                    progress=progress, cancel=self._cancel_event)
            if result is None and self._cancel_event.is_set():
                return False, None, "__CANCELLED__"
            if result is None:
                return False, None, "Modelul nu a returnat niciun rezultat."
            return True, result, f"{time.time() - t0:.1f} s"

        def done(ok, img, msg):
            if not ok:
                if msg == "__CANCELLED__":
                    self.set_status("Editare anulată.")
                    return
                messagebox.showerror(APP_NAME, msg)
                self.set_status("Eroare la editare.")
                return
            self._edit_result = img
            self._edit_show_image(img)
            for b in (self.btn_edit_save, self.btn_edit_use, self.btn_edit_compare):
                b.configure(state="normal")
            if self.settings.get("auto_save", True):
                saved = self._auto_save(img, "edit")
                self.set_status(f"Gata în {msg} · salvat: {os.path.basename(saved)}")
            else:
                self.set_status(f"Gata în {msg}.")

        self._run_task(work, done,
                       busy_widgets=[self.btn_edit_run, self.btn_edit_load, self.btn_edit_save])

    def _edit_show_image(self, img: Image.Image):
        w, h = basics.fit_size(img.width, img.height, *PREVIEW_BOX)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
        self.edit_result_label.configure(image=ctk_img, text="")
        self._img_refs["edit_res"] = ctk_img

    def _edit_show_before(self, before: bool):
        if before and self._edit_source is not None:
            self._edit_show_image(self._edit_source)
        elif self._edit_result is not None:
            self._edit_show_image(self._edit_result)

    def _edit_use_result(self):
        if self._edit_result is not None:
            self._edit_set_source(self._edit_result)
            self.set_status("Rezultatul a devenit imaginea sursă — poți continua editarea.")

    def _save_edit_result(self):
        if self._edit_result is not None:
            self._save_as_dialog(self._edit_result, f"editata_{datetime.now():%Y%m%d_%H%M%S}")

    # ================================================================ tab EDITARE DE BAZĂ
    def _build_basic_tab(self):
        tab = ctk.CTkFrame(self.container, fg_color="transparent")
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.tabs["de_baza"] = tab

        self._basic_img: Image.Image | None = None
        self._basic_undo: list[Image.Image] = []
        self._basic_sel = None          # (x0,y0,x1,y1) în coordonate imagine
        self._basic_scale = 1.0
        self._basic_ox = self._basic_oy = 0
        self._basic_photo = None
        self._basic_drag = None

        left = ctk.CTkScrollableFrame(tab, width=330, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsw", padx=(16, 8), pady=(8, 12))
        left.grid_columnconfigure(0, weight=1)

        def header(text):
            ctk.CTkLabel(left, text=text, font=self.font_h, anchor="w").grid(
                row=left.grid_size()[1], column=0, sticky="w", pady=(12, 4))

        # -- fișier
        header("Imagine")
        self.btn_basic_load = ctk.CTkButton(left, text="Încarcă imagine…", height=32,
                                            font=self.font_n, command=self._basic_load_dialog)
        self.btn_basic_paste = ctk.CTkButton(left, text="Lipire (Ctrl+V)", height=32,
                                             font=self.font_n, command=self._basic_paste)
        self.btn_basic_undo = ctk.CTkButton(left, text="↶ Undo", height=32, width=80,
                                            font=self.font_n, state="disabled",
                                            command=self._basic_undo_op)
        r = left.grid_size()[1]
        self.btn_basic_load.grid(row=r, column=0, sticky="w")
        self.btn_basic_paste.grid(row=r, column=1, padx=(8, 0))
        self.btn_basic_undo.grid(row=r, column=2, padx=(8, 0))

        # -- rotire / oglindire
        header("Rotire și oglindire")
        r = left.grid_size()[1]
        for i, (txt, cmd) in enumerate([
                ("⟲ 90°", lambda: self._basic_rotate(-90)),
                ("90° ⟳", lambda: self._basic_rotate(90)),
                ("180°", lambda: self._basic_rotate(180)),
                ("⇋ orizontal", lambda: self._basic_flip(True)),
                ("⇅ vertical", lambda: self._basic_flip(False))]):
            ctk.CTkButton(left, text=txt, height=32, font=self.font_n, fg_color="#2a2a2a",
                          hover_color="#3a3a3a", command=cmd).grid(
                row=r + i // 3, column=i % 3, sticky="ew", padx=(0, 6), pady=2)

        # -- redimensionare
        header("Redimensionare")
        r = left.grid_size()[1]
        self._basic_w_entry = ctk.CTkEntry(left, width=90, height=30, placeholder_text="lățime")
        self._basic_h_entry = ctk.CTkEntry(left, width=90, height=30, placeholder_text="înălțime")
        self._basic_keep_ratio = ctk.CTkCheckBox(left, text="proporții", font=self.font_small)
        self._basic_keep_ratio.select()
        self._basic_w_entry.grid(row=r, column=0, sticky="w")
        self._basic_h_entry.grid(row=r, column=1, sticky="w", padx=(8, 0))
        self._basic_keep_ratio.grid(row=r, column=2, padx=(8, 0))
        self._basic_w_entry.bind("<KeyRelease>", lambda _e: self._basic_sync_h())
        r = left.grid_size()[1]
        self.btn_basic_resize = ctk.CTkButton(left, text="Aplică redimensionarea", height=32,
                                              font=self.font_n, command=self._basic_resize)
        self.btn_basic_resize.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(6, 0))

        # -- decupare
        header("Decupare")
        r = left.grid_size()[1]
        ctk.CTkLabel(left, text="Trage cu mouse-ul un dreptunghi pe imagine,\n"
                     "apoi apasă butonul.", font=self.font_small, text_color="#8a8a8a",
                     justify="left").grid(row=r, column=0, columnspan=3, sticky="w")
        r = left.grid_size()[1]
        self.btn_basic_crop = ctk.CTkButton(left, text="✂ Decupează selecția", height=32,
                                            font=self.font_n, state="disabled",
                                            command=self._basic_crop)
        self.btn_basic_crop.grid(row=r, column=0, columnspan=3, sticky="ew")

        # -- ajustări
        header("Ajustări (1.0 = nemodificat)")
        self._basic_adj = {}
        r = left.grid_size()[1]
        for i, (key, label) in enumerate([("brightness", "Luminozitate"),
                                          ("contrast", "Contrast"),
                                          ("saturation", "Saturație"),
                                          ("sharpness", "Claritate")]):
            row_i = r + i * 2
            ctk.CTkLabel(left, text=label, font=self.font_n).grid(row=row_i, column=0, sticky="w")
            val = ctk.CTkLabel(left, text="1.00", font=self.font_small, text_color="#4f8cff")
            val.grid(row=row_i, column=2, sticky="e")
            slider = ctk.CTkSlider(left, from_=0.2, to=2.0, number_of_steps=36, width=290,
                                   command=lambda v, k=key, l=val: self._basic_adj_changed(v, k, l))
            slider.set(1.0)
            slider.grid(row=row_i + 1, column=0, columnspan=3, sticky="ew", pady=(0, 4))
            self._basic_adj[key] = (slider, val)
        r = left.grid_size()[1]
        self.btn_basic_adj_reset = ctk.CTkButton(left, text="Resetează ajustările", height=28,
                                                 font=self.font_small, fg_color="#2a2a2a",
                                                 hover_color="#3a3a3a",
                                                 command=self._basic_adj_reset)
        self.btn_basic_adj_reset.grid(row=r, column=0, columnspan=3, sticky="ew")
        self._basic_adj_apply_after = None

        # -- export
        header("Salvare")
        r = left.grid_size()[1]
        self.basic_fmt = ctk.CTkOptionMenu(left, values=["PNG", "JPEG", "WEBP", "BMP"],
                                           height=30, font=self.font_n, width=110,
                                           command=lambda _v: self._basic_quality_visible())
        self.basic_fmt.grid(row=r, column=0, sticky="w")
        self._basic_q_val = ctk.CTkLabel(left, text="calitate 92", font=self.font_small)
        self._basic_q_val.grid(row=r, column=2, sticky="e")
        self.basic_quality = ctk.CTkSlider(left, from_=40, to=100, number_of_steps=60, width=290,
                                           command=lambda v: self._basic_q_val.configure(
                                               text=f"calitate {int(v)}"))
        self.basic_quality.set(92)
        r = left.grid_size()[1]
        self.basic_quality.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(2, 4))
        self._basic_quality_visible_ok = True
        r = left.grid_size()[1]
        self.btn_basic_save = ctk.CTkButton(left, text="💾 Salvează ca…", height=36,
                                            font=self.font_btn, state="disabled",
                                            command=self._basic_save)
        self.btn_basic_save.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self._basic_quality_visible()

        # --- zona de previzualizare (dreapta)
        right = ctk.CTkFrame(tab, fg_color="#1a1a1a", corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(8, 12))
        self.basic_canvas = ctk.CTkCanvas(right, width=760, height=540, bg="#101010",
                                          highlightthickness=0, cursor="tcross")
        self.basic_canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.basic_info = ctk.CTkLabel(right, text="Nicio imagine. Încarcă un fișier sau lipește "
                                       "din clipboard (Ctrl+V).", font=self.font_n,
                                       text_color="#8a8a8a")
        self.basic_info.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        self.basic_canvas.bind("<Button-1>", self._basic_on_press)
        self.basic_canvas.bind("<B1-Motion>", self._basic_on_drag)
        self.basic_canvas.bind("<ButtonRelease-1>", self._basic_on_release)

    # -- bază: încărcare / randare
    def _basic_load_dialog(self):
        path = filedialog.askopenfilename(
            title="Alege imaginea",
            filetypes=[("Imagini", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                       ("Toate fișierele", "*.*")])
        if path:
            try:
                img = basics.auto_orient(basics.load_image(path))
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Nu pot deschide imaginea:\n{e}")
                return
            self._basic_set_image(img)
            self.set_status(f"Încărcată: {os.path.basename(path)}")

    def _basic_paste(self):
        img = basics.paste_from_clipboard()
        if img is None:
            messagebox.showinfo(APP_NAME, "Clipboard-ul nu conține o imagine.")
            return
        self._basic_set_image(basics.auto_orient(img))
        self.set_status("Imagine lipită din clipboard.")

    def _basic_set_image(self, img: Image.Image, clear_undo: bool = True):
        if clear_undo:
            self._basic_undo = []
        self._basic_img = img
        self._basic_sel = None
        self._basic_adj_reset(silent=True)
        self._basic_w_entry.delete(0, "end"); self._basic_w_entry.insert(0, str(img.width))
        self._basic_h_entry.delete(0, "end"); self._basic_h_entry.insert(0, str(img.height))
        self.btn_basic_save.configure(state="normal")
        self._basic_update_undo_btn()
        self._basic_render()

    def _basic_render(self):
        cv = self.basic_canvas
        cv.delete("all")
        img = self._basic_img
        if img is None:
            return
        cw, ch = cv.winfo_width() or 760, cv.winfo_height() or 540
        if cw < 50:
            cw, ch = 760, 540
        disp = self._basic_display_image()
        w, h = basics.fit_size(disp.width, disp.height, cw, ch)
        disp = disp.resize((w, h), Image.LANCZOS) if (w, h) != disp.size else disp
        self._basic_photo = ImageTk.PhotoImage(disp)
        self._basic_ox, self._basic_oy = (cw - w) // 2, (ch - h) // 2
        cv.create_image(self._basic_ox, self._basic_oy, anchor="nw", image=self._basic_photo)
        self._basic_scale = w / disp.width if disp.width else 1.0
        # redesenează selecția existentă
        if self._basic_sel:
            x0, y0, x1, y1 = self._basic_sel
            cv.create_rectangle(self._c2x(x0), self._c2y(y0), self._c2x(x1), self._c2y(y1),
                                outline="#4f8cff", width=2, dash=(6, 4), tags="sel")
        info = f"{disp.width}×{disp.height} px"
        if self._basic_sel:
            sx0, sy0, sx1, sy1 = self._basic_sel
            info += f"  ·  selecție: {abs(sx1-sx0)}×{abs(sy1-sy0)} px"
        self.basic_info.configure(text=info)

    def _basic_display_image(self) -> Image.Image:
        """Imaginea curentă cu ajustările slider-elor aplicate (doar pentru afișare)."""
        img = self._basic_img
        if img is None:
            return Image.new("RGB", (8, 8))
        return basics.enhance_image(
            img,
            brightness=float(self._basic_adj["brightness"][0].get()),
            contrast=float(self._basic_adj["contrast"][0].get()),
            saturation=float(self._basic_adj["saturation"][0].get()),
            sharpness=float(self._basic_adj["sharpness"][0].get()),
        )

    # -- bază: decupare interactivă
    def _x2c(self, x): return x * self._basic_scale + self._basic_ox
    def _y2c(self, y): return y * self._basic_scale + self._basic_oy
    def _c2x(self, cx): return (cx - self._basic_ox) / self._basic_scale
    def _c2y(self, cy): return (cy - self._basic_oy) / self._basic_scale

    def _basic_on_press(self, ev):
        if self._basic_img is None:
            return
        self._basic_drag = (ev.x, ev.y)
        self.basic_canvas.delete("sel")

    def _basic_on_drag(self, ev):
        if self._basic_drag is None:
            return
        x0, y0 = self._basic_drag
        self.basic_canvas.delete("sel")
        self.basic_canvas.create_rectangle(x0, y0, ev.x, ev.y, outline="#4f8cff",
                                           width=2, dash=(6, 4), tags="sel")

    def _basic_on_release(self, ev):
        if self._basic_drag is None or self._basic_img is None:
            return
        x0, y0 = self._basic_drag
        self._basic_drag = None
        ix0, iy0 = self._c2x(x0), self._c2y(y0)
        ix1, iy1 = self._c2x(ev.x), self._c2y(ev.y)
        ix0, ix1 = sorted((int(ix0), int(ix1)))
        iy0, iy1 = sorted((int(iy0), int(iy1)))
        w, h = self._basic_img.size
        ix0, iy0 = max(0, ix0), max(0, iy0)
        ix1, iy1 = min(w, ix1), min(h, iy1)
        if ix1 - ix0 < 8 or iy1 - iy0 < 8:
            self._basic_sel = None
            self.btn_basic_crop.configure(state="disabled")
            self._basic_render()
            return
        self._basic_sel = (ix0, iy0, ix1, iy1)
        self.btn_basic_crop.configure(state="normal")
        self._basic_render()

    # -- bază: operații
    def _basic_commit_adjustments(self) -> bool:
        """Aplică permanent ajustările slider-elor (dacă sunt modificate)."""
        vals = {k: float(s.get()) for k, (s, _l) in self._basic_adj.items()}
        if all(abs(v - 1.0) < 1e-3 for v in vals.values()):
            return False
        self._basic_push_undo()
        self._basic_img = basics.enhance_image(self._basic_img, **vals)
        self._basic_adj_reset(silent=True)
        return True

    def _basic_push_undo(self):
        if self._basic_img is not None:
            self._basic_undo.append(self._basic_img.copy())
            if len(self._basic_undo) > 10:
                self._basic_undo.pop(0)
        self._basic_update_undo_btn()

    def _basic_undo_op(self):
        if self._basic_undo:
            self._basic_img = self._basic_undo.pop()
            self._basic_sel = None
            self._basic_adj_reset(silent=True)
            self._basic_update_undo_btn()
            self._basic_render()
            self.set_status("S-a anulat ultima operație.")

    def _basic_update_undo_btn(self):
        try:
            self.btn_basic_undo.configure(state="normal" if self._basic_undo else "disabled")
        except Exception:
            pass

    def _basic_rotate(self, degrees: int):
        if self._basic_img is None:
            return
        self._basic_commit_adjustments()
        self._basic_push_undo()
        self._basic_img = basics.rotate_image(self._basic_img, degrees)
        self._basic_sel = None
        self.btn_basic_crop.configure(state="disabled")
        self._basic_after_op()

    def _basic_flip(self, horizontal: bool):
        if self._basic_img is None:
            return
        self._basic_commit_adjustments()
        self._basic_push_undo()
        self._basic_img = basics.flip_image(self._basic_img, horizontal)
        self._basic_sel = None
        self._basic_after_op()

    def _basic_sync_h(self):
        if not (self._basic_keep_ratio.get() and self._basic_img):
            return
        txt = self._basic_w_entry.get().strip()
        if txt.isdigit() and int(txt) > 0:
            w, h = self._basic_img.size
            self._basic_h_entry.delete(0, "end")
            self._basic_h_entry.insert(0, str(max(1, round(int(txt) * h / w))))

    def _basic_resize(self):
        if self._basic_img is None:
            messagebox.showinfo(APP_NAME, "Încarcă întâi o imagine.")
            return
        try:
            w = int(self._basic_w_entry.get().strip())
            h = int(self._basic_h_entry.get().strip())
        except ValueError:
            messagebox.showwarning(APP_NAME, "Lățimea și înălțimea trebuie să fie numere.")
            return
        if w < 8 or h < 8:
            messagebox.showwarning(APP_NAME, "Dimensiunile minime sunt 8×8 px.")
            return
        self._basic_commit_adjustments()
        self._basic_push_undo()
        self._basic_img = basics.resize_image(self._basic_img, w, h,
                                              keep_ratio=False)
        self._basic_sel = None
        self._basic_after_op()

    def _basic_crop(self):
        if self._basic_img is None or not self._basic_sel:
            return
        self._basic_commit_adjustments()
        self._basic_push_undo()
        try:
            self._basic_img = basics.crop_image(self._basic_img, self._basic_sel)
        except ValueError as e:
            messagebox.showwarning(APP_NAME, str(e))
            return
        self._basic_sel = None
        self.btn_basic_crop.configure(state="disabled")
        self._basic_after_op()

    def _basic_after_op(self):
        self._basic_w_entry.delete(0, "end"); self._basic_w_entry.insert(0, str(self._basic_img.width))
        self._basic_h_entry.delete(0, "end"); self._basic_h_entry.insert(0, str(self._basic_img.height))
        self._basic_render()
        self.set_status("Operație aplicată.")

    def _basic_adj_changed(self, value, key, val_label):
        val_label.configure(text=f"{value:.2f}")
        if self._basic_adj_apply_after:
            self.after_cancel(self._basic_adj_apply_after)
        self._basic_adj_apply_after = self.after(140, self._basic_render)

    def _basic_adj_reset(self, silent: bool = False):
        for slider, val in self._basic_adj.values():
            slider.set(1.0)
            val.configure(text="1.00")
        if not silent and self._basic_img is not None:
            self._basic_render()

    def _basic_quality_visible(self):
        fmt = self.basic_fmt.get()
        if fmt in ("JPEG", "WEBP"):
            self.basic_quality.grid()
            self._basic_q_val.grid()
        else:
            self.basic_quality.grid_remove()
            self._basic_q_val.grid_remove()

    def _basic_save(self):
        if self._basic_img is None:
            return
        img = self._basic_display_image()
        self._save_as_dialog(img, f"imagine_{datetime.now():%Y%m%d_%H%M%S}",
                             default_fmt=self.basic_fmt.get(),
                             quality=int(self.basic_quality.get()))

    # ================================================================ tab ISTORIC
    def _build_history_tab(self):
        tab = ctk.CTkFrame(self.container, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        self.tabs["istoric"] = tab

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        ctk.CTkLabel(top, text="Istoric", font=self.font_title).pack(side="left")
        self.hist_count_lbl = ctk.CTkLabel(top, text="", font=self.font_n, text_color="#8a8a8a")
        self.hist_count_lbl.pack(side="left", padx=16)
        ctk.CTkButton(top, text="⟳ Reîmprospătează", height=32, font=self.font_n,
                      command=self._refresh_history).pack(side="right", padx=(8, 0))
        ctk.CTkButton(top, text="Deschide folderul", height=32, font=self.font_n,
                      command=lambda: open_path(self.settings["output_dir"])).pack(side="right")

        self.hist_grid = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.hist_grid.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 16))
        for c in range(5):
            self.hist_grid.grid_columnconfigure(c, weight=1)

    def _refresh_history(self):
        for w in self.hist_grid.winfo_children():
            w.destroy()
        self._img_refs.pop("hist", None)
        out = self.settings["output_dir"]
        files = []
        try:
            for name in os.listdir(out):
                if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                    p = os.path.join(out, name)
                    files.append((os.path.getmtime(p), p))
        except Exception:
            pass
        files.sort(reverse=True)
        files = files[:60]
        self.hist_count_lbl.configure(
            text=f"{len(files)} imagini în {out}" + (" (se arată primele 60)" if len(files) == 60 else ""))
        if not files:
            ctk.CTkLabel(self.hist_grid, text="Folderul de ieșire e gol.\n"
                         "Imaginile generate și editate apar aici automat.",
                         font=ctk.CTkFont(family="Segoe UI", size=15), text_color="#7a7a7a",
                         justify="center").grid(row=0, column=0, columnspan=5, pady=40)
            return
        refs = []
        for i, (_mt, path) in enumerate(files):
            try:
                thumb = basics.load_image(path)
            except Exception:
                continue
            w, h = basics.fit_size(thumb.width, thumb.height, 190, 140)
            img = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=(w, h))
            refs.append(img)
            cell = ctk.CTkFrame(self.hist_grid, fg_color="#1a1a1a", corner_radius=10)
            cell.grid(row=i // 5, column=i % 5, padx=6, pady=6, sticky="nsew")
            btn = ctk.CTkButton(cell, image=img, text="", fg_color="transparent",
                                hover_color="#2a2a2a", corner_radius=8,
                                command=lambda p=path: open_path(p))
            btn.pack(padx=6, pady=(6, 2))
            ctk.CTkLabel(cell, text=datetime.fromtimestamp(_mt).strftime("%d.%m.%Y %H:%M"),
                         font=self.font_small, text_color="#8a8a8a").pack(pady=(0, 6))
        self._img_refs["hist"] = refs

    # ================================================================ tab SETĂRI
    def _build_settings_tab(self):
        tab = ctk.CTkFrame(self.container, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)
        self.tabs["setari"] = tab

        ctk.CTkLabel(tab, text="Setări", font=self.font_title).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        # -- dispozitiv + foldere
        top = ctk.CTkFrame(tab, fg_color="#1a1a1a", corner_radius=12)
        top.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Dispozitiv de calcul", font=self.font_h, anchor="w").grid(
            row=0, column=0, sticky="w", padx=14, pady=(10, 2))
        self.device_full_label = ctk.CTkLabel(top, text="…", font=self.font_n,
                                              text_color="#9a9a9a", anchor="w", justify="left")
        self.device_full_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=14)
        self.device_menu = ctk.CTkOptionMenu(
            top, width=240, height=30, font=self.font_n,
            values=["Automat (GPU dacă există)", "CUDA — placa video", "CPU — procesor"],
            command=self._on_device_change)
        self.device_menu.set("Automat (GPU dacă există)")
        self.device_menu.grid(row=0, column=1, sticky="e", padx=14, pady=(10, 4))
        ctk.CTkLabel(top, text="Folderul de ieșire (imaginile salvate automat)", font=self.font_h,
                     anchor="w").grid(row=2, column=0, sticky="w", padx=14, pady=(10, 2))
        self.out_entry = ctk.CTkEntry(top, height=30, font=self.font_n)
        self.out_entry.insert(0, self.settings["output_dir"])
        self.out_entry.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14)
        self.out_entry.bind("<Return>", lambda _e: self._sync_output_entry())
        self.out_entry.bind("<FocusOut>", lambda _e: self._sync_output_entry())
        ctk.CTkButton(top, text="Alege…", width=90, height=28, font=self.font_small,
                      command=self._choose_output_dir).grid(row=3, column=1, sticky="e",
                                                            padx=14, pady=6)
        ctk.CTkButton(top, text="Deschide folderul", width=130, height=28, font=self.font_small,
                      fg_color="#2a2a2a", hover_color="#3a3a3a",
                      command=lambda: open_path(self.settings["output_dir"])).grid(
            row=4, column=1, sticky="e", padx=14, pady=(0, 12))
        self.auto_save_switch = ctk.CTkSwitch(
            top, text="Salvează automat rezultatele în folderul de ieșire",
            font=self.font_n, command=self._save_settings_now)
        if self.settings.get("auto_save", True):
            self.auto_save_switch.select()
        self.auto_save_switch.grid(row=5, column=0, sticky="w", padx=14, pady=(0, 12))

        # -- modele
        ctk.CTkLabel(tab, text="Modele AI (descărcate pe calculatorul tău)", font=self.font_title
                     ).grid(row=2, column=0, sticky="w", padx=16, pady=(12, 4))
        self.models_frame = ctk.CTkScrollableFrame(tab, fg_color="#1a1a1a", corner_radius=12)
        self.models_frame.grid(row=3, column=0, sticky="nsew", padx=16, pady=(4, 16))
        self.models_frame.grid_columnconfigure(0, weight=1)
        self.models_list = ctk.CTkFrame(self.models_frame, fg_color="transparent")
        self.models_list.grid(row=0, column=0, sticky="ew")
        self.models_list.grid_columnconfigure(0, weight=1)
        self._model_row_refs: dict[str, dict] = {}

        # rând „model personalizat”
        custom = ctk.CTkFrame(self.models_frame, fg_color="transparent")
        custom.grid(row=1, column=0, sticky="ew", padx=14, pady=12)
        custom.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(custom, text="Adaugă orice model difuzie de pe Hugging Face:",
                     font=self.font_n, anchor="w").grid(row=0, column=0, sticky="w")
        self.custom_repo_entry = ctk.CTkEntry(custom, placeholder_text="organizatie/model",
                                              height=30, font=self.font_n)
        self.custom_repo_entry.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.custom_repo_btn = ctk.CTkButton(custom, text="Descarcă", width=110, height=30,
                                             font=self.font_n,
                                             command=self._download_custom_model)
        self.custom_repo_btn.grid(row=1, column=1, padx=(8, 0), pady=(4, 0))

    def _on_device_change(self, label: str):
        pref = {"Automat (GPU dacă există)": "auto",
                "CUDA — placa video": "cuda",
                "CPU — procesor": "cpu"}.get(label, "auto")
        self.settings["device_pref"] = pref
        self._save_settings_now()
        if self.engine:
            def work():
                self.engine.set_device_pref(pref)
            threading.Thread(target=work, daemon=True).start()
        self.set_status("Preferința de dispozitiv a fost salvată.")

    def _choose_output_dir(self):
        d = filedialog.askdirectory(title="Alege folderul de ieșire", initialdir=self.settings["output_dir"])
        if d:
            self.settings["output_dir"] = d
            os.makedirs(d, exist_ok=True)
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, d)
            self._save_settings_now()

    def _sync_output_entry(self):
        d = self.out_entry.get().strip()
        if d and os.path.isdir(d) and d != self.settings["output_dir"]:
            self.settings["output_dir"] = d
            self._save_settings_now()
            self.set_status(f"Folderul de ieșire: {d}")

    def _save_settings_now(self):
        self.settings["auto_save"] = bool(self.auto_save_switch.get())
        save_settings(self.settings)

    def _refresh_model_rows(self):
        """(Re)construiește rândurile de modele din Setări."""
        for w in self.models_list.winfo_children():
            w.destroy()
        self._model_row_refs.clear()
        try:
            self.device_full_label.configure(
                text=f"{self.engine.device['name']} · "
                     f"{self.engine.device['vram_gb']:.1f} GB VRAM"
                     if self.engine and self.engine.device["kind"] == "cuda"
                     else (self.engine.device["name"] if self.engine else "…"))
        except Exception:
            pass

        for i, m in enumerate(CATALOG):
            row = ctk.CTkFrame(self.models_list, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", padx=14, pady=8)
            row.grid_columnconfigure(0, weight=1)

            installed = self.mgr.is_installed(m.repo_id)
            purpose_txt = "Generare" if m.purpose == "generate" else "Editare"
            extra = " · instrucțiuni ✎" if m.pix2pix else (" · rapid ⚡" if m.turbo else "")
            name_lbl = ctk.CTkLabel(row, text=f"{m.name}  ·  {purpose_txt}{extra}",
                                    font=self.font_h, anchor="w")
            name_lbl.grid(row=0, column=0, sticky="w")
            status_txt = (f"Instalat · {human_gb(self.mgr.installed_bytes(m.repo_id))}"
                          if installed else f"Neinstalat · ~{m.approx_gb:.1f} GB de descărcat")
            status_lbl = ctk.CTkLabel(row, text=f"{m.repo_id}\n{m.desc}\n{status_txt}",
                                      font=self.font_small, text_color="#8a8a8a",
                                      anchor="w", justify="left")
            status_lbl.grid(row=1, column=0, sticky="w", pady=(2, 6))

            bar = ctk.CTkProgressBar(row, height=8)
            bar.set(0)
            bar.grid_remove()
            btn = ctk.CTkButton(
                row, width=110, height=30, font=self.font_n,
                text="Șterge" if installed else "Descarcă",
                fg_color="#7a2d2d" if installed else None,
                hover_color="#a03d3d" if installed else None,
                command=lambda mm=m: self._model_row_action(mm.repo_id))
            btn.grid(row=0, column=1, rowspan=2, padx=(10, 0))
            self._model_row_refs[m.repo_id] = {"bar": bar, "status": status_lbl,
                                               "btn": btn, "installed": installed}

    def _model_row_action(self, repo_id: str):
        if self.mgr.is_installed(repo_id):
            if self.engine and self.engine.loaded_repo() == repo_id:
                self.engine.unload()
            self.mgr.delete(repo_id)
            self._refresh_model_rows()
            self._refresh_model_dropdowns()
            self._update_first_run_hint()
            self.set_status(f"Modelul {repo_id} a fost șters de pe disc.")
        else:
            self._download_model(repo_id)

    def _download_model(self, repo_id: str):
        if self.mgr.busy:
            messagebox.showinfo(APP_NAME, "Există deja o descărcare în curs — așteaptă să se termine.")
            return
        refs = self._model_row_refs.get(repo_id)
        if refs:
            refs["btn"].configure(state="disabled", text="Se descarcă…")
            refs["bar"].grid()
        self.set_status(f"Se descarcă {repo_id}… (progresul apare în bara de jos)")

        def on_prog(done_b, total_b):
            def upd():
                if refs:
                    if total_b:
                        refs["bar"].set(min(1.0, done_b / total_b))
                        refs["status"].configure(
                            text=f"Se descarcă… {human_gb(done_b)} / {human_gb(total_b)}")
                    else:
                        refs["status"].configure(text=f"Se descarcă… {human_gb(done_b)}")
                if total_b:
                    self.set_progress(min(0.99, done_b / total_b))
                    self.set_status(f"Se descarcă modelul… {human_gb(done_b)} / {human_gb(total_b)}")
            self._post(upd)

        def on_done(ok, err):
            def upd():
                self.set_progress(None)
                self._refresh_model_rows()
                self._refresh_model_dropdowns()
                self._update_first_run_hint()
                if ok:
                    self.set_status(f"Modelul {repo_id} a fost descărcat. Îl poți folosi acum!")
                else:
                    messagebox.showerror(APP_NAME, f"Descărcarea a eșuat:\n{err}")
                    self.set_status("Descărcare eșuată.")
            self._post(upd)

        self.mgr.start_download(repo_id, on_prog, on_done)

    def _download_custom_model(self):
        raw = self.custom_repo_entry.get().strip()
        if not re.fullmatch(r"[\w.\-]+/[\w.\-]+", raw):
            messagebox.showwarning(APP_NAME, "Scrie un ID valid, ex.: stabilityai/sd-turbo")
            return
        m = ModelInfo(repo_id=raw, name=raw.split("/")[-1], purpose="generate", variant=None,
                      approx_gb=0, desc="Model adăugat de tine.")
        if m not in self.custom_models and not find_model(raw):
            self.custom_models.append(m)
        self.custom_repo_entry.delete(0, "end")
        self._refresh_model_dropdowns()
        self._download_model(raw)

    # ================================================================ diverse
    def _save_as_dialog(self, img: Image.Image, suggested: str, default_fmt: str = "PNG",
                        quality: int = 92):
        ext = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "BMP": ".bmp"}[default_fmt]
        path = filedialog.asksaveasfilename(
            title="Salvează imaginea",
            initialfile=suggested + ext,
            defaultextension=ext,
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("WebP", "*.webp"),
                       ("BMP", "*.bmp"), ("Toate", "*.*")])
        if not path:
            return
        fmt = "PNG" if not path.lower().endswith((".jpg", ".jpeg", ".webp", ".bmp")) else (
            "JPEG" if path.lower().endswith((".jpg", ".jpeg")) else
            ("WEBP" if path.lower().endswith(".webp") else "BMP"))
        try:
            saved = basics.save_image(img, path, fmt, quality)
            self.set_status(f"Salvat: {saved}")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Nu am putut salva:\n{e}")

    def _auto_save(self, img: Image.Image, prefix: str, idx: int | None = None) -> str:
        out = self.settings["output_dir"]
        os.makedirs(out, exist_ok=True)
        name = f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}" + (f"_{idx + 1}" if idx is not None else "")
        path = os.path.join(out, name + ".png")
        try:
            basics.save_image(img, path, "PNG")
        except Exception:
            pass
        return path

    def _global_paste(self):
        # lipește în tab-ul activ
        cur = [k for k, f in self.tabs.items() if f.winfo_ismapped()]
        cur = cur[0] if cur else "generare"
        if cur == "editare":
            self._edit_paste()
        elif cur == "de_baza":
            self._basic_paste()

    def _global_action(self):
        cur = [k for k, f in self.tabs.items() if f.winfo_ismapped()]
        cur = cur[0] if cur else "generare"
        if cur == "generare":
            self._on_generate()
        elif cur == "editare":
            self._on_edit()

    def _global_undo(self):
        cur = [k for k, f in self.tabs.items() if f.winfo_ismapped()]
        if cur and cur[0] == "de_baza":
            self._basic_undo_op()

    def _on_close(self):
        save_settings(self.settings)
        self.destroy()


def main():
    app = ArenaEditApp()
    app.mainloop()


if __name__ == "__main__":
    main()
