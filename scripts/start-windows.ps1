param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Api = Join-Path $Root ".venv\Scripts\geologia-api.exe"

if (-not (Test-Path $Api)) {
    throw "GEOLOGIA is not installed. Run scripts\install-windows.ps1 first."
}

Write-Host "GEOLOGIA is bound to localhost only."
Write-Host "Open http://127.0.0.1:$Port"
& $Api --host 127.0.0.1 --port $Port
