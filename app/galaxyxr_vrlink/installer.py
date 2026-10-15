"""Install, update and remove the resource-only SteamVR driver `galaxyxr`."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from . import steamvr

if steamvr.IS_WINDOWS:
    APP_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "GalaxyXR" / "VRLink"
else:
    APP_DIR = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "GalaxyXR" / "VRLink"
INSTALL_DIR = APP_DIR / "driver" / steamvr.DRIVER_NAME
BACKUP_DIR = APP_DIR / "backups"
STATE_FILE = APP_DIR / "state.json"

# vrlink keys the resource-only driver cannot supply because vrlink ignores vendor sections
# in the SteamVR builds tested (2.18.3 / 1791582248). Written to the user settings on request.
# 10-bit is not forced: vrlink's own default (10bit=true) already selects it when the GPU can encode it.
VRLINK_USER_KEYS = {
    "renderWidth": 3552,
    "renderHeight": 3840,
    "overrideRenderWidth": 3552,
    "overrideRenderHeight": 3840,
}


def bundled_driver_dir() -> Path:
    """Driver payload shipped next to the app (PyInstaller bundle or source checkout)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    # driver/galaxyxr/ is the layout; driver/ (flat) is accepted for the 0.1.0 zip.
    for cand in (base / "driver" / steamvr.DRIVER_NAME, base / steamvr.DRIVER_NAME, base / "driver"):
        if (cand / "driver.vrdrivermanifest").exists():
            return cand
    raise FileNotFoundError("bundled driver folder not found")


def bundled_version() -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    v = base / "VERSION"
    return v.read_text(encoding="utf-8").strip() if v.exists() else "0.0.0"


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(root)).replace("\\", "/").encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(d: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


@dataclass
class InstallResult:
    ok: bool
    messages: list[str]


def install(info: steamvr.SteamVRInfo, source: Path | None = None) -> InstallResult:
    """Copy the driver to APP_DIR (per-user, no admin) and register it with vrpathreg. Idempotent."""
    msgs: list[str] = []
    if info.root is None:
        return InstallResult(False, ["SteamVR not found."])
    running = steamvr.steamvr_running()
    if running:
        return InstallResult(False, [f"Close SteamVR first (running: {', '.join(running)})."])
    src = source or bundled_driver_dir()
    staging = INSTALL_DIR.with_name(INSTALL_DIR.name + ".new")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(src, staging)
    # swap in
    old = INSTALL_DIR.with_name(INSTALL_DIR.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if INSTALL_DIR.exists():
        INSTALL_DIR.rename(old)
    staging.rename(INSTALL_DIR)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    msgs.append(f"Driver files installed to {INSTALL_DIR}")
    # drop stale registrations of other copies of this driver
    for p in steamvr.registered_driver_paths(info):
        if p.resolve() != INSTALL_DIR.resolve():
            rc, out = steamvr.vrpathreg(info, "removedriver", str(p))
            msgs.append(f"Removed stale registration {p} (rc={rc})")
    if INSTALL_DIR.resolve() not in [p.resolve() for p in steamvr.registered_driver_paths(info)]:
        rc, out = steamvr.vrpathreg(info, "adddriver", str(INSTALL_DIR))
        if rc != 0:
            return InstallResult(False, msgs + [f"vrpathreg adddriver failed: {out}"])
        msgs.append("Registered with SteamVR (vrpathreg adddriver).")
    else:
        msgs.append("Already registered with SteamVR.")
    st = load_state()
    st.update({"driver_version": bundled_version(), "driver_digest": tree_digest(INSTALL_DIR), "install_dir": str(INSTALL_DIR)})
    save_state(st)
    return InstallResult(True, msgs)


def uninstall(info: steamvr.SteamVRInfo) -> InstallResult:
    msgs: list[str] = []
    running = steamvr.steamvr_running()
    if running:
        return InstallResult(False, [f"Close SteamVR first (running: {', '.join(running)})."])
    for p in steamvr.registered_driver_paths(info):
        rc, out = steamvr.vrpathreg(info, "removedriver", str(p))
        msgs.append(f"Unregistered {p} (rc={rc})")
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
        msgs.append(f"Removed {INSTALL_DIR}")
    st = load_state()
    st.pop("driver_version", None)
    st.pop("driver_digest", None)
    save_state(st)
    return InstallResult(True, msgs or ["Nothing to remove."])


def apply_vrlink_settings(info: steamvr.SteamVRInfo) -> InstallResult:
    """Write the vrlink user keys (render size) with a backup. SteamVR must be closed."""
    running = steamvr.steamvr_running()
    if running:
        return InstallResult(False, [f"Close SteamVR first (running: {', '.join(running)})."])
    data = steamvr.read_user_settings(info)
    sec = data.setdefault(steamvr.VRLINK_SECTION, {})
    changed = {k: v for k, v in VRLINK_USER_KEYS.items() if sec.get(k) != v}
    if not changed:
        return InstallResult(True, ["vrlink settings already applied."])
    st = load_state()
    originals = st.setdefault("vrlink_originals", {})
    for k in changed:
        originals.setdefault(k, sec.get(k, None))
    sec.update(changed)
    b = steamvr.write_user_settings(info, data, BACKUP_DIR)
    save_state(st)
    return InstallResult(True, [f"Applied {', '.join(changed)} to {steamvr.VRLINK_SECTION}.", f"Backup: {b}"])


def restore_vrlink_settings(info: steamvr.SteamVRInfo) -> InstallResult:
    running = steamvr.steamvr_running()
    if running:
        return InstallResult(False, [f"Close SteamVR first (running: {', '.join(running)})."])
    st = load_state()
    originals = st.get("vrlink_originals") or {}
    if not originals:
        return InstallResult(True, ["No recorded originals; nothing restored."])
    data = steamvr.read_user_settings(info)
    sec = data.setdefault(steamvr.VRLINK_SECTION, {})
    for k, v in originals.items():
        if v is None:
            sec.pop(k, None)
        else:
            sec[k] = v
    b = steamvr.write_user_settings(info, data, BACKUP_DIR)
    st.pop("vrlink_originals", None)
    save_state(st)
    return InstallResult(True, [f"Restored {', '.join(originals)}.", f"Backup: {b}"])
