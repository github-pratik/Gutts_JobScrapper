from __future__ import annotations

"""Tkinter GUI runner for the GUTTS job scraping workflow.

This module provides a desktop interface around `run_gutts_scrape` so users can
configure scrape settings without command-line arguments, run the scrape in a
background thread, and view progress/errors in real time.
"""

import queue
import re
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext
from tkinter import ttk

from jobspy_scrape import (
    GUTTS_DEFAULT_SEARCH,
    GUTTS_DEFAULT_LOCATION,
    GUTTS_SECOND_PASS_SEARCH,
    ScrapeConfig,
    run_gutts_scrape,
)


SITE_CHOICES = [
    ("Indeed", "indeed"),
    ("ZipRecruiter", "zip_recruiter"),
    ("LinkedIn", "linkedin"),
    ("Glassdoor", "glassdoor"),
    ("Google", "google"),
]

COUNTRY_CHOICES = [
    "USA",
    "Canada",
    "UK",
    "India",
    "Australia",
]

MANUAL_FILTER_SITE_SET = {"indeed", "zip_recruiter", "linkedin"}

FAIRFAX_COMBINED_PRIMARY = (
    '("plumbing helper" OR "plumbing apprentice" OR "entry-level plumber" OR "plumber i" '
    'OR "pipe-layer" OR "service plumber" OR "maintenance technician" OR "helper apprentice" '
    'OR "building engineer helper" OR "building engineer apprentice" OR "hvac technician" '
    'OR "hvac tech" OR "hvac helper" OR "hvac apprentice" OR "hvac maintenance" '
    'OR "hvac service" OR "commercial hvac" OR "refrigeration tech" OR "fridge tech") '
    '("new construction" OR "service company" OR "property management" OR maintenance '
    'OR "data center") -software -developer -IT -sales'
)

FAIRFAX_COMBINED_SECONDARY = (
    '("plumbing" OR "plumbing helper" OR "plumbing apprentice" OR "plumber i" OR "service plumber" '
    'OR "hvac" OR "hvac helper" OR "hvac apprentice" OR "hvac service" OR "commercial hvac" '
    'OR "refrigeration tech" OR "building engineer helper" OR "building engineer apprentice") '
    '(apprentice OR helper OR "entry level" OR trainee OR "willing to train") '
    '("new construction" OR "property management" OR "data center") -software -developer -IT'
)

FAIRFAX_PLUMBING_PRIMARY = (
    '("plumbing" OR "plumbing helper" OR "plumbing apprentice" OR "plumber i" '
    'OR "entry-level plumber" OR "pipe-layer" OR "service plumber" '
    'OR "maintenance technician" OR "building engineer helper" OR "building engineer apprentice") '
    '("new construction" OR "service company" OR "property management" OR maintenance '
    'OR "data center") -software -developer -IT'
)

FAIRFAX_HVAC_PRIMARY = (
    '("hvac" OR "hvac technician" OR "hvac tech" OR "hvac helper" OR "hvac apprentice" '
    'OR "hvac maintenance" OR "hvac service" OR "commercial hvac" OR "maintenance technician" '
    'OR "refrigeration tech" OR "fridge tech" OR "building engineer helper" OR "building engineer apprentice") '
    '("new construction" OR "service company" OR "property management" OR maintenance '
    'OR "data center") -software -developer -IT'
)

STRICT_ENTRY_EXCLUSIONS = (
    "-manager -supervisor -director -lead -senior -sr -principal "
    "-foreman -estimator -projectmanager -\"project manager\" -\"service manager\" "
    "-\"operations manager\" -\"maintenance manager\""
)

EMPLOYMENT_TARGET_TERMS: dict[str, str] = {
    "All targets": (
        '("new construction" OR "service company" OR "service technician" OR '
        '"service plumber" OR "hvac service" OR "property management" OR '
        '"maintenance technician" OR "facilities maintenance" OR '
        '"building engineer" OR "data center" OR "critical facilities" OR '
        '"mission critical")'
    ),
    "New Construction": '("new construction" OR "ground-up construction" OR "construction project")',
    "Service Companies": (
        '("service company" OR "service technician" OR "service plumber" OR '
        '"hvac service" OR "field service")'
    ),
    "Property Management / Maintenance": (
        '("property management" OR "maintenance technician" OR '
        '"facilities maintenance" OR "building engineer")'
    ),
    "Data Centers": '("data center" OR "critical facilities" OR "mission critical")',
}


class GuttsRunnerApp:
    def __init__(self, root: tk.Tk) -> None:
        """Initialize window state, Tk variables, widgets, and event polling."""
        self.root = root
        self.root.title("GUTTS Job Scraper Runner")
        self.root.geometry("1080x780")
        self.root.minsize(980, 700)

        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.is_running = False
        self.last_output_dir = str(Path.cwd())
        self.last_error_details = ""

        self._init_vars()
        self._build_ui()
        self._toggle_second_pass()
        self._toggle_advanced_options()
        self._refresh_query_preview()
        self.root.after(100, self._poll_events)

    def _init_vars(self) -> None:
        """Create Tkinter-bound state used by inputs and runtime controls."""
        self.search_preset_var = tk.StringVar(value="GUTTS default")
        self.parameter_preset_var = tk.StringVar(value="Custom")
        self.run_profile_var = tk.StringVar(value="Standard")
        self.employment_target_var = tk.StringVar(value="All targets")
        self.second_pass_var = tk.BooleanVar(value=False)
        self.strict_entry_var = tk.BooleanVar(value=False)
        self.manual_keywords_visible_var = tk.BooleanVar(value=False)
        self.advanced_visible_var = tk.BooleanVar(value=False)
        self.location_var = tk.StringVar(value=GUTTS_DEFAULT_LOCATION)
        self.distance_var = tk.IntVar(value=100)
        self.days_var = tk.IntVar(value=14)
        self.results_var = tk.IntVar(value=50)
        self.country_var = tk.StringVar(value="USA")
        self.output_dir_var = tk.StringVar(value=str(Path.cwd()))
        self.output_file_var = tk.StringVar(value="")
        self.google_override_var = tk.StringVar(value="")
        self.linkedin_fetch_var = tk.BooleanVar(value=False)
        self.verbose_var = tk.IntVar(value=1)
        self.status_var = tk.StringVar(value="Idle")
        self.status_detail_var = tk.StringVar(value="Ready to run a scrape.")
        self.validation_var = tk.StringVar(value="")
        self.progress_var = tk.IntVar(value=0)

        self.site_vars: dict[str, tk.BooleanVar] = {
            value: tk.BooleanVar(value=True) for _, value in SITE_CHOICES
        }

    def _build_ui(self) -> None:
        """Build top-level UI sections in the order users complete them."""
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        self._build_status_frame(outer)
        self._build_main_tabs(outer)
        self._build_actions(outer)
    def _build_status_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Run status")
        frame.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(row1, text="Status:", width=10).pack(side=tk.LEFT)
        ttk.Label(row1, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Label(row1, text="  |  ", padding=(6, 0)).pack(side=tk.LEFT)
        ttk.Label(row1, textvariable=self.status_detail_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress = ttk.Progressbar(
            frame,
            orient=tk.HORIZONTAL,
            mode="determinate",
            maximum=100,
            variable=self.progress_var,
        )
        self.progress.pack(fill=tk.X, padx=10, pady=(0, 6))
        ttk.Label(frame, textvariable=self.validation_var, foreground="#8a5a00").pack(
            anchor="w", padx=10, pady=(0, 8)
        )

    def _build_main_tabs(self, parent: ttk.Frame) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.search_tab = ttk.Frame(self.notebook, padding=10)
        self.scope_tab = ttk.Frame(self.notebook, padding=10)
        self.output_tab = ttk.Frame(self.notebook, padding=10)
        self.advanced_tab = ttk.Frame(self.notebook, padding=10)
        self.logs_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.search_tab, text="1) Search")
        self.notebook.add(self.scope_tab, text="2) Location & Sources")
        self.notebook.add(self.output_tab, text="3) Output")
        self.notebook.add(self.advanced_tab, text="4) Advanced")
        self.notebook.add(self.logs_tab, text="Logs")

        self._build_search_tab(self.search_tab)
        self._build_scope_tab(self.scope_tab)
        self._build_output_tab(self.output_tab)
        self._build_advanced_tab(self.advanced_tab)
        self._build_logs_tab(self.logs_tab)

    def _build_search_tab(self, parent: ttk.Frame) -> None:
        top = ttk.LabelFrame(parent, text="Quick setup")
        top.pack(fill=tk.X, pady=(0, 8))

        row = ttk.Frame(top)
        row.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(row, text="Search preset:").grid(row=0, column=0, sticky="w")
        preset_box = ttk.Combobox(
            row,
            textvariable=self.search_preset_var,
            values=[
                "GUTTS default",
                "Fairfax Entry - Combined",
                "Fairfax Entry - Plumbing",
                "Fairfax Entry - HVAC",
                "Custom",
            ],
            state="readonly",
            width=26,
        )
        preset_box.grid(row=0, column=1, sticky="w", padx=(6, 16))
        preset_box.bind("<<ComboboxSelected>>", self._on_search_preset_changed)

        ttk.Label(row, text="Run profile:").grid(row=0, column=2, sticky="w")
        profile_box = ttk.Combobox(
            row,
            textvariable=self.run_profile_var,
            values=["Fast scan", "Standard", "Deep scan"],
            state="readonly",
            width=14,
        )
        profile_box.grid(row=0, column=3, sticky="w", padx=(6, 16))
        profile_box.bind("<<ComboboxSelected>>", self._on_profile_changed)

        ttk.Checkbutton(
            row,
            text="Second pass (merge + dedupe)",
            variable=self.second_pass_var,
            command=self._toggle_second_pass,
        ).grid(row=0, column=4, sticky="w")
        ttk.Checkbutton(
            row,
            text="Entry-level only (strict)",
            variable=self.strict_entry_var,
            command=self._refresh_query_preview,
        ).grid(row=0, column=5, sticky="w", padx=(12, 0))
        ttk.Label(row, text="Employment target:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        target_box = ttk.Combobox(
            row,
            textvariable=self.employment_target_var,
            values=list(EMPLOYMENT_TARGET_TERMS.keys()),
            state="readonly",
            width=33,
        )
        target_box.grid(row=1, column=1, columnspan=2, sticky="w", padx=(6, 0), pady=(8, 0))
        target_box.bind("<<ComboboxSelected>>", self._on_employment_target_changed)
        ttk.Label(
            row,
            text="Adds target company-type terms automatically.",
        ).grid(row=1, column=3, columnspan=3, sticky="w", padx=(12, 0), pady=(8, 0))

        ttk.Label(
            top,
            text="Flow: pick Search preset + Employment target, then run. Open manual editor only when needed.",
        ).pack(anchor="w", padx=8, pady=(0, 8))

        editor_toggle_row = ttk.Frame(parent)
        editor_toggle_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(
            editor_toggle_row,
            text="Show manual keyword editor",
            variable=self.manual_keywords_visible_var,
            command=self._toggle_manual_keyword_editor,
        ).pack(side=tk.LEFT)
        ttk.Label(
            editor_toggle_row,
            text="(Most users can keep this off and use presets.)",
        ).pack(side=tk.LEFT, padx=(10, 0))

        self.manual_keywords_frame = ttk.LabelFrame(parent, text="Manual keyword editor")
        self.manual_keywords_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        ttk.Label(
            self.manual_keywords_frame,
            text="Primary keywords are used across selected job boards.",
        ).pack(anchor="w", padx=8, pady=(8, 2))
        self.primary_text = tk.Text(self.manual_keywords_frame, height=4, wrap=tk.WORD)
        self.primary_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        self.primary_text.insert("1.0", GUTTS_DEFAULT_SEARCH)
        self.primary_text.bind("<KeyRelease>", self._on_keyword_text_changed)

        ttk.Label(self.manual_keywords_frame, text="Second pass keywords (optional):").pack(
            anchor="w", padx=8
        )
        self.second_text = tk.Text(self.manual_keywords_frame, height=3, wrap=tk.WORD)
        self.second_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.second_text.insert("1.0", GUTTS_SECOND_PASS_SEARCH)
        self.second_text.bind("<KeyRelease>", self._on_keyword_text_changed)

        preview = ttk.LabelFrame(parent, text="Effective query preview")
        preview.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        ttk.Label(
            preview,
            text="Shows final keywords after Employment target and Entry-level strict filters.",
        ).pack(anchor="w", padx=8, pady=(8, 4))
        self.query_preview_box = scrolledtext.ScrolledText(
            preview,
            height=10,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.query_preview_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self._toggle_manual_keyword_editor()

    def _build_scope_tab(self, parent: ttk.Frame) -> None:
        where = ttk.LabelFrame(parent, text="Where to search")
        where.pack(fill=tk.X, pady=(0, 8))

        preset_row = ttk.Frame(where)
        preset_row.pack(fill=tk.X, padx=8, pady=(8, 0))
        ttk.Label(preset_row, text="Parameters preset:").grid(row=0, column=0, sticky="w")
        param_box = ttk.Combobox(
            preset_row,
            textvariable=self.parameter_preset_var,
            values=[
                "Custom",
                "Fairfax Entry - Standard",
                "Fairfax Entry - Deep",
                "DMV Entry - Broad",
            ],
            state="readonly",
            width=24,
        )
        param_box.grid(row=0, column=1, sticky="w", padx=(6, 10))
        param_box.bind("<<ComboboxSelected>>", self._on_parameter_preset_changed)
        ttk.Label(
            preset_row,
            text="Applies location, radius, recency, result count, and board selection.",
        ).grid(row=0, column=2, sticky="w")

        row = ttk.Frame(where)
        row.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(row, text="Search center:").grid(row=0, column=0, sticky="w")
        ttk.Entry(row, textvariable=self.location_var, width=30).grid(
            row=0, column=1, sticky="w", padx=(6, 16)
        )
        ttk.Label(row, text="Radius (miles):").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(row, from_=1, to=500, textvariable=self.distance_var, width=8).grid(
            row=0, column=3, sticky="w", padx=(6, 16)
        )
        ttk.Label(row, text="Country:").grid(row=0, column=4, sticky="w")
        ttk.Combobox(
            row, textvariable=self.country_var, values=COUNTRY_CHOICES, state="readonly", width=12
        ).grid(row=0, column=5, sticky="w", padx=(6, 0))

        scope = ttk.LabelFrame(parent, text="How many and how fresh")
        scope.pack(fill=tk.X, pady=(0, 8))
        scope_row = ttk.Frame(scope)
        scope_row.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(scope_row, text="Results per site:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(scope_row, from_=1, to=1000, textvariable=self.results_var, width=8).grid(
            row=0, column=1, sticky="w", padx=(6, 16)
        )
        ttk.Label(scope_row, text="Job age (days):").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(scope_row, from_=1, to=90, textvariable=self.days_var, width=8).grid(
            row=0, column=3, sticky="w", padx=(6, 8)
        )
        ttk.Label(scope_row, text="(Only jobs posted in last N days)").grid(
            row=0, column=4, sticky="w"
        )

        sites = ttk.LabelFrame(parent, text="Job boards")
        sites.pack(fill=tk.X)
        sites_row = ttk.Frame(sites)
        sites_row.pack(fill=tk.X, padx=8, pady=8)
        for idx, (label, value) in enumerate(SITE_CHOICES):
            ttk.Checkbutton(sites_row, text=label, variable=self.site_vars[value]).grid(
                row=0, column=idx, sticky="w", padx=(0, 14)
            )

    def _build_output_tab(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Output settings")
        frame.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Label(row1, text="Output folder:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.output_dir_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6)
        )
        ttk.Button(row1, text="Browse...", command=self._choose_output_dir).pack(side=tk.LEFT)

        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(row2, text="Output file name (optional):").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.output_file_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 8)
        )
        ttk.Label(row2, text="Leave blank for timestamped file").pack(side=tk.LEFT)

        ttk.Label(
            parent,
            text="Use 'Open output folder' after a run to quickly view CSV results.",
        ).pack(anchor="w", padx=2)

    def _build_advanced_tab(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(
            row,
            text="Show advanced options",
            variable=self.advanced_visible_var,
            command=self._toggle_advanced_options,
        ).pack(side=tk.LEFT)
        ttk.Label(
            row,
            text="(Keep hidden for simpler day-to-day usage)",
        ).pack(side=tk.LEFT, padx=(10, 0))

        self.advanced_options_frame = ttk.LabelFrame(parent, text="Advanced options")
        self.advanced_options_frame.pack(fill=tk.X)

        row1 = ttk.Frame(self.advanced_options_frame)
        row1.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(row1, text="Google Jobs query override (optional):").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.google_override_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0)
        )

        row2 = ttk.Frame(self.advanced_options_frame)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Checkbutton(
            row2,
            text="LinkedIn: fetch full descriptions (slower)",
            variable=self.linkedin_fetch_var,
        ).pack(side=tk.LEFT)
        ttk.Label(row2, text="Verbose level:").pack(side=tk.LEFT, padx=(20, 6))
        ttk.Combobox(
            row2,
            textvariable=self.verbose_var,
            values=[0, 1, 2],
            state="readonly",
            width=4,
        ).pack(side=tk.LEFT)

    def _build_logs_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Runtime logs").pack(anchor="w", pady=(0, 4))
        self.log_box = scrolledtext.ScrolledText(parent, height=14, wrap=tk.WORD, state=tk.DISABLED)
        self.log_box.pack(fill=tk.BOTH, expand=True)

    def _build_actions(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 6))
        self.run_btn = ttk.Button(row, text="Run scrape", command=self._on_run)
        self.run_btn.pack(side=tk.LEFT)
        self.open_btn = ttk.Button(row, text="Open output folder", command=self._open_output_dir)
        self.open_btn.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            row,
            text="Show last error details",
            command=self._show_last_error_details,
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _on_search_preset_changed(self, _: object = None) -> None:
        preset = self.search_preset_var.get()
        if preset == "Custom":
            return
        if preset == "GUTTS default":
            self._set_text(self.primary_text, GUTTS_DEFAULT_SEARCH)
            self._set_text(self.second_text, GUTTS_SECOND_PASS_SEARCH)
            self.location_var.set(GUTTS_DEFAULT_LOCATION)
            self.distance_var.set(100)
            self.days_var.set(14)
            self.results_var.set(50)
            self.strict_entry_var.set(False)
            self.employment_target_var.set("All targets")
            self.parameter_preset_var.set("Custom")
            for site_key, site_flag in self.site_vars.items():
                site_flag.set(True)
        elif preset == "Fairfax Entry - Combined":
            self._set_text(self.primary_text, FAIRFAX_COMBINED_PRIMARY)
            self._set_text(self.second_text, FAIRFAX_COMBINED_SECONDARY)
            self.location_var.set("Fairfax, VA")
            self.distance_var.set(50)
            self.days_var.set(14)
            self.results_var.set(75)
            self.second_pass_var.set(True)
            self.strict_entry_var.set(True)
            self.employment_target_var.set("All targets")
            self.parameter_preset_var.set("Fairfax Entry - Standard")
            for site_key, site_flag in self.site_vars.items():
                site_flag.set(site_key in MANUAL_FILTER_SITE_SET)
        elif preset == "Fairfax Entry - Plumbing":
            self._set_text(self.primary_text, FAIRFAX_PLUMBING_PRIMARY)
            self._set_text(self.second_text, FAIRFAX_COMBINED_SECONDARY)
            self.location_var.set("Fairfax, VA")
            self.distance_var.set(50)
            self.days_var.set(14)
            self.results_var.set(60)
            self.second_pass_var.set(True)
            self.strict_entry_var.set(True)
            self.employment_target_var.set("All targets")
            self.parameter_preset_var.set("Fairfax Entry - Standard")
            for site_key, site_flag in self.site_vars.items():
                site_flag.set(site_key in MANUAL_FILTER_SITE_SET)
        elif preset == "Fairfax Entry - HVAC":
            self._set_text(self.primary_text, FAIRFAX_HVAC_PRIMARY)
            self._set_text(self.second_text, FAIRFAX_COMBINED_SECONDARY)
            self.location_var.set("Fairfax, VA")
            self.distance_var.set(50)
            self.days_var.set(14)
            self.results_var.set(60)
            self.second_pass_var.set(True)
            self.strict_entry_var.set(True)
            self.employment_target_var.set("All targets")
            self.parameter_preset_var.set("Fairfax Entry - Standard")
            for site_key, site_flag in self.site_vars.items():
                site_flag.set(site_key in MANUAL_FILTER_SITE_SET)
        self._toggle_second_pass()
        self._refresh_query_preview()
        self.validation_var.set("")

    def _set_site_selection(self, selected_sites: set[str]) -> None:
        for site_key, site_flag in self.site_vars.items():
            site_flag.set(site_key in selected_sites)

    def _on_parameter_preset_changed(self, _: object = None) -> None:
        preset = self.parameter_preset_var.get()
        if preset == "Custom":
            return
        if preset == "Fairfax Entry - Standard":
            self.location_var.set("Fairfax, VA")
            self.distance_var.set(50)
            self.days_var.set(14)
            self.results_var.set(60)
            self.second_pass_var.set(True)
            self.strict_entry_var.set(True)
            self.employment_target_var.set("All targets")
            self._set_site_selection(MANUAL_FILTER_SITE_SET)
            self.run_profile_var.set("Standard")
        elif preset == "Fairfax Entry - Deep":
            self.location_var.set("Fairfax, VA")
            self.distance_var.set(50)
            self.days_var.set(30)
            self.results_var.set(100)
            self.second_pass_var.set(True)
            self.strict_entry_var.set(True)
            self.employment_target_var.set("All targets")
            self._set_site_selection(MANUAL_FILTER_SITE_SET)
            self.run_profile_var.set("Deep scan")
        elif preset == "DMV Entry - Broad":
            self.location_var.set("Washington, DC")
            self.distance_var.set(75)
            self.days_var.set(21)
            self.results_var.set(80)
            self.second_pass_var.set(True)
            self.strict_entry_var.set(True)
            self.employment_target_var.set("All targets")
            self._set_site_selection(set(self.site_vars.keys()))
            self.run_profile_var.set("Standard")
        self._toggle_second_pass()
        self._refresh_query_preview()
        self.validation_var.set("")

    def _on_employment_target_changed(self, _: object = None) -> None:
        self._refresh_query_preview()

    def _on_keyword_text_changed(self, _: object = None) -> None:
        self.search_preset_var.set("Custom")
        self._refresh_query_preview()

    def _on_profile_changed(self, _: object = None) -> None:
        profile = self.run_profile_var.get()
        if profile == "Fast scan":
            self.results_var.set(25)
            self.days_var.set(7)
            self.second_pass_var.set(False)
        elif profile == "Deep scan":
            self.results_var.set(100)
            self.days_var.set(30)
            self.second_pass_var.set(True)
        else:
            self.results_var.set(50)
            self.days_var.set(14)
        self._toggle_second_pass()
        self.validation_var.set("")

    def _toggle_second_pass(self) -> None:
        """Enable/disable second-pass keywords based on checkbox state."""
        state = tk.NORMAL if self.second_pass_var.get() else tk.DISABLED
        self.second_text.configure(state=state)
        self._refresh_query_preview()

    def _toggle_manual_keyword_editor(self) -> None:
        if not hasattr(self, "manual_keywords_frame"):
            return
        if self.manual_keywords_visible_var.get():
            self.manual_keywords_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        else:
            self.manual_keywords_frame.pack_forget()

    def _toggle_advanced_options(self) -> None:
        if self.advanced_visible_var.get():
            self.advanced_options_frame.pack(fill=tk.X)
        else:
            self.advanced_options_frame.pack_forget()

    def _choose_output_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(Path.cwd()))
        if chosen:
            self.output_dir_var.set(chosen)

    def _open_output_dir(self) -> None:
        """Open output folder in Explorer, creating it first if needed."""
        try:
            out = Path(self.output_dir_var.get()).expanduser().resolve()
            out.mkdir(parents=True, exist_ok=True)
            self.last_output_dir = str(out)
            import os

            os.startfile(str(out))
        except Exception as exc:  # pragma: no cover - GUI path
            messagebox.showerror("Open folder failed", str(exc))

    def _get_text(self, widget: tk.Text) -> str:
        return widget.get("1.0", tk.END).strip()

    def _set_text(self, widget: tk.Text, text: str) -> None:
        current_state = str(widget["state"])
        if current_state == tk.DISABLED:
            widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        if current_state == tk.DISABLED:
            widget.configure(state=tk.DISABLED)
        self._refresh_query_preview()

    def _append_log(self, message: str) -> None:
        """Append one line to the read-only log area and auto-scroll."""
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def _set_status(self, status: str, detail: str, progress: int | None = None) -> None:
        self.status_var.set(status)
        self.status_detail_var.set(detail)
        if progress is not None:
            self.progress_var.set(max(0, min(100, progress)))

    def _update_progress_from_log(self, message: str) -> None:
        lowered = message.lower()
        if "output file" in lowered:
            self._set_status("Running", "Preparing output path...", 15)
            return
        if "pass" in lowered:
            match = re.search(r"pass\s+(\d+)/(\d+)", lowered)
            if match:
                current = int(match.group(1))
                total = max(1, int(match.group(2)))
                percent = 20 + int((current / total) * 55)
                self._set_status("Running", f"Scraping pass {current} of {total}...", percent)
            return
        if "found " in lowered and "jobs" in lowered:
            self._set_status("Running", "Finalizing and writing CSV...", 85)

    def _show_last_error_details(self) -> None:
        if not self.last_error_details:
            messagebox.showinfo("No error details", "No error details are available yet.")
            return
        detail_window = tk.Toplevel(self.root)
        detail_window.title("Last error details")
        detail_window.geometry("900x500")
        detail_window.minsize(760, 380)
        box = scrolledtext.ScrolledText(detail_window, wrap=tk.WORD)
        box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        box.insert("1.0", self.last_error_details)
        box.configure(state=tk.DISABLED)

    def _selected_sites(self) -> list[str]:
        """Return currently selected board identifiers for the scrape request."""
        return [site for site, flag in self.site_vars.items() if flag.get()]

    def _apply_strict_entry_filter(self, term: str) -> str:
        """Append strong exclusions to reduce senior/non-entry role matches."""
        if not self.strict_entry_var.get():
            return term
        compact = term.lower()
        if "-manager" in compact and "-senior" in compact:
            return term
        return f"{term} {STRICT_ENTRY_EXCLUSIONS}".strip()

    def _apply_employment_target_filter(self, term: str) -> str:
        """Append company-target terms selected by user."""
        selected_target = self.employment_target_var.get().strip()
        target_terms = EMPLOYMENT_TARGET_TERMS.get(selected_target)
        if not target_terms:
            return term
        lowered = term.lower()
        if "data center" in lowered and "property management" in lowered and selected_target == "All targets":
            return term
        return f"{term} {target_terms}".strip()

    def _compose_effective_terms(self) -> tuple[str, str]:
        primary_term = self._get_text(self.primary_text)
        second_term = self._get_text(self.second_text)
        primary_term = self._apply_employment_target_filter(primary_term)
        second_term = self._apply_employment_target_filter(second_term)
        primary_term = self._apply_strict_entry_filter(primary_term)
        second_term = self._apply_strict_entry_filter(second_term)
        return primary_term, second_term

    def _refresh_query_preview(self) -> None:
        if not hasattr(self, "query_preview_box"):
            return
        primary_term, second_term = self._compose_effective_terms()
        lines = [
            "Primary (effective):",
            primary_term or "(empty)",
            "",
            "Second pass (effective):",
            second_term or "(empty)",
        ]
        if not self.second_pass_var.get():
            lines.extend(
                [
                    "",
                    "Note: Second pass is currently disabled.",
                ]
            )
        self.query_preview_box.configure(state=tk.NORMAL)
        self.query_preview_box.delete("1.0", tk.END)
        self.query_preview_box.insert("1.0", "\n".join(lines))
        self.query_preview_box.configure(state=tk.DISABLED)

    def _fail_validation(self, title: str, message: str) -> bool:
        self.validation_var.set(message)
        self._set_status("Needs input", message, self.progress_var.get())
        messagebox.showwarning(title, message)
        return False

    def _validate(self) -> bool:
        """Run pre-flight checks and show user-facing warnings for invalid input."""
        if self.is_running:
            return False
        if not self._selected_sites():
            return self._fail_validation("Missing sites", "Select at least one job board.")
        if not self._get_text(self.primary_text):
            return self._fail_validation(
                "Missing keywords",
                "Primary keywords cannot be empty. Add at least one keyword group.",
            )
        if self.second_pass_var.get() and not self._get_text(self.second_text):
            return self._fail_validation(
                "Missing second pass",
                "Second pass is enabled, so provide second-pass keywords.",
            )
        if self.days_var.get() <= 0:
            return self._fail_validation("Invalid age", "Job age (days) must be at least 1.")
        if self.results_var.get() <= 0:
            return self._fail_validation("Invalid count", "Results per site must be at least 1.")
        self.validation_var.set("")
        return True

    def _build_config(self) -> ScrapeConfig:
        """Translate current UI values into a `ScrapeConfig` object."""
        google_override = self.google_override_var.get().strip()
        output_file = self.output_file_var.get().strip()
        primary_term, second_term = self._compose_effective_terms()
        return ScrapeConfig(
            search_term=primary_term,
            second_pass_search=second_term,
            location=self.location_var.get().strip(),
            distance=int(self.distance_var.get()),
            sites=self._selected_sites(),
            results_wanted=int(self.results_var.get()),
            multi_query=bool(self.second_pass_var.get()),
            hours_old=int(self.days_var.get()) * 24,
            country_indeed=self.country_var.get().strip(),
            google_search_term=google_override if google_override else None,
            output=output_file if output_file else None,
            output_dir=self.output_dir_var.get().strip() or ".",
            linkedin_fetch_description=bool(self.linkedin_fetch_var.get()),
            verbose=int(self.verbose_var.get()),
        )

    def _on_run(self) -> None:
        """Start scrape on a background thread to keep the GUI responsive."""
        self.validation_var.set("")
        if not self._validate():
            return
        config = self._build_config()
        self.is_running = True
        self.run_btn.configure(state=tk.DISABLED)
        self.last_error_details = ""
        self._set_status("Running", "Starting scrape...", 10)
        self._append_log("Starting scrape...")

        def worker() -> None:
            # Worker thread does all network/data work and reports events back to
            # the main Tk thread through `event_queue` (Tk widgets are not thread-safe).
            try:
                out_path, row_count = run_gutts_scrape(
                    config=config,
                    log=lambda msg: self.event_queue.put(("log", str(msg))),
                )
                self.event_queue.put(("done", (str(out_path), row_count)))
            except Exception:
                self.event_queue.put(("error", traceback.format_exc()))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _poll_events(self) -> None:
        """Process queued worker events on the Tk thread and update UI safely."""
        while True:
            try:
                event, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event == "log":
                msg = str(payload)
                self._append_log(msg)
                self._update_progress_from_log(msg)
            elif event == "done":
                out_path, row_count = payload
                self.is_running = False
                self.run_btn.configure(state=tk.NORMAL)
                self.last_output_dir = str(Path(out_path).parent)
                self._set_status("Success", f"Saved {row_count} jobs.", 100)
                self.validation_var.set("")
                messagebox.showinfo(
                    "Scrape complete",
                    f"Saved {row_count} jobs to:\n{out_path}",
                )
            elif event == "error":
                self.is_running = False
                self.run_btn.configure(state=tk.NORMAL)
                self.last_error_details = str(payload)
                self._append_log("ERROR:\n" + self.last_error_details)
                self._set_status("Failed", "Scrape failed. See logs or open last error details.", 100)
                messagebox.showerror(
                    "Scrape failed",
                    "Scrape failed.\n\nUse 'Show last error details' for traceback info.",
                )

        self.root.after(100, self._poll_events)


def main() -> None:
    """Application entrypoint used by Python and by the packaged EXE."""
    root = tk.Tk()
    app = GuttsRunnerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
