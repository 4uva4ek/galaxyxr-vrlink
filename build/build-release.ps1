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

# The venv interpreter location depends on the Python version and OS:
#   Windows, Python <= 3.13: <venv>\python.exe
#   Windows, Python  3.14+:  <venv>\Scripts\python.exe
#   Unix:                   <venv>\bin\python
function Find-VenvPython([string]$VenvDir) {
    # $IsWindows does not exist in Windows PowerShell 5.1; fall back to the OS variable.
    $onWindows = ($IsWindows -eq $true) -or ($env:OS -eq 'Windows_NT')
    $candidates = if ($onWindows) {
        @((Join-Path $VenvDir 'Scripts\python.exe'), (Join-Path $VenvDir 'python.exe'))
    } else {
        @((Join-Path $VenvDir 'bin/python'))
    }
    foreach ($candidate in $candidates) { if (Test-Path $candidate) { return $candidate } }
    return $null
}

function Invoke-Native {
    param([string]$Exe, [string[]]$CmdArgs, [string]$What)
    # Resolve the executable up front. If it is missing, a bare & would raise a
    # non-terminating error and leave $LASTEXITCODE stale (still 0), which would
    # slip past the exit-code check below and publish a broken release.
    $resolved = Get-Command $Exe -ErrorAction Stop
    & $resolved.Source @CmdArgs 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE)" }
}

if (-not $SkipVenv) {
    if (-not (Find-VenvPython $venv)) {
        Invoke-Native python @('-m', 'venv', $venv) 'venv'
    }
    $venvPy = Find-VenvPython $venv
    if (-not $venvPy) { throw "venv creation did not produce a python interpreter under $venv" }
    Invoke-Native $venvPy @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pip', 'pyinstaller') 'pip install'
}
$py = if ($venvPy = (Find-VenvPython $venv)) { $venvPy } else { 'python' }
Invoke-Native $py @('-m', 'PyInstaller', '--version') 'PyInstaller check'
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Force $dist | Out-Null
Invoke-Native $py @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
    '--name', 'GalaxyXR-VRLink-Setup',
    '--distpath', (Join-Path $dist 'exe'), '--workpath', (Join-Path $root 'build\pyi'), '--specpath', (Join-Path $root 'build\pyi'),
    '--add-data', ((Join-Path $root 'driver') + ';driver'),
    '--add-data', ((Join-Path $root 'VERSION') + ';.'),
    '--add-data', ((Join-Path $root 'app\galaxyxr_vrlink\icon.png') + ';galaxyxr_vrlink'),
    '--icon', (Join-Path $root 'assets\icon.ico'),
    '--paths', (Join-Path $root 'app'),
    (Join-Path $root 'app\launcher.py')
) 'PyInstaller'
$exe = Join-Path $dist 'exe\GalaxyXR-VRLink-Setup.exe'
if (-not (Test-Path $exe)) { throw "PyInstaller did not produce $exe" }
$stage = Join-Path $dist "galaxyxr-vrlink-$version-windows-x64"
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item $exe $stage
Copy-Item -Recurse (Join-Path $root 'driver') (Join-Path $stage 'driver')
Copy-Item (Join-Path $root 'VERSION') $stage
Copy-Item (Join-Path $root 'README.md') $stage
if (-not (Test-Path (Join-Path $stage 'GalaxyXR-VRLink-Setup.exe'))) { throw "staging lost the exe" }
$zip = "$stage.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "$stage\*" -DestinationPath $zip
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path $zip -Leaf)" | Set-Content -Encoding ascii "$zip.sha256"
Write-Host "built $zip"
Write-Host "sha256 $hash"
