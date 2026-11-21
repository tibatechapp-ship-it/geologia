param(
    [switch]$GIS
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw "Python 3.12+ is required. Install Python and ensure python.exe is on PATH."
}

& python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12+ is required."
}

if (-not (Test-Path ".venv")) {
    & python -m venv .venv
}
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
$PackageSpec = if ($GIS) { ".[pdf,gis]" } else { ".[pdf]" }
& $VenvPython -m pip install -e $PackageSpec

Write-Host ""
Write-Host "GEOLOGIA installed in $Root\.venv"
Write-Host "Start with: powershell -ExecutionPolicy Bypass -File scripts\start-windows.ps1"
if (-not $GIS) {
    Write-Host "Optional GIS extra: powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -GIS"
}
