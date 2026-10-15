"""SteamVR discovery, vrpathreg registration, process checks and settings access (Windows, Linux)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DRIVER_NAME = "galaxyxr"
VRLINK_SECTION = "driver_vrlink"
STEAMVR_PROCESSES = ("vrserver", "vrmonitor", "vrcompositor", "vrdashboard", "vrwebhelper", "vrstartup")
IS_WINDOWS = sys.platform == "win32"


@dataclass
class SteamVRInfo:
    root: Path | None = None
    config_dir: Path | None = None
    log_dir: Path | None = None
    vrpathreg: Path | None = None
    version: str = ""
    external_drivers: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _steam_path() -> Path | None:
    if IS_WINDOWS:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                return Path(winreg.QueryValueEx(k, "SteamPath")[0])
        except OSError:
            return None
    # Native Steam on Linux; ~/.steam/steam and ~/.steam/root are symlinks to the real install.
    home = Path.home()
    for c in (home / ".local" / "share" / "Steam", home / ".steam" / "steam", home / ".steam" / "root"):
        if (c / "steamapps").is_dir():
            return c.resolve()
    return None


def openvrpaths_file() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", "")) / "openvr" / "openvrpaths.vrpath"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "openvr" / "openvrpaths.vrpath"


def _vrpathreg_in(root: Path) -> Path:
    # On Linux the .sh wrapper sets up the SteamVR runtime environment before running linux64/vrpathreg.
    return root / "bin" / "win64" / "vrpathreg.exe" if IS_WINDOWS else root / "bin" / "vrpathreg.sh"


def read_openvrpaths() -> dict:
    p = openvrpaths_file()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def discover() -> SteamVRInfo:
    info = SteamVRInfo()
    paths = read_openvrpaths()
    candidates: list[Path] = []
    for r in paths.get("runtime", []) or []:
        candidates.append(Path(r))
    steam = _steam_path()
    if steam:
        candidates.append(steam / "steamapps" / "common" / "SteamVR")
    for c in candidates:
        if _vrpathreg_in(c).exists():
            info.root = c
            info.vrpathreg = _vrpathreg_in(c)
            break
    if info.root is None:
        info.errors.append("SteamVR not found (no runtime in openvrpaths.vrpath and no Steam install found).")
        return info
    cfg = paths.get("config", []) or []
    info.config_dir = Path(cfg[0]) if cfg else (steam / "config" if steam else None)
    logs = paths.get("log", []) or []
    info.log_dir = Path(logs[0]) if logs else (steam / "logs" if steam else None)
    vt = info.root / "bin" / "version.txt"
    if vt.exists():
        info.version = vt.read_text(encoding="utf-8", errors="ignore").strip()
    info.external_drivers = [str(x) for x in (paths.get("external_drivers", []) or [])]
    return info


def _process_names() -> list[str]:
    if IS_WINDOWS:
        try:
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        return [m.group(1) for m in (re.match(r'"([^"]+)\.exe"', line, re.I) for line in out.splitlines()) if m]
    names = []
    for d in Path("/proc").glob("[0-9]*"):
        try:
            names.append((d / "comm").read_text().strip())
        except OSError:
            continue
    return names


def steamvr_running() -> list[str]:
    return sorted({n.lower() for n in _process_names() if n.lower() in STEAMVR_PROCESSES})


def vrpathreg(info: SteamVRInfo, *args: str) -> tuple[int, str]:
    if not info.vrpathreg:
        return 1, "vrpathreg not found"
    try:
        r = subprocess.run([str(info.vrpathreg), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)
    return r.returncode, (r.stdout + r.stderr).strip()


def registered_driver_paths(info: SteamVRInfo) -> list[Path]:
    """Driver folders currently registered whose manifest name is galaxyxr."""
    found = []
    for d in read_openvrpaths().get("external_drivers", []) or []:
        m = Path(d) / "driver.vrdrivermanifest"
        try:
            name = json.loads(m.read_text(encoding="utf-8")).get("name", "")
        except (OSError, ValueError):
            continue
        if name == DRIVER_NAME:
            found.append(Path(d))
    return found


def read_user_settings(info: SteamVRInfo) -> dict:
    if not info.config_dir:
        return {}
    p = info.config_dir / "steamvr.vrsettings"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_user_settings(info: SteamVRInfo, data: dict, backup_dir: Path) -> Path:
    """Write steamvr.vrsettings with a timestamped backup. Caller must ensure SteamVR is closed."""
    import shutil
    import time

    p = info.config_dir / "steamvr.vrsettings"
    backup_dir.mkdir(parents=True, exist_ok=True)
    b = backup_dir / f"steamvr.vrsettings.{time.strftime('%Y%m%d-%H%M%S')}.bak"
    if p.exists():
        shutil.copy2(p, b)
    tmp = p.with_suffix(".vrsettings.tmp")
    tmp.write_text(json.dumps(data, indent=3), encoding="utf-8")
    os.replace(tmp, p)
    return b
