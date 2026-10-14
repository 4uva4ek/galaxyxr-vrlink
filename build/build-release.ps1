# Builds galaxyxr-vrlink-<version>-windows-x64.zip: a single-file GUI exe plus the driver folder.
# Requires Python 3.11+ on PATH. Installs PyInstaller into a local venv on first run.
[CmdletBinding()]
param([switch]$SkipVenv)
# Native tools write progress to stderr; do not let PowerShell turn that into terminating errors.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$version = (Get-Content (Join-Path $root 'VERSION') -Raw).Trim()
$dist = Join-Path $root 'dist'
$venv = Join-Path $root '.venv'

function Invoke-Native {
    param([string]$Exe, [string[]]$Args, [string]$What)
    & $Exe @Args 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE)" }
}

if (-not $SkipVenv) {
    if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) { Invoke-Native python @('-m', 'venv', $venv) 'venv' }
    Invoke-Native (Join-Path $venv 'Scripts\python.exe') @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pip', 'pyinstaller') 'pip install'
}
$py = if (Test-Path (Join-Path $venv 'Scripts\python.exe')) { Join-Path $venv 'Scripts\python.exe' } else { 'python' }
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Force $dist | Out-Null
Invoke-Native $py @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
    '--name', 'GalaxyXR-VRLink-Setup',
    '--distpath', (Join-Path $dist 'exe'), '--workpath', (Join-Path $root 'build\pyi'), '--specpath', (Join-Path $root 'build\pyi'),
    '--add-data', ((Join-Path $root 'driver') + ';driver'),
    '--add-data', ((Join-Path $root 'VERSION') + ';.'),
    (Join-Path $root 'app\galaxyxr_vrlink\__main__.py')
) 'PyInstaller'
$stage = Join-Path $dist "galaxyxr-vrlink-$version-windows-x64"
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item (Join-Path $dist 'exe\GalaxyXR-VRLink-Setup.exe') $stage
Copy-Item -Recurse (Join-Path $root 'driver') (Join-Path $stage 'driver')
Copy-Item (Join-Path $root 'VERSION') $stage
Copy-Item (Join-Path $root 'README.md') $stage
$zip = "$stage.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "$stage\*" -DestinationPath $zip
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path $zip -Leaf)" | Set-Content -Encoding ascii "$zip.sha256"
Write-Host "built $zip"
Write-Host "sha256 $hash"
