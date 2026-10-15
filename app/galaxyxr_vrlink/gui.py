"""Tkinter GUI: status, install/update/remove, vrlink settings, update check."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from . import installer, status, steamvr, updater

TITLE = "Galaxy XR VRLink Setup"


def open_path(path) -> None:
    """Open a file or folder with the desktop's default handler."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])  # noqa: S603,S607


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(TITLE)
        self.geometry("720x560")
        self.minsize(640, 480)
        self.app_version = installer.bundled_version()
        self._build()
        self.after(100, self.refresh)

    # ---------- layout ----------
    def _build(self) -> None:
        pad = {"padx": 10, "pady": 4}
        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text=TITLE, font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 14, "bold")).pack(side="left")
        ttk.Label(top, text=f"v{self.app_version}").pack(side="right")

        self.status_box = ttk.LabelFrame(self, text="Status")
        self.status_box.pack(fill="x", **pad)
        self.rows: dict[str, tuple[ttk.Label, ttk.Label]] = {}
        for key, label in [
            ("steamvr", "SteamVR"),
            ("running", "SteamVR state"),
            ("driver", "Driver files"),
            ("registered", "Registration"),
            ("settings", "vrlink settings"),
            ("headset", "Last headset session"),
            ("section", "Vendor section"),
        ]:
            r = ttk.Frame(self.status_box)
            r.pack(fill="x", padx=6, pady=1)
            ttk.Label(r, text=label + ":", width=20).pack(side="left")
            icon = ttk.Label(r, text="•", width=2)
            icon.pack(side="left")
            val = ttk.Label(r, text="…", anchor="w")
            val.pack(side="left", fill="x", expand=True)
            self.rows[key] = (icon, val)

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        self.btn_install = ttk.Button(btns, text="Install / Update driver", command=self.on_install)
        self.btn_install.pack(side="left", padx=2)
        self.btn_settings = ttk.Button(btns, text="Apply vrlink settings", command=self.on_apply_settings)
        self.btn_settings.pack(side="left", padx=2)
        self.btn_restore = ttk.Button(btns, text="Restore settings", command=self.on_restore_settings)
        self.btn_restore.pack(side="left", padx=2)
        self.btn_remove = ttk.Button(btns, text="Remove driver", command=self.on_uninstall)
        self.btn_remove.pack(side="left", padx=2)
        ttk.Button(btns, text="Refresh", command=self.refresh).pack(side="right", padx=2)

        btns2 = ttk.Frame(self)
        btns2.pack(fill="x", **pad)
        self.btn_update = ttk.Button(btns2, text="Check for updates", command=self.on_check_updates)
        self.btn_update.pack(side="left", padx=2)
        ttk.Button(btns2, text="Open vrlink log", command=self.on_open_log).pack(side="left", padx=2)
        ttk.Button(btns2, text="Open install folder", command=self.on_open_folder).pack(side="left", padx=2)
        self.progress = ttk.Progressbar(btns2, mode="determinate", length=200)
        self.progress.pack(side="right", padx=2)

        logf = ttk.LabelFrame(self, text="Log")
        logf.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(logf, height=10, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

    # ---------- helpers ----------
    def say(self, *lines: str) -> None:
        self.log.configure(state="normal")
        for l in lines:
            self.log.insert("end", l + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_row(self, key: str, ok: bool | None, text: str) -> None:
        icon, val = self.rows[key]
        icon.configure(text={True: "✓", False: "✗", None: "•"}[ok], foreground={True: "#1a7f37", False: "#b42318", None: "#666"}[ok])
        val.configure(text=text)

    def busy(self, flag: bool) -> None:
        for b in (self.btn_install, self.btn_settings, self.btn_restore, self.btn_remove, self.btn_update):
            b.configure(state="disabled" if flag else "normal")

    def run_bg(self, fn, done=None) -> None:
        self.busy(True)

        def work():
            try:
                res = fn()
            except Exception as e:  # noqa: BLE001 - surface everything to the user
                res = installer.InstallResult(False, [f"Error: {e}"])
            self.after(0, lambda: self._finish(res, done))

        threading.Thread(target=work, daemon=True).start()

    def _finish(self, res, done) -> None:
        self.busy(False)
        if isinstance(res, installer.InstallResult):
            self.say(*res.messages)
            if not res.ok:
                messagebox.showwarning(TITLE, "\n".join(res.messages))
        if done:
            done(res)
        self.refresh()

    # ---------- actions ----------
    def refresh(self) -> None:
        s = status.collect()
        self.set_row("steamvr", s.steamvr_found, f"{s.steamvr_root}  (build {s.steamvr_version})" if s.steamvr_found else "not found")
        self.set_row("running", None if not s.steamvr_running else False,
                     "closed" if not s.steamvr_running else "running: " + ", ".join(s.steamvr_running) + " (close it before installing or changing settings)")
        if s.driver_installed:
            self.set_row("driver", s.driver_up_to_date, f"installed v{s.driver_version or '?'} at {installer.INSTALL_DIR}" + ("" if s.driver_up_to_date else "  (differs from bundled files, press Install / Update)"))
        else:
            self.set_row("driver", False, "not installed")
        self.set_row("registered", s.driver_registered, "registered with SteamVR (vrpathreg)" if s.driver_registered else ("other copies registered: " + "; ".join(s.registered_paths) if s.registered_paths else "not registered"))
        self.set_row("settings", s.vrlink_settings_applied, "render 3552x3840 applied" if s.vrlink_settings_applied else "not applied (vrlink defaults 2048x2048 unless set)")
        ls = s.last_session
        if ls.get("model"):
            ok = ls.get("model_class") == 1 and not ls.get("controller_error")
            txt = f"{ls.get('time','')}: model '{ls['model']}', root {ls.get('resource_root','?')}, render {ls.get('render_target','?')}, 10-bit {'on' if ls.get('ten_bit') else 'off'}"
            self.set_row("headset", ok, txt)
        else:
            self.set_row("headset", None, "no connection in the current vrlink log")
        vs = ls.get("vendor_section")
        self.set_row("section", True if vs == "read" else None, {"read": "vrlink read vrlink_<model> settings", "ignored": "ignored by this vrlink build (expected on 2.18.x); user settings used instead"}.get(vs, "unknown"))
        for p in s.problems:
            self.say("! " + p)

    def on_install(self) -> None:
        info = steamvr.discover()
        self.run_bg(lambda: installer.install(info))

    def on_uninstall(self) -> None:
        if not messagebox.askyesno(TITLE, "Unregister and delete the galaxyxr driver?"):
            return
        info = steamvr.discover()
        self.run_bg(lambda: installer.uninstall(info))

    def on_apply_settings(self) -> None:
        info = steamvr.discover()
        self.run_bg(lambda: installer.apply_vrlink_settings(info))

    def on_restore_settings(self) -> None:
        info = steamvr.discover()
        self.run_bg(lambda: installer.restore_vrlink_settings(info))

    def on_open_log(self) -> None:
        info = steamvr.discover()
        if info.log_dir and (info.log_dir / "driver_vrlink.txt").exists():
            open_path(info.log_dir / "driver_vrlink.txt")
        else:
            messagebox.showinfo(TITLE, "driver_vrlink.txt not found.")

    def on_open_folder(self) -> None:
        installer.APP_DIR.mkdir(parents=True, exist_ok=True)
        open_path(installer.APP_DIR)

    def on_check_updates(self) -> None:
        def work():
            rel = updater.check(self.app_version)
            if rel is None:
                return installer.InstallResult(True, [f"No update: v{self.app_version} is the latest."])
            return rel

        def done(res):
            if isinstance(res, updater.Release):
                if messagebox.askyesno(TITLE, f"Version {res.version} is available.\n\n{res.notes[:800]}\n\nDownload and update the driver files now?"):
                    self.run_bg(lambda: self._download_and_apply(res))
                else:
                    webbrowser.open(f"https://github.com/{updater.GITHUB_REPO}/releases/latest")

        self.run_bg(work, done)

    def _download_and_apply(self, rel: updater.Release):
        def prog(done, total):
            self.after(0, lambda: self.progress.configure(maximum=max(total, 1), value=done))

        z = updater.download(rel, prog)
        info = steamvr.discover()
        res = updater.apply_driver_update(info, z)
        res.messages.insert(0, f"Downloaded {z.name}")
        res.messages.append("The app itself updates with the next release zip; the driver files are updated in place.")
        return res


def main() -> None:
    App().mainloop()
