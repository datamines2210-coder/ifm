param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path $ProjectRoot).Path.TrimEnd([char[]]@('\','/'))
$docsRoot = Join-Path $ProjectRoot 'docs'
$docsPrefix = $docsRoot.TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
New-Item -ItemType Directory -Force -Path $docsRoot | Out-Null

function Test-IsExcludedMarkdownPath {
    param([string]$FullName)

    # docs/ is already compliant. Ignore generated/dependency/cache trees.
    if ($FullName.StartsWith($docsPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    return ($FullName -match '[\\/](\.venv|venv|node_modules|\.git|__pycache__)[\\/]')
}

$files = Get-ChildItem -Path $ProjectRoot -Recurse -File -Filter '*.md' | Where-Object {
    -not (Test-IsExcludedMarkdownPath $_.FullName)
}

$moved = 0
$deduplicated = 0
foreach ($file in $files) {
    # TrimStart requires Char values. Supplying "\\" as a string causes the
    # Windows PowerShell conversion error fixed by this hot patch.
    $relative = $file.FullName.Substring($ProjectRoot.Length).TrimStart([char[]]@('\','/'))
    if ([string]::IsNullOrWhiteSpace($relative)) {
        continue
    }

    $destination = Join-Path $docsRoot $relative
    $destinationDir = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

    if (Test-Path -LiteralPath $destination) {
        $srcHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash
        $dstHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash
        if ($srcHash -eq $dstHash) {
            Remove-Item -Force -LiteralPath $file.FullName
            $deduplicated++
            continue
        }
        throw "Refusing to overwrite different Markdown file: $destination"
    }

    Move-Item -LiteralPath $file.FullName -Destination $destination
    $moved++
}

Write-Host "Markdown organization complete. Moved $moved file(s); removed $deduplicated duplicate(s)." -ForegroundColor Green
Write-Host "Markdown root: $docsRoot" -ForegroundColor Green

$remaining = Get-ChildItem -Path $ProjectRoot -Recurse -File -Filter '*.md' | Where-Object {
    -not (Test-IsExcludedMarkdownPath $_.FullName)
}
if ($remaining) {
    Write-Host 'Markdown files still outside docs/:' -ForegroundColor Yellow
    $remaining.FullName | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host 'Validated: no project Markdown files remain outside docs/.' -ForegroundColor Cyan
