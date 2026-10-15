<img src="assets/icon.svg" width="96" alt="">

# Galaxy XR VRLink Setup

PC side of native Samsung Galaxy XR support in SteamVR through Steam Link, without a custom
OpenVR driver. It follows Valve's resource-only vendor driver layout
([Steam Link Integration for External Vendors](https://github.com/ValveSoftware/openvr/wiki/Steam-Link-Integration-for-External-Vendors)):
a driver folder named `galaxyxr` that ships only JSON, icons, input profiles and render models.
SteamVR resolves `{galaxyxr}/...` paths the headset sends, so the Galaxy XR headset and controllers
appear with their own names, icons, models and bindings.

The headset side is the Morphe Steam Link patch that sends the Galaxy XR identity with
`{galaxyxr}` paths and the calibrated controller offset; see the steamlink-patches repository.

## What the app does

- **Status**: SteamVR location and build, whether SteamVR is running, driver files and version,
  vrpathreg registration, vrlink user settings, and what the last headset session reported
  (model, resource root, render target, 10-bit, controller errors).
- **Install / Update driver**: copies `driver/galaxyxr` to `%LOCALAPPDATA%\GalaxyXR\VRLink\driver\galaxyxr`
  (Linux: `~/.local/share/GalaxyXR/VRLink/driver/galaxyxr`, honouring `XDG_DATA_HOME`)
  and registers it with `vrpathreg adddriver`. No administrator rights, nothing is written into the
  SteamVR folder, so SteamVR updates cannot remove it. Stale registrations of older copies are removed.
- **Apply vrlink settings**: writes render size 3552x3840 into `driver_vrlink` in
  `steamvr.vrsettings` with a backup. Needed because the vrlink builds tested (SteamVR 2.18.3)
  ignore the vendor `vrlink_<model>` section that the driver also ships. Restore puts the previous
  values back.
- **Check for updates**: compares with the latest GitHub release, downloads the zip, verifies the
  published SHA-256 and updates the driver files in place.

All actions that change files require SteamVR to be closed; the app refuses otherwise.

## Install

### Windows

1. Download `galaxyxr-vrlink-<version>-windows-x64.zip` from Releases and extract it anywhere.
2. Close SteamVR, run `GalaxyXR-VRLink-Setup.exe`, press **Install / Update driver**, then
   **Apply vrlink settings**.
3. Start SteamVR and connect with the patched Steam Link. The status row "Last headset session"
   must show model `Galaxy XR` and resource root `galaxyxr`.

Command line: `GalaxyXR-VRLink-Setup.exe --status`, `--install`, `--uninstall`.

### Linux

Native (non-Flatpak) Steam with SteamVR for Linux. SteamVR's own `bin/vrpathreg.sh` is used for
registration and `~/.config/openvr/openvrpaths.vrpath` for discovery.

1. Download `galaxyxr-vrlink-<version>-linux-x64.zip` from Releases and extract it with `unzip`
   (keeps the executable bit; otherwise `chmod +x GalaxyXR-VRLink-Setup`).
2. Close SteamVR, run `./GalaxyXR-VRLink-Setup`, then proceed as on Windows.

Command line: `./GalaxyXR-VRLink-Setup --status`, `--install`, `--uninstall`.

From a source checkout no build is needed (Python 3.11+; the GUI needs tkinter, Arch `tk`,
Debian/Ubuntu `python3-tk`; the command line works without it):

```
python3 app/launcher.py --status
python3 app/launcher.py --install
python3 app/launcher.py
```

Flatpak Steam is not supported: its sandbox does not see `~/.local/share` and runs
`vrpathreg` inside the sandbox.

## Driver contents

- `driver.vrdrivermanifest`: `resourceOnly`, `alwaysActivate`, no HMD presence.
- `resources/settings/default.vrsettings`: `driver_galaxyxr` plus `vrlink_xrvst2ue` /
  `vrlink_Galaxy XR` sections and their `_controller_left/right` companions per the Valve wiki.
- `resources/driver.vrresources`: status icons keyed by model numbers `Galaxy XR`,
  `Galaxy XR (Left Controller)`, `Galaxy XR (Right Controller)`.
- `resources/input`: HMD and controller profiles, bindings, remappings.
- `resources/rendermodels`: `vst_controller_left/right` (and the s100 variants).

Known vrlink constraints (SteamVR 2.18.3, driver_vrlink.dll from 2026-10-10): controller type
must be one vrlink accepts (`oculus_touch` is used), handedness is parsed from the
`(Left Controller)` / `(Right Controller)` suffix of the model number, and the vendor settings
section is not consumed, hence the user-settings step.

## Build

`build\build-release.ps1` (Windows) and `build/build-release.sh` (Linux) create a venv, run
PyInstaller and produce the platform release zip and its `.sha256`. The GitHub workflow builds both
on Windows and Linux runners and attaches all files to the release; the updater picks the zip for
its own platform.
Set `GITHUB_REPO` in `app/galaxyxr_vrlink/updater.py` to the published repository.
