$ErrorActionPreference = "Stop"

# Loads DB creds from .env in the repo root and runs pg_dump.
# Requires pg_dump to be installed (PostgreSQL bin folder on PATH).

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (!(Test-Path ".env")) {
  throw ".env not found in project root."
}

# Minimal .env loader (KEY=VALUE)
Get-Content ".env" | ForEach-Object {
  $line = $_.Trim()
  if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
    $k, $v = $line.Split("=", 2)
    $k = $k.Trim()
    $v = $v.Trim()
    if ($k) { Set-Item -Path "Env:$k" -Value $v }
  }
}

$dbName = $env:DB_NAME
$dbUser = $env:DB_USER
$dbHost = $env:DB_HOST
$dbPort = $env:DB_PORT
$dbPass = $env:DB_PASS

if (!$dbName -or !$dbUser -or !$dbHost -or !$dbPort -or !$dbPass) {
  throw "Missing DB_* variables in .env"
}

$backupDir = Join-Path $root "backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $backupDir "attendance_db_$ts.dump"

$env:PGPASSWORD = $dbPass
Write-Host "Backing up database to $outFile"
pg_dump -Fc -h $dbHost -p $dbPort -U $dbUser -d $dbName -f $outFile
Write-Host "Backup complete."

