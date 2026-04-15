import ctypes
import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText


APP_BG = "#0B1220"
PANEL_BG = "#111827"
FIELD_BG = "#0F172A"
TEXT_FG = "#E5E7EB"
MUTED_FG = "#94A3B8"
BORDER = "#233047"
ACCENT = "#2563EB"
ACCENT_ACTIVE = "#1D4ED8"
DANGER = "#EF4444"

DEFAULT_CONFIG = {
    "LISTEN_HOST": "127.0.0.1",
    "LISTEN_PORT": 400,
    "CONNECT_IP": "",
    "CONNECT_PORT": 443,
    "FAKE_SNI": "",
    "DEBUG": False,
    "HANDLE_LIMIT": 64,
    "ACCEPT_BACKLOG": 128,
    "CONNECT_TIMEOUT": 5,
    "HANDSHAKE_TIMEOUT": 2,
    "RESOURCE_PRESSURE_BACKOFF": 0.5,
    "FAKE_SEND_WORKERS": 2,
    "NARROW_WINDIVERT_FILTER": True,
}


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_config_path() -> Path:
    return get_app_dir() / "config.json"


def load_config_file(path: Path) -> dict:
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config_file(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def resolve_ipv4(domain: str) -> str:
    infos = socket.getaddrinfo(domain, 443, socket.AF_INET, socket.SOCK_STREAM)
    if not infos:
        raise OSError("No IPv4 record found")
    return infos[0][4][0]


def parse_ping_ms(output: str) -> float | None:
    patterns = [
        r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
        r"Average = (\d+)\s*ms",
        r"Minimum = \d+ms, Maximum = \d+ms, Average = (\d+)\s*ms",
    ]
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def ping_host(ip: str, timeout_ms: int = 1200) -> float | None:
    if sys.platform.startswith("win"):
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        timeout_sec = max(1, int(round(timeout_ms / 1000)))
        cmd = ["ping", "-c", "1", "-W", str(timeout_sec), ip]

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
    latency = parse_ping_ms(combined)
    if completed.returncode == 0 and latency is not None:
        return latency
    return None


def contains_persian(text: str) -> bool:
    for ch in text:
        if "\u0600" <= ch <= "\u06FF":
            return True
    return False


def is_windows_admin() -> bool:
    if not sys.platform.startswith("win"):
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


@dataclass
class ScanResult:
    domain: str
    ip: str | None
    ping_ms: float | None
    status: str


def scan_domain(domain: str, timeout_ms: int = 1200) -> ScanResult:
    domain = domain.strip()
    if not domain:
        return ScanResult(domain="", ip=None, ping_ms=None, status="Empty")

    try:
        ip = resolve_ipv4(domain)
    except Exception as e:
        return ScanResult(domain=domain, ip=None, ping_ms=None, status=f"DNS failed: {e}")

    try:
        ping_ms = ping_host(ip, timeout_ms=timeout_ms)
    except Exception as e:
        return ScanResult(domain=domain, ip=ip, ping_ms=None, status=f"Ping failed: {e}")

    if ping_ms is None:
        return ScanResult(domain=domain, ip=ip, ping_ms=None, status="Ping timeout or unreachable")

    return ScanResult(domain=domain, ip=ip, ping_ms=ping_ms, status="OK")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bypass Control Center")
        self.geometry("1240x820")
        self.minsize(1080, 720)
        self.configure(bg=APP_BG)

        self.app_dir = get_app_dir()
        self.config_path = get_config_path()
        self.config_data = load_config_file(self.config_path)

        self.scan_queue: queue.Queue = queue.Queue()
        self.log_queue: queue.Queue = queue.Queue()
        self.scan_results: dict[str, ScanResult] = {}
        self.process: subprocess.Popen | None = None

        self._setup_style()
        self._build_ui()
        self._load_config_into_form()
        self._refresh_runtime_summary()

        self.after(120, self._poll_scan_queue)
        self.after(120, self._poll_log_queue)
        self.after(500, self._poll_process_state)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=APP_BG, foreground=TEXT_FG)
        style.configure("TNotebook", background=APP_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_BG, foreground=TEXT_FG, padding=(18, 10))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "white")])

        style.configure("Panel.TFrame", background=PANEL_BG)
        style.configure("Title.TLabel", background=PANEL_BG, foreground="white", font=("Segoe UI Semibold", 12))
        style.configure("Subtle.TLabel", background=PANEL_BG, foreground=MUTED_FG)
        style.configure("Accent.TButton", background=ACCENT, foreground="white", padding=(14, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", ACCENT_ACTIVE), ("pressed", ACCENT_ACTIVE)])
        style.configure("Stop.TButton", background=DANGER, foreground="white", padding=(14, 8), borderwidth=0)
        style.map("Stop.TButton", background=[("active", "#DC2626"), ("pressed", "#DC2626")])
        style.configure("Secondary.TButton", background="#334155", foreground="white", padding=(12, 8))
        style.map("Secondary.TButton", background=[("active", "#475569")])

        style.configure("Treeview",
                        background=FIELD_BG,
                        fieldbackground=FIELD_BG,
                        foreground=TEXT_FG,
                        rowheight=28,
                        borderwidth=0)
        style.configure("Treeview.Heading", background="#172033", foreground="white", relief="flat")
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])

    def _panel(self, parent: tk.Widget, title: str, subtitle: str = "") -> ttk.Frame:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=16)
        ttk.Label(panel, text=title, style="Title.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(panel, text=subtitle, style="Subtle.TLabel").pack(anchor="w", pady=(2, 10))
        return panel

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=APP_BG)
        header.pack(fill="x", padx=22, pady=(18, 10))

        tk.Label(
            header,
            text="Bypass Control Center",
            bg=APP_BG,
            fg="white",
            font=("Segoe UI Semibold", 24),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Edit settings, scan domains, select the best target, and run the core service.",
            bg=APP_BG,
            fg=MUTED_FG,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        self.status_var = tk.StringVar(value=f"Config file: {self.config_path}")
        tk.Label(self, textvariable=self.status_var, bg=APP_BG, fg="#BFDBFE", font=("Segoe UI", 9)).pack(
            anchor="w", padx=24, pady=(0, 10)
        )

        content = tk.Frame(self, bg=APP_BG)
        content.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        left = tk.Frame(content, bg=APP_BG)
        right = tk.Frame(content, bg=APP_BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right.pack(side="left", fill="both", expand=True)

        notebook = ttk.Notebook(left)
        notebook.pack(fill="both", expand=True)

        self.settings_tab = tk.Frame(notebook, bg=APP_BG)
        self.scanner_tab = tk.Frame(notebook, bg=APP_BG)
        notebook.add(self.settings_tab, text="Settings")
        notebook.add(self.scanner_tab, text="Domain Scanner")

        self._build_settings_tab()
        self._build_scanner_tab()
        self._build_runtime_panel(right)

    def _entry_row(self, parent: tk.Widget, label: str, variable: tk.Variable) -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=6)

        tk.Label(row, text=label, bg=PANEL_BG, fg=TEXT_FG, width=24, anchor="w",
                 font=("Segoe UI", 10)).pack(side="left")

        entry = tk.Entry(
            row,
            textvariable=variable,
            bg=FIELD_BG,
            fg=TEXT_FG,
            insertbackground="white",
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 0))

    def _check_row(self, parent: tk.Widget, label: str, variable: tk.BooleanVar) -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=6)

        tk.Checkbutton(
            row,
            text=label,
            variable=variable,
            bg=PANEL_BG,
            fg=TEXT_FG,
            selectcolor=FIELD_BG,
            activebackground=PANEL_BG,
            activeforeground=TEXT_FG,
            font=("Segoe UI", 10),
        ).pack(anchor="w")

    def _build_settings_tab(self) -> None:
        wrap = tk.Frame(self.settings_tab, bg=APP_BG)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)

        left = tk.Frame(wrap, bg=APP_BG)
        right = tk.Frame(wrap, bg=APP_BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right.pack(side="left", fill="both", expand=True)

        self.listen_host_var = tk.StringVar()
        self.listen_port_var = tk.StringVar()
        self.connect_ip_var = tk.StringVar()
        self.connect_port_var = tk.StringVar()
        self.fake_sni_var = tk.StringVar()

        self.debug_var = tk.BooleanVar()
        self.narrow_filter_var = tk.BooleanVar()
        self.handle_limit_var = tk.StringVar()
        self.accept_backlog_var = tk.StringVar()
        self.connect_timeout_var = tk.StringVar()
        self.handshake_timeout_var = tk.StringVar()
        self.backoff_var = tk.StringVar()
        self.fake_send_workers_var = tk.StringVar()

        core = self._panel(left, "Core settings", "Primary networking and target settings.")
        core.pack(fill="x", pady=(0, 10))
        self._entry_row(core, "LISTEN_HOST", self.listen_host_var)
        self._entry_row(core, "LISTEN_PORT", self.listen_port_var)
        self._entry_row(core, "CONNECT_PORT", self.connect_port_var)
        self._entry_row(core, "FAKE_SNI", self.fake_sni_var)
        self._entry_row(core, "CONNECT_IP", self.connect_ip_var)

        perf = self._panel(right, "Performance settings", "Resource limits and runtime tuning.")
        perf.pack(fill="x", pady=(0, 10))
        self._check_row(perf, "DEBUG", self.debug_var)
        self._check_row(perf, "NARROW_WINDIVERT_FILTER", self.narrow_filter_var)
        self._entry_row(perf, "HANDLE_LIMIT", self.handle_limit_var)
        self._entry_row(perf, "ACCEPT_BACKLOG", self.accept_backlog_var)
        self._entry_row(perf, "CONNECT_TIMEOUT", self.connect_timeout_var)
        self._entry_row(perf, "HANDSHAKE_TIMEOUT", self.handshake_timeout_var)
        self._entry_row(perf, "RESOURCE_PRESSURE_BACKOFF", self.backoff_var)
        self._entry_row(perf, "FAKE_SEND_WORKERS", self.fake_send_workers_var)

        help_panel = self._panel(left, "Recommended starting values")
        help_panel.pack(fill="both", expand=True)
        tk.Label(
            help_panel,
            text=(
                "Suggested defaults:\n"
                "• HANDLE_LIMIT = 64\n"
                "• ACCEPT_BACKLOG = 128\n"
                "• DEBUG = false\n"
                "• FAKE_SEND_WORKERS = 2\n"
                "• NARROW_WINDIVERT_FILTER = true\n\n"
                "Save the configuration before starting the service."
            ),
            bg=PANEL_BG,
            fg=TEXT_FG,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w")

        actions = tk.Frame(self.settings_tab, bg=APP_BG)
        actions.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Button(actions, text="Reload config", style="Secondary.TButton", command=self.reload_config).pack(side="left")
        ttk.Button(actions, text="Save config", style="Accent.TButton", command=self.save_config).pack(side="left", padx=10)

    def _build_scanner_tab(self) -> None:
        wrap = tk.Frame(self.scanner_tab, bg=APP_BG)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)

        left = self._panel(wrap, "Domain list", "One domain per line. This box is fully editable.")
        right = self._panel(wrap, "Scan results", "Auto-select the lowest latency or apply a manual selection.")
        left.pack(side="left", fill="both", expand=False, padx=(0, 10))
        right.pack(side="left", fill="both", expand=True)

        self.domain_text = ScrolledText(
            left,
            width=36,
            height=24,
            bg=FIELD_BG,
            fg=TEXT_FG,
            insertbackground="white",
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=("Consolas", 10),
            wrap="none",
        )
        self.domain_text.pack(fill="both", expand=True)
        self.domain_text.insert(
            "1.0",
            "static.cloudflareinsights.com\nwww.cloudflare.com\none.one.one.one\n"
        )
        self.domain_text.focus_set()

        left_buttons = tk.Frame(left, bg=PANEL_BG)
        left_buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(left_buttons, text="Start scan", style="Accent.TButton", command=self.start_scan).pack(side="left")
        ttk.Button(left_buttons, text="Clear", style="Secondary.TButton", command=self.clear_domain_list).pack(side="left", padx=10)
        ttk.Button(left_buttons, text="Load sample list", style="Secondary.TButton", command=self.load_sample_domains).pack(side="left")

        columns = ("domain", "ip", "ping", "status")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", height=18)
        self.tree.heading("domain", text="Domain")
        self.tree.heading("ip", text="Resolved IP")
        self.tree.heading("ping", text="Ping (ms)")
        self.tree.heading("status", text="Status")
        self.tree.column("domain", width=250)
        self.tree.column("ip", width=170)
        self.tree.column("ping", width=90, anchor="center")
        self.tree.column("status", width=240)
        self.tree.pack(fill="both", expand=True)

        result_actions = tk.Frame(right, bg=PANEL_BG)
        result_actions.pack(fill="x", pady=(12, 0))
        ttk.Button(result_actions, text="Auto select best", style="Accent.TButton", command=self.auto_select_best).pack(side="left")
        ttk.Button(result_actions, text="Apply selected", style="Secondary.TButton", command=self.apply_selected_result).pack(side="left", padx=10)

        self.best_var = tk.StringVar(value="No scan has been run yet.")
        tk.Label(right, textvariable=self.best_var, bg=PANEL_BG, fg="#BFDBFE", font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 0))

    def _build_runtime_panel(self, parent: tk.Widget) -> None:
        runtime = self._panel(parent, "Runtime", "Start or stop the core service, inspect status, and view logs.")
        runtime.pack(fill="both", expand=True)

        status_grid = tk.Frame(runtime, bg=PANEL_BG)
        status_grid.pack(fill="x", pady=(0, 10))

        self.service_status_var = tk.StringVar(value="Stopped")
        self.proxy_var = tk.StringVar(value="Proxy: -")
        self.target_var = tk.StringVar(value="Target: -")
        self.runtime_mode_var = tk.StringVar(value="Source: -")

        self._status_line(status_grid, "Service status", self.service_status_var, 0)
        self._status_line(status_grid, "Proxy endpoint", self.proxy_var, 1)
        self._status_line(status_grid, "Current target", self.target_var, 2)
        self._status_line(status_grid, "Launch source", self.runtime_mode_var, 3)

        buttons = tk.Frame(runtime, bg=PANEL_BG)
        buttons.pack(fill="x", pady=(0, 12))
        self.run_button = ttk.Button(buttons, text="RUN", style="Accent.TButton", command=self.start_service)
        self.stop_button = ttk.Button(buttons, text="STOP", style="Stop.TButton", command=self.stop_service)
        self.clear_log_button = ttk.Button(buttons, text="Clear log", style="Secondary.TButton", command=self.clear_log)
        self.run_button.pack(side="left")
        self.stop_button.pack(side="left", padx=10)
        self.clear_log_button.pack(side="left")
        self.stop_button.state(["disabled"])

        tk.Label(runtime, text="Service log", bg=PANEL_BG, fg="white",
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(4, 8))

        self.log_text = ScrolledText(
            runtime,
            bg=FIELD_BG,
            fg=TEXT_FG,
            insertbackground="white",
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=("Consolas", 10),
            state="disabled",
            wrap="word",
        )
        self.log_text.pack(fill="both", expand=True)

    def _status_line(self, parent: tk.Widget, label: str, variable: tk.StringVar, row: int) -> None:
        tk.Label(parent, text=label, bg=PANEL_BG, fg=MUTED_FG, width=16, anchor="w",
                 font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", pady=4)
        tk.Label(parent, textvariable=variable, bg=PANEL_BG, fg=TEXT_FG, anchor="w",
                 font=("Segoe UI", 10)).grid(row=row, column=1, sticky="w", pady=4, padx=(10, 0))

    def _load_config_into_form(self) -> None:
        cfg = self.config_data
        self.listen_host_var.set(str(cfg.get("LISTEN_HOST", "")))
        self.listen_port_var.set(str(cfg.get("LISTEN_PORT", "")))
        self.connect_ip_var.set(str(cfg.get("CONNECT_IP", "")))
        self.connect_port_var.set(str(cfg.get("CONNECT_PORT", "")))
        self.fake_sni_var.set(str(cfg.get("FAKE_SNI", "")))

        self.debug_var.set(bool(cfg.get("DEBUG", False)))
        self.narrow_filter_var.set(bool(cfg.get("NARROW_WINDIVERT_FILTER", True)))
        self.handle_limit_var.set(str(cfg.get("HANDLE_LIMIT", DEFAULT_CONFIG["HANDLE_LIMIT"])))
        self.accept_backlog_var.set(str(cfg.get("ACCEPT_BACKLOG", DEFAULT_CONFIG["ACCEPT_BACKLOG"])))
        self.connect_timeout_var.set(str(cfg.get("CONNECT_TIMEOUT", DEFAULT_CONFIG["CONNECT_TIMEOUT"])))
        self.handshake_timeout_var.set(str(cfg.get("HANDSHAKE_TIMEOUT", DEFAULT_CONFIG["HANDSHAKE_TIMEOUT"])))
        self.backoff_var.set(str(cfg.get("RESOURCE_PRESSURE_BACKOFF", DEFAULT_CONFIG["RESOURCE_PRESSURE_BACKOFF"])))
        self.fake_send_workers_var.set(str(cfg.get("FAKE_SEND_WORKERS", DEFAULT_CONFIG["FAKE_SEND_WORKERS"])))

    def _collect_form_data(self) -> dict:
        return {
            "LISTEN_HOST": self.listen_host_var.get().strip(),
            "LISTEN_PORT": int(self.listen_port_var.get().strip()),
            "CONNECT_IP": self.connect_ip_var.get().strip(),
            "CONNECT_PORT": int(self.connect_port_var.get().strip()),
            "FAKE_SNI": self.fake_sni_var.get().strip(),
            "DEBUG": bool(self.debug_var.get()),
            "HANDLE_LIMIT": int(self.handle_limit_var.get().strip()),
            "ACCEPT_BACKLOG": int(self.accept_backlog_var.get().strip()),
            "CONNECT_TIMEOUT": float(self.connect_timeout_var.get().strip()),
            "HANDSHAKE_TIMEOUT": float(self.handshake_timeout_var.get().strip()),
            "RESOURCE_PRESSURE_BACKOFF": float(self.backoff_var.get().strip()),
            "FAKE_SEND_WORKERS": int(self.fake_send_workers_var.get().strip()),
            "NARROW_WINDIVERT_FILTER": bool(self.narrow_filter_var.get()),
        }

    def save_config(self, show_message: bool = True) -> bool:
        try:
            self.config_data = self._collect_form_data()
            save_config_file(self.config_path, self.config_data)
            self._refresh_runtime_summary()
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            self.status_var.set(f"Save failed: {e}")
            return False

        self.status_var.set(f"Saved config: {self.config_path}")
        if show_message:
            messagebox.showinfo("Saved", "Configuration saved successfully.")
        return True

    def reload_config(self) -> None:
        try:
            self.config_data = load_config_file(self.config_path)
        except Exception as e:
            messagebox.showerror("Load failed", str(e))
            self.status_var.set(f"Load failed: {e}")
            return

        self._load_config_into_form()
        self._refresh_runtime_summary()
        self.status_var.set(f"Reloaded config: {self.config_path}")

    def _refresh_runtime_summary(self) -> None:
        cfg = self._collect_form_data_safe()
        proxy = f"{cfg.get('LISTEN_HOST', '-') or '-'}:{cfg.get('LISTEN_PORT', '-')}"
        target = f"{cfg.get('FAKE_SNI', '-') or '-'}  |  {cfg.get('CONNECT_IP', '-') or '-'}:{cfg.get('CONNECT_PORT', '-')}"
        self.proxy_var.set(proxy)
        self.target_var.set(target)

    def _collect_form_data_safe(self) -> dict:
        try:
            return self._collect_form_data()
        except Exception:
            return dict(self.config_data)

    def clear_domain_list(self) -> None:
        self.domain_text.delete("1.0", "end")

    def load_sample_domains(self) -> None:
        self.domain_text.delete("1.0", "end")
        self.domain_text.insert(
            "1.0",
            "\n".join([
                "static.cloudflareinsights.com",
                "www.cloudflare.com",
                "one.one.one.one",
                "cloudflare-dns.com",
                "www.bing.com",
            ])
            + "\n"
        )

    def _unique_domains(self) -> list[str]:
        lines = [line.strip() for line in self.domain_text.get("1.0", "end").splitlines()]
        result = []
        seen = set()
        for domain in lines:
            if domain and domain not in seen:
                seen.add(domain)
                result.append(domain)
        return result

    def start_scan(self) -> None:
        domains = self._unique_domains()
        if not domains:
            messagebox.showwarning("No domains", "Enter at least one domain first.")
            return

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.scan_results.clear()
        self.best_var.set("Scanning...")

        def worker():
            for index, domain in enumerate(domains, 1):
                result = scan_domain(domain)
                self.scan_queue.put(("result", f"row-{index}", result))
            self.scan_queue.put(("done", None, None))

        threading.Thread(target=worker, daemon=True).start()
        self.status_var.set(f"Started scan for {len(domains)} domains.")

    def _poll_scan_queue(self) -> None:
        try:
            while True:
                kind, item_id, payload = self.scan_queue.get_nowait()
                if kind == "result":
                    result: ScanResult = payload
                    self.scan_results[item_id] = result
                    ping_text = "-" if result.ping_ms is None else f"{result.ping_ms:.0f}"
                    self.tree.insert("", "end", iid=item_id, values=(result.domain, result.ip or "-", ping_text, result.status))
                elif kind == "done":
                    self._update_best_label()
                    self.status_var.set("Domain scan finished.")
        except queue.Empty:
            pass
        finally:
            self.after(120, self._poll_scan_queue)

    def _best_result(self) -> tuple[str, ScanResult] | None:
        candidates = [
            (item_id, result)
            for item_id, result in self.scan_results.items()
            if result.ping_ms is not None and result.ip
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda pair: pair[1].ping_ms)

    def _update_best_label(self) -> None:
        best = self._best_result()
        if not best:
            self.best_var.set("No successful result found.")
            return
        _, result = best
        self.best_var.set(f"Best result: {result.domain}  |  {result.ip}  |  {result.ping_ms:.0f} ms")

    def auto_select_best(self) -> None:
        best = self._best_result()
        if not best:
            messagebox.showwarning("No result", "No successful scan result is available.")
            return

        item_id, result = best
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.see(item_id)
        self._apply_result(result, source="Auto-selected best result")

    def apply_selected_result(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select a result row first.")
            return

        result = self.scan_results.get(selected[0])
        if not result or not result.ip:
            messagebox.showwarning("Invalid selection", "The selected row does not contain a valid IP.")
            return

        self._apply_result(result, source="Applied selected result")

    def _apply_result(self, result: ScanResult, source: str) -> None:
        self.fake_sni_var.set(result.domain)
        self.connect_ip_var.set(result.ip or "")
        if self.save_config(show_message=False):
            self.status_var.set(f"{source}: FAKE_SNI={result.domain}, CONNECT_IP={result.ip}")
            messagebox.showinfo(
                "Configuration updated",
                f"{source}\n\nFAKE_SNI = {result.domain}\nCONNECT_IP = {result.ip}\n\nThe configuration file was saved."
            )

    def _append_log(self, line: str) -> None:
        if not line.strip():
            return
        if contains_persian(line):
            return

        self.log_text.configure(state="normal")
        self.log_text.insert("end", line.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _core_command(self) -> tuple[list[str] | None, str, str]:
        main_py = self.app_dir / "main.py"
        bypass_exe = self.app_dir / "bypass.exe"

        if bypass_exe.exists():
            return [str(bypass_exe)], f"Executable: {bypass_exe.name}", "exe"

        if main_py.exists():
            return [sys.executable, "-X", "utf8", str(main_py)], f"Python source: {main_py.name}", "python"

        return None, "No launch target found", "missing"

    def start_service(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("Already running", "The service is already running.")
            return

        if not self.save_config(show_message=False):
            return

        cmd, source_text, launch_kind = self._core_command()
        if cmd is None:
            messagebox.showerror("Start failed", "Could not find main.py or bypass.exe next to the GUI.")
            return

        if launch_kind == "python" and not is_windows_admin():
            messagebox.showerror(
                "Administrator rights required",
                "WinDivert needs administrator rights when the service is started from Python source.\n\n"
                "Run this GUI as administrator, or place bypass.exe next to the GUI so it can be launched instead."
            )
            self.status_var.set("Start blocked: administrator rights are required for Python source mode.")
            return

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.app_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=creationflags,
            )
        except Exception as e:
            messagebox.showerror(
                "Start failed",
                str(e) + "\n\nIf you are launching Python source mode, try running the GUI as administrator. "
                "If bypass.exe exists, the GUI will prefer it automatically."
            )
            self.process = None
            return

        self.runtime_mode_var.set(source_text + (" (admin)" if is_windows_admin() else " (standard user)"))
        self.service_status_var.set("Running")
        self.status_var.set("Service started.")
        self.run_button.state(["disabled"])
        self.stop_button.state(["!disabled"])
        self._append_log(f"[{time.strftime('%H:%M:%S')}] Service started.")

        thread = threading.Thread(target=self._read_process_output, daemon=True)
        thread.start()

    def stop_service(self) -> None:
        proc = self.process
        if not proc or proc.poll() is not None:
            self.service_status_var.set("Stopped")
            self.run_button.state(["!disabled"])
            self.stop_button.state(["disabled"])
            return

        self._append_log(f"[{time.strftime('%H:%M:%S')}] Stopping service...")
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

        self.process = None
        self.service_status_var.set("Stopped")
        self.status_var.set("Service stopped.")
        self.run_button.state(["!disabled"])
        self.stop_button.state(["disabled"])

    def _read_process_output(self) -> None:
        proc = self.process
        if proc is None or proc.stdout is None:
            return

        for raw_line in proc.stdout:
            self.log_queue.put(raw_line)

        try:
            code = proc.wait(timeout=0.2)
        except Exception:
            code = proc.poll()
        self.log_queue.put(f"[process exited with code {code}]")

    def _poll_log_queue(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass
        finally:
            self.after(120, self._poll_log_queue)

    def _poll_process_state(self) -> None:
        proc = self.process
        if proc is not None:
            code = proc.poll()
            if code is not None:
                self.process = None
                self.service_status_var.set(f"Stopped (exit code {code})")
                self.status_var.set("Service exited.")
                self.run_button.state(["!disabled"])
                self.stop_button.state(["disabled"])
        self.after(500, self._poll_process_state)

    def destroy(self) -> None:
        try:
            self.stop_service()
        finally:
            super().destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
