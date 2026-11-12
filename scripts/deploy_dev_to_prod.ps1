[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputDirectory = '',
    [switch]$RunTests
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
Set-Location $ProjectRoot
if (-not $OutputDirectory) { $OutputDirectory = Split-Path -Parent $ProjectRoot }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

if ($RunTests) {
    $env:PYTHONPATH='.'
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; deployment package was not created.' }
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$zip = Join-Path $OutputDirectory "indian-family-market-deploy-$timestamp.zip"

$excludeDirs = @('.venv','__pycache__','.pytest_cache','.git','backups','deployment-backups')
$excludeNames = @('setup_indian_family_market_v2.bat')

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Force | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($ProjectRoot.Length).TrimStart('\','/')
        $parts = $relative -split '[\\/]'
        if ($parts | Where-Object { $excludeDirs -contains $_ }) { return }
        if ($excludeNames -contains $parts[-1]) { return }
        # NEVER ship runtime databases or SQLite journals/WAL files.
        if ($_.Name -match '(?i)\.(db|sqlite|sqlite3|db-shm|db-wal|sqlite-wal|sqlite-shm)$') { return }
        if ($_.PSIsContainer) { return }
        $archivePath = $relative -replace '\\','/'
        [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $archivePath, [System.IO.Compression.CompressionLevel]::Optimal)
    }
}
finally { $archive.Dispose() }

# Hard safety check: a deployment package must never contain SQLite database files.
$bad = & python -c "from zipfile import ZipFile; import sys; z=ZipFile(r'$zip'); bad=[n for n in z.namelist() if n.lower().endswith(('.db','.sqlite','.sqlite3','.db-wal','.db-shm','.sqlite-wal','.sqlite-shm'))]; print('\n'.join(bad)); sys.exit(1 if bad else 0)"
if ($LASTEXITCODE -ne 0) { Remove-Item $zip -Force; throw 'Safety check failed: deployment ZIP contains a database file.' }

Write-Host "Created SAFE deployment package: $zip"
Write-Host "Production databases are intentionally excluded. Back them up on the server before deployment."
