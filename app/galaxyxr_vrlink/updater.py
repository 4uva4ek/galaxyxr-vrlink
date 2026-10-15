"""Update check against GitHub Releases and in-place driver update from a downloaded zip."""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import installer, steamvr

GITHUB_REPO = "4uva4ek/galaxyxr-vrlink"  # owner/repo
API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
USER_AGENT = "galaxyxr-vrlink-updater"
PLATFORM_TAG = "windows-x64" if steamvr.IS_WINDOWS else "linux-x64"
ASSET_RE = re.compile(rf"^galaxyxr-vrlink-(\d+\.\d+\.\d+)-{PLATFORM_TAG}\.zip$")


@dataclass
class Release:
    version: str
    url: str
    sha256: str | None
    notes: str


def _vt(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def check(current: str) -> Release | None:
    """Return the latest release if it is newer than `current`, else None. Raises on network errors."""
    req = urllib.request.Request(API, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    version = str(data.get("tag_name", "")).lstrip("v")
    urls = {a.get("name", ""): a.get("browser_download_url") for a in data.get("assets", [])}
    asset_name = next((n for n in urls if ASSET_RE.match(n)), None)
    asset_url = urls.get(asset_name) if asset_name else None
    # Releases carry one zip per platform; the checksum file is named after its zip.
    sha_url = urls.get(f"{asset_name}.sha256") if asset_name else None
    if not asset_url or _vt(version) <= _vt(current):
        return None
    sha = None
    if sha_url:
        req = urllib.request.Request(sha_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as r:
            txt = r.read().decode("utf-8", errors="ignore")
        m = re.search(r"\b([0-9a-fA-F]{64})\b", txt)
        sha = m.group(1).lower() if m else None
    return Release(version, asset_url, sha, str(data.get("body", "")))


def download(rel: Release, progress=None) -> Path:
    req = urllib.request.Request(rel.url, headers={"User-Agent": USER_AGENT})
    tmp = Path(tempfile.mkdtemp(prefix="galaxyxr-vrlink-")) / rel.url.rsplit("/", 1)[-1]
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if rel.sha256 and h.hexdigest() != rel.sha256:
        tmp.unlink(missing_ok=True)
        raise ValueError("Downloaded file does not match the published SHA-256.")
    return tmp


def apply_driver_update(info: steamvr.SteamVRInfo, zip_path: Path) -> installer.InstallResult:
    """Install the driver folder contained in a release zip (driver/galaxyxr/...)."""
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        prefix = None
        for marker in ("driver/galaxyxr/driver.vrdrivermanifest", "driver/driver.vrdrivermanifest"):
            for n in names:
                if n.endswith(marker):
                    prefix = n[: -len("driver.vrdrivermanifest")]
                    break
            if prefix is not None:
                break
        if prefix is None:
            return installer.InstallResult(False, ["Release zip has no driver/galaxyxr folder."])
        extract = Path(tempfile.mkdtemp(prefix="galaxyxr-driver-"))
        for n in names:
            if n.startswith(prefix) and not n.endswith("/"):
                target = extract / n[len(prefix):]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(n))
        version = None
        for n in names:
            if n.endswith("/VERSION") or n == "VERSION":
                version = z.read(n).decode("utf-8", errors="ignore").strip()
    res = installer.install(info, source=extract)
    shutil.rmtree(extract, ignore_errors=True)
    if res.ok and version:
        st = installer.load_state()
        st["driver_version"] = version
        installer.save_state(st)
    return res
