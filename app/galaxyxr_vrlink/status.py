"""Status model: what is installed, registered, running and what the last headset session reported."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import installer, steamvr


@dataclass
class Status:
    steamvr_found: bool = False
    steamvr_root: str = ""
    steamvr_version: str = ""
    steamvr_running: list[str] = field(default_factory=list)
    driver_installed: bool = False
    driver_version: str = ""
    driver_up_to_date: bool = False
    driver_registered: bool = False
    registered_paths: list[str] = field(default_factory=list)
    vrlink_settings_applied: bool = False
    last_session: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def _parse_vrlink_log(log_dir: Path | None) -> dict:
    """Last connection facts from driver_vrlink.txt: model, vendor section, render target, 10-bit."""
    out: dict = {}
    if not log_dir:
        return out
    p = log_dir / "driver_vrlink.txt"
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    lines = text.splitlines()
    # find last session start
    starts = [i for i, l in enumerate(lines) if "vrserver" in l and "startup with PID" in l]
    seg = lines[starts[-1]:] if starts else lines
    for l in seg:
        if "ReceivedHMDStaticProps" in l:
            m = re.search(r"Model Number: (.*?), Serial Number: (\S+) \((\d+)\)", l)
            if m:
                out["model"] = m.group(1)
                out["serial"] = m.group(2)
                out["model_class"] = int(m.group(3))
                out["time"] = l[:24]
        elif "Render Target:" in l:
            m = re.search(r"Render Target: (\d+) (\d+)", l)
            if m:
                out["render_target"] = f"{m.group(1)}x{m.group(2)}"
        elif "Using 10bit mode:" in l:
            out["ten_bit"] = l.strip().endswith("1")
        elif "Found settings for unknown hmd" in l:
            out["vendor_section"] = "read"
        elif "Using defaults as unknown headset" in l:
            out.setdefault("vendor_section", "ignored")
        elif "Unsupported controller type" in l:
            out["controller_error"] = l.split("- ", 1)[-1]
        elif "ResourceRoot " in l and "vrlink: " not in l:
            out["resource_root"] = l.rsplit(" ", 1)[-1]
    return out


def collect() -> Status:
    s = Status()
    info = steamvr.discover()
    s.steamvr_found = info.root is not None
    s.steamvr_root = str(info.root or "")
    s.steamvr_version = info.version
    s.problems.extend(info.errors)
    s.steamvr_running = steamvr.steamvr_running()
    s.driver_installed = (installer.INSTALL_DIR / "driver.vrdrivermanifest").exists()
    st = installer.load_state()
    s.driver_version = st.get("driver_version", "")
    if s.driver_installed:
        try:
            s.driver_up_to_date = installer.tree_digest(installer.INSTALL_DIR) == installer.tree_digest(installer.bundled_driver_dir())
        except (OSError, FileNotFoundError):
            s.driver_up_to_date = False
    if info.root:
        regs = steamvr.registered_driver_paths(info)
        s.registered_paths = [str(p) for p in regs]
        s.driver_registered = any(p.resolve() == installer.INSTALL_DIR.resolve() for p in regs if p.exists())
        for p in regs:
            if not (p / "driver.vrdrivermanifest").exists():
                s.problems.append(f"Registered driver path missing on disk: {p}")
        sec = steamvr.read_user_settings(info).get(steamvr.VRLINK_SECTION, {})
        s.vrlink_settings_applied = all(sec.get(k) == v for k, v in installer.VRLINK_USER_KEYS.items())
        s.last_session = _parse_vrlink_log(info.log_dir)
    ls = s.last_session
    if ls.get("model_class") not in (None, 1):
        s.problems.append(f"Headset reported '{ls.get('model')}' which vrlink treats as a known model; the Galaxy XR identity patch is not active on the headset.")
    if ls.get("controller_error"):
        s.problems.append(ls["controller_error"])
    return s
