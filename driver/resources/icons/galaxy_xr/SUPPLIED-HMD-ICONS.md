# Supplied Galaxy XR headset icons

Source: `galaxy-xr-hmd-icons.7z` supplied with this project.

**Galaxy XR icons were made by Vilkka. Based on original Quest Pro iconpack made by Lux / Hekky.**

Existing controller artwork and credits are unchanged.

## SteamVR driver resources

All 14 original PNG/GIF files are copied **byte-for-byte** into this resource directory and `GalaxyXRDriverGUI/public/icons`. Base artwork is 50×32 pixels; `_2x` artwork is 100×64 pixels. Searching animations are retained.

The Galaxy XR HMD shim now publishes nine `Prop_NamedIconPathDevice*` properties using the explicit supplied `headset_galaxy_xr_*` filenames and the installed driver's `{driverName}/icons/galaxy_xr/` resource namespace. See `src/Headsets/GalaxyXRStatusIcons.h` and `GalaxyXR.cpp`. A periodic check reapplies HMD icons while native identity is enabled, because the underlying streaming driver may rewrite them after activation. No controller or neutral-driver identity is replaced.

The supplied set has no distinct standby-alert or low-battery artwork. Those two property slots use standby and ready-alert respectively. The older `_status_*` assets remain for compatibility with older binaries; they are not the new HMD map. Keep matching `_2x` files alongside base files.

**Rebuild and deploy both the driver DLL and its entire resources folder.** Replacing only the GUI executable cannot change OpenVR device properties. Stop SteamVR before updating the installed driver, then restart and reconnect.

## Windows application icons

`tools/Generate-CompanionIcons.py` regenerates committed desktop assets from the supplied 100×64 ready image. No image-generation model, unrelated artwork or downloaded font is used. Alpha-bounds cropping and proportional centering improve small-size legibility. Each size is rendered directly from the source.

The Windows ICO has 13 RGBA entries: 32 (first), 16, 20, 24, 28, 40, 48, 56, 64, 80, 96, 128 and 256 pixels. Tauri's documented 32-pixel first-entry recommendation replaces the old 16-pixel first entry. Square PNGs, ICNS and both favicons are regenerated. `scripts/configure-tauri.mjs` selects these icon sources while preserving the existing native identifier, security configuration and Rust backend.

Larger files are resampled from the supplied art; they cannot recover detail absent from its 100×64 source. Native titlebar/taskbar appearance at different Windows scaling factors still requires the rebuilt Windows application to be checked. Existing pinned shortcuts may need to be replaced because the portable executable is now `Galaxy XR Companion.exe`.
