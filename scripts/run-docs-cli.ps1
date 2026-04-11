<#
.SYNOPSIS
  Convert every supported file under docs/ using only md-* console commands.

.DESCRIPTION
  Writes results under docs/cli-output/<safe-basename>/.
  Requires: pip install -e ".[pdf,word,ppt,xlsx,image,text,archive]" from repo root (plus OCR/Tesseract for md-image if using tess).

.PARAMETER DocsDir
  Folder to scan (default: <repo>/docs).

.PARAMETER OutDir
  Parent folder for outputs (default: <DocsDir>/cli-output).

.PARAMETER ImageEngines
  Passed to md-image --engines (default: tess).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/run-docs-cli.ps1
#>
[CmdletBinding()]
param(
    [string] $DocsDir = "",
    [string] $OutDir = "",
    [string] $ImageEngines = "tess"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $DocsDir) { $DocsDir = Join-Path $RepoRoot "docs" }
$DocsDir = (Resolve-Path $DocsDir).Path
if (-not $OutDir) { $OutDir = Join-Path $DocsDir "cli-output" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Test-Cmd([string] $Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

$need = @("md-pdf", "md-word", "md-ppt", "md-xlsx", "md-image", "md-text", "md-zip")
$missing = @($need | Where-Object { -not (Test-Cmd $_) })
if ($missing.Count -gt 0) {
    Write-Error "Missing on PATH: $($missing -join ', '). From repo root: pip install -e `".[pdf,word,ppt,xlsx,image,text,archive]`""
}

function Safe-DirName([string] $base) {
    $s = $base -replace '[<>:"/\\|?*]', "_"
    if ([string]::IsNullOrWhiteSpace($s)) { $s = "file" }
    return $s.Trim("._")
}

$skipExt = @{
    ".md" = "already Markdown"
}

$files = Get-ChildItem -Path $DocsDir -Recurse -File -ErrorAction Stop |
    Where-Object { $_.FullName -notlike "*\cli-output\*" }

$exitCode = 0
foreach ($f in $files) {
    $ext = $f.Extension.ToLowerInvariant()
    if ($skipExt.ContainsKey($ext)) {
        Write-Host "[SKIP] $($f.Name) - $($skipExt[$ext])" -ForegroundColor DarkYellow
        continue
    }

    $stem = Safe-DirName $f.BaseName
    $destParent = Join-Path $OutDir $stem
    $rel = $f.FullName.Substring($DocsDir.Length).TrimStart('\', '/')
    Write-Host ""
    Write-Host "=== $rel ===" -ForegroundColor Cyan

    try {
        New-Item -ItemType Directory -Force -Path $destParent | Out-Null

        if ($ext -eq ".pdf") {
            & md-pdf $f.FullName $destParent --artifact-layout
            if ($LASTEXITCODE -ne 0) { throw "md-pdf exit $LASTEXITCODE" }
        }
        elseif ($ext -eq ".docx") {
            $md = Join-Path $destParent "document.md"
            $img = Join-Path $destParent "images"
            & md-word $f.FullName $md --images-dir $img
            if ($LASTEXITCODE -ne 0) { throw "md-word exit $LASTEXITCODE" }
        }
        elseif ($ext -eq ".pptx") {
            & md-ppt $f.FullName $destParent --artifact-layout --no-extract-embedded-deep
            if ($LASTEXITCODE -ne 0) { throw "md-ppt exit $LASTEXITCODE" }
        }
        elseif ($ext -eq ".xlsx" -or $ext -eq ".xlsm" -or $ext -eq ".csv") {
            & md-xlsx -i $f.FullName -o $destParent
            if ($LASTEXITCODE -ne 0) { throw "md-xlsx exit $LASTEXITCODE" }
        }
        elseif ($ext -eq ".zip") {
            & md-zip $f.FullName $destParent
            if ($LASTEXITCODE -ne 0) { throw "md-zip exit $LASTEXITCODE" }
        }
        elseif ($ext -eq ".json" -or $ext -eq ".xml" -or $ext -eq ".txt") {
            $md = Join-Path $destParent "document.md"
            & md-text $f.FullName $md
            if ($LASTEXITCODE -ne 0) { throw "md-text exit $LASTEXITCODE" }
        }
        elseif ($ext -in ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif") {
            $md = Join-Path $destParent "document.md"
            & md-image $f.FullName $md --engines $ImageEngines --strategy best --title $stem
            if ($LASTEXITCODE -ne 0) { throw "md-image exit $LASTEXITCODE" }
        }
        else {
            Remove-Item -LiteralPath $destParent -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "[SKIP] $($f.Name) - extension $ext not mapped to md-*" -ForegroundColor DarkYellow
            continue
        }
    }
    catch {
        Write-Host "[FAIL] $($f.Name): $_" -ForegroundColor Red
        $exitCode = 1
    }
}

Write-Host ""
Write-Host "Done. Outputs under: $OutDir" -ForegroundColor Green
exit $exitCode
