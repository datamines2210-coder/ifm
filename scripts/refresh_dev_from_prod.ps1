[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [string]$ProdHost,
    [Parameter(Mandatory=$true)] [string]$ProdUser,
    [Parameter(Mandatory=$true)] [string]$ProdBackupRoot,
    [string]$LocalProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$RemoteBackupStamp = '',
    [string]$SshPort = '22',
    [ValidateSet('All','Market','Scorer','Travel','Sports')] [string]$Service = 'All'
)

$ErrorActionPreference = 'Stop'
$LocalProjectRoot = (Resolve-Path $LocalProjectRoot).Path
$stamp = if ($RemoteBackupStamp) { $RemoteBackupStamp } else { (ssh -p $SshPort "$ProdUser@$ProdHost" "ls -1dt '$ProdBackupRoot'/*/ | head -1" ).Trim().TrimEnd('/') | Split-Path -Leaf }
if (-not $stamp) { throw 'Could not determine the latest production backup directory.' }

$localBackup = Join-Path $LocalProjectRoot ("backups\dev-before-prod-refresh\" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $localBackup | Out-Null

$allTargets = @{
    Market = @{ Remote = "$ProdBackupRoot/$stamp/indian_family_market.db"; Local = (Join-Path $LocalProjectRoot 'indian_family_market.db') };
    Scorer = @{ Remote = "$ProdBackupRoot/$stamp/scorer.db"; Local = (Join-Path $LocalProjectRoot 'scorer_data\scorer.db') };
    Travel = @{ Remote = "$ProdBackupRoot/$stamp/travel.db"; Local = (Join-Path $LocalProjectRoot 'travel_data\travel.db') };
    Sports = @{ Remote = "$ProdBackupRoot/$stamp/sports.db"; Local = (Join-Path $LocalProjectRoot 'sports_data\sports.db') }
}
$targets = if ($Service -eq 'All') { @($allTargets.Market,$allTargets.Scorer,$allTargets.Travel,$allTargets.Sports) } else { @($allTargets[$Service]) }
Write-Host "Refreshing DEV service scope: $Service"

$tempRoot = Join-Path $env:TEMP ("ifm-prod-refresh-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
try {
    foreach ($target in $targets) {
        if (-not (Test-Path $target.Local)) { Write-Host "Local DB does not exist yet: $($target.Local)" }
        else {
            Copy-Item $target.Local (Join-Path $localBackup (Split-Path $target.Local -Leaf)) -Force
        }

        $download = Join-Path $tempRoot (Split-Path $target.Local -Leaf)
        scp -P $SshPort "$ProdUser@$ProdHost`:$($target.Remote)" $download
        if ($LASTEXITCODE -ne 0) { throw "SCP failed for $($target.Remote)" }

        $env:DB_TO_CHECK = $download
        $check = & python -c "import os,sqlite3; p=os.environ['DB_TO_CHECK']; c=sqlite3.connect(p); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()"
        if ($check.Trim() -ne 'ok') { throw "Integrity check failed for downloaded DB: $download" }

        $destDir = Split-Path $target.Local -Parent
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        Move-Item -Force $download $target.Local
        Write-Host "Refreshed: $($target.Local)"
    }

    Write-Host "DEV refresh completed from PROD backup: $stamp"
    Write-Host "Local pre-refresh backup: $localBackup"
}
finally {
    Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
