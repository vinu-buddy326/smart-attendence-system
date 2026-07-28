$ErrorActionPreference = "Stop"

# Run from project root
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Ensure venv is active if you use one
if (Test-Path ".venv\\Scripts\\Activate.ps1") {
  . .venv\Scripts\Activate.ps1
} elseif (Test-Path "venv\\Scripts\\Activate.ps1") {
  . venv\Scripts\Activate.ps1
}

Write-Host "Starting Waitress on 0.0.0.0:5000"
waitress-serve --listen=0.0.0.0:5000 wsgi:application

