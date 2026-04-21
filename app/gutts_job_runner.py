from __future__ import annotations

"""Tkinter GUI runner for the GUTTS job scraping workflow.

This module provides a desktop interface around `run_gutts_scrape` so users can
configure scrape settings without command-line arguments, run the scrape in a
background thread, and view progress/errors in real time.
"""

import queue
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


class GuttsRunnerApp:
    def __init__(self, root: tk.Tk) -> None:
        """Initialize window state, Tk variables, widgets, and event polling."""
        self.root = root
        self.root.title("GUTTS Job Scraper Runner")
        self.root.geometry("980x760")
        self.root.minsize(900, 650)

        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.is_running = False
        self.last_output_dir = str(Path.cwd())

        self._init_vars()
        self._build_ui()
        self._toggle_second_pass()
        self.root.after(100, self._poll_events)

    def _init_vars(self) -> None:
        """Create Tkinter-bound state used by inputs and runtime controls."""
        self.preset_var = tk.StringVar(value="GUTTS default")
        self.second_pass_var = tk.BooleanVar(value=False)
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

        self.site_vars: dict[str, tk.BooleanVar] = {
            value: tk.BooleanVar(value=True) for _, value in SITE_CHOICES
        }

    def _build_ui(self) -> None:
        """Build top-level UI sections in the order users complete them."""
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        self._build_job_frame(outer)
        self._build_location_frame(outer)
        self._build_scope_frame(outer)
        self._build_sites_frame(outer)
        self._build_output_frame(outer)
        self._build_advanced_frame(outer)
        self._build_actions(outer)
        self._build_logs(outer)

    def _build_job_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Job & keywords")
        frame.pack(fill=tk.X, pady=(0, 8))

        row0 = ttk.Frame(frame)
        row0.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(row0, text="Preset:").pack(side=tk.LEFT)
        preset_box = ttk.Combobox(
            row0,
            textvariable=self.preset_var,
            values=["GUTTS default", "Custom"],
            state="readonly",
            width=18,
        )
        preset_box.pack(side=tk.LEFT, padx=(6, 12))
        preset_box.bind("<<ComboboxSelected>>", self._on_preset_changed)
        ttk.Label(
            row0,
            text="Search keywords match job title and posting text on most boards.",
        ).pack(side=tk.LEFT)

        ttk.Label(frame, text="Primary keywords:").pack(anchor="w", padx=8)
        self.primary_text = tk.Text(frame, height=4, wrap=tk.WORD)
        self.primary_text.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.primary_text.insert("1.0", GUTTS_DEFAULT_SEARCH)

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Checkbutton(
            row1,
            text="Run second search pass (merge + dedupe)",
            variable=self.second_pass_var,
            command=self._toggle_second_pass,
        ).pack(side=tk.LEFT)

        ttk.Label(frame, text="Second pass keywords:").pack(anchor="w", padx=8)
        self.second_text = tk.Text(frame, height=3, wrap=tk.WORD)
        self.second_text.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.second_text.insert("1.0", GUTTS_SECOND_PASS_SEARCH)

    def _build_location_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Where")
        frame.pack(fill=tk.X, pady=(0, 8))

        row = ttk.Frame(frame)
        row.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(row, text="Search center:").grid(row=0, column=0, sticky="w")
        ttk.Entry(row, textvariable=self.location_var, width=34).grid(
            row=0, column=1, sticky="w", padx=(6, 16)
        )

        ttk.Label(row, text="Radius (miles):").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(row, from_=1, to=500, textvariable=self.distance_var, width=8).grid(
            row=0, column=3, sticky="w", padx=(6, 16)
        )

        ttk.Label(row, text="Country (Indeed/Glassdoor):").grid(
            row=0, column=4, sticky="w"
        )
        ttk.Combobox(
            row,
            textvariable=self.country_var,
            values=COUNTRY_CHOICES,
            width=12,
        ).grid(row=0, column=5, sticky="w", padx=(6, 0))

    def _build_scope_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="How many & how fresh")
        frame.pack(fill=tk.X, pady=(0, 8))
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(row, text="Results per site:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(row, from_=1, to=1000, textvariable=self.results_var, width=8).grid(
            row=0, column=1, sticky="w", padx=(6, 16)
        )

        ttk.Label(row, text="Job age (days):").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(row, from_=1, to=90, textvariable=self.days_var, width=8).grid(
            row=0, column=3, sticky="w", padx=(6, 8)
        )
        ttk.Label(row, text="(Only jobs posted in the last N days)").grid(
            row=0, column=4, sticky="w"
        )

    def _build_sites_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Boards")
        frame.pack(fill=tk.X, pady=(0, 8))
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, padx=8, pady=8)

        for idx, (label, value) in enumerate(SITE_CHOICES):
            ttk.Checkbutton(row, text=label, variable=self.site_vars[value]).grid(
                row=0, column=idx, sticky="w", padx=(0, 14)
            )

    def _build_output_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Output")
        frame.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(row1, text="Output folder:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.output_dir_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6)
        )
        ttk.Button(row1, text="Browse...", command=self._choose_output_dir).pack(side=tk.LEFT)

        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(row2, text="File name (optional):").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.output_file_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 8)
        )
        ttk.Label(
            row2,
            text="Leave blank for auto timestamped file.",
        ).pack(side=tk.LEFT)

    def _build_advanced_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Advanced")
        frame.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(row1, text="Google Jobs search override (optional):").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.google_override_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0)
        )

        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Checkbutton(
            row2,
            text="LinkedIn: fetch full job descriptions (slower)",
            variable=self.linkedin_fetch_var,
        ).pack(side=tk.LEFT)
        ttk.Label(row2, text="Verbose:").pack(side=tk.LEFT, padx=(20, 6))
        ttk.Combobox(
            row2,
            textvariable=self.verbose_var,
            values=[0, 1, 2],
            width=4,
            state="readonly",
        ).pack(side=tk.LEFT)

    def _build_actions(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(0, 6))
        self.run_btn = ttk.Button(row, text="Run scrape", command=self._on_run)
        self.run_btn.pack(side=tk.LEFT)
        self.open_btn = ttk.Button(row, text="Open output folder", command=self._open_output_dir)
        self.open_btn.pack(side=tk.LEFT, padx=(8, 0))

    def _build_logs(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Log")
        frame.pack(fill=tk.BOTH, expand=True)
        self.log_box = scrolledtext.ScrolledText(frame, height=14, wrap=tk.WORD, state=tk.DISABLED)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _on_preset_changed(self, _: object = None) -> None:
        if self.preset_var.get() != "GUTTS default":
            return
        self._set_text(self.primary_text, GUTTS_DEFAULT_SEARCH)
        self._set_text(self.second_text, GUTTS_SECOND_PASS_SEARCH)
        self.location_var.set(GUTTS_DEFAULT_LOCATION)
        self.distance_var.set(100)
        self.days_var.set(14)
        self.results_var.set(50)

    def _toggle_second_pass(self) -> None:
        """Enable/disable second-pass keywords based on checkbox state."""
        state = tk.NORMAL if self.second_pass_var.get() else tk.DISABLED
        self.second_text.configure(state=state)

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

    def _append_log(self, message: str) -> None:
        """Append one line to the read-only log area and auto-scroll."""
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def _selected_sites(self) -> list[str]:
        """Return currently selected board identifiers for the scrape request."""
        return [site for site, flag in self.site_vars.items() if flag.get()]

    def _validate(self) -> bool:
        """Run pre-flight checks and show user-facing warnings for invalid input."""
        if self.is_running:
            return False
        if not self._selected_sites():
            messagebox.showwarning("Missing sites", "Select at least one job board.")
            return False
        if not self._get_text(self.primary_text):
            messagebox.showwarning("Missing keywords", "Primary keywords cannot be empty.")
            return False
        if self.second_pass_var.get() and not self._get_text(self.second_text):
            messagebox.showwarning("Missing second pass", "Second pass keywords cannot be empty.")
            return False
        if self.days_var.get() <= 0:
            messagebox.showwarning("Invalid age", "Job age (days) must be at least 1.")
            return False
        if self.results_var.get() <= 0:
            messagebox.showwarning("Invalid count", "Results per site must be at least 1.")
            return False
        return True

    def _build_config(self) -> ScrapeConfig:
        """Translate current UI values into a `ScrapeConfig` object."""
        google_override = self.google_override_var.get().strip()
        output_file = self.output_file_var.get().strip()
        return ScrapeConfig(
            search_term=self._get_text(self.primary_text),
            second_pass_search=self._get_text(self.second_text),
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
        if not self._validate():
            return
        config = self._build_config()
        self.is_running = True
        self.run_btn.configure(state=tk.DISABLED)
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
                self._append_log(str(payload))
            elif event == "done":
                out_path, row_count = payload
                self.is_running = False
                self.run_btn.configure(state=tk.NORMAL)
                self.last_output_dir = str(Path(out_path).parent)
                messagebox.showinfo(
                    "Scrape complete",
                    f"Saved {row_count} jobs to:\n{out_path}",
                )
            elif event == "error":
                self.is_running = False
                self.run_btn.configure(state=tk.NORMAL)
                self._append_log("ERROR:\n" + str(payload))
                messagebox.showerror(
                    "Scrape failed",
                    "Scrape failed. Check the log for details.",
                )

        self.root.after(100, self._poll_events)


def main() -> None:
    """Application entrypoint used by Python and by the packaged EXE."""
    root = tk.Tk()
    app = GuttsRunnerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
