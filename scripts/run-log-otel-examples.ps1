<#
.SYNOPSIS
  Convert example/log and example/otel samples via md-log and md-otel.

.DESCRIPTION
  Writes Markdown under example/log/output/<lang>/ and example/otel/output/<name>/.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/run-log-otel-examples.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} elseif ($RepoRoot -isnot [string]) {
    $RepoRoot = $RepoRoot.ToString()
}

function Test-Cmd([string] $Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Cmd "md-log")) {
    Write-Error "md-log not on PATH. From repo root: pip install -e `".[log]`""
}
if (-not (Test-Cmd "md-otel")) {
    Write-Warning "md-otel not on PATH; skipping OTEL exports (pip install -e `".[log]`""
}

$LogRoot = Join-Path $RepoRoot "example\log"
$OtelRoot = Join-Path $RepoRoot "example\otel"
$LogOut = Join-Path $LogRoot "output"
$OtelOut = Join-Path $OtelRoot "output"
New-Item -ItemType Directory -Force -Path $LogOut, $OtelOut | Out-Null

# Build tar.gz archive example
$ArchDir = Join-Path $LogRoot "archives"
New-Item -ItemType Directory -Force -Path $ArchDir | Out-Null
python -c @"
import tarfile, io
from pathlib import Path
p = Path(r'$ArchDir') / 'multi-service.tar.gz'
with tarfile.open(p, 'w:gz') as tar:
    for name, body in [
        ('api/gateway.log', b'2024-06-01T17:00:00Z INFO gateway user=@archive_user ip=10.0.0.1\n'),
        ('worker/queue.log', b'2024-06-01T17:00:01Z ERROR worker job=retry from [::1]\n'),
    ]:
        data = body
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
print('wrote', p)
"@

$langs = @(
    @{ Name = "python"; Preset = "generic"; Input = "python\app.log" },
    @{ Name = "node"; Preset = "generic"; Input = "node\app.log" },
    @{ Name = "java"; Preset = "generic"; Input = "java\app.log" },
    @{ Name = "spring"; Preset = "springboot"; Input = "spring\app.log" },
    @{ Name = "go"; Preset = "generic"; Input = "go\app.log" },
    @{ Name = "php"; Preset = "generic"; Input = "php\app.log" },
    @{ Name = "cpp"; Preset = "generic"; Input = "cpp\app.log" },
    @{ Name = "frappe"; Preset = "generic"; Input = "frappe\app.log" },
    @{ Name = "liferay"; Preset = "generic"; Input = "liferay\app.log" },
    @{ Name = "logback"; Preset = "logback"; Input = "logback\app.log" },
    @{ Name = "json"; Preset = "json"; Input = "json\app.jsonl" },
    @{ Name = "json-logstash"; Preset = "json"; Input = "json\logstash.jsonl" },
    @{ Name = "json-ecs"; Preset = "json"; Input = "json\ecs.jsonl" },
    @{ Name = "json-mixed"; Preset = "json"; Input = "json\mixed.log" }
)

$summary = @()
foreach ($lang in $langs) {
    $inPath = Join-Path $LogRoot $lang.Input
    $outPath = Join-Path $LogOut $lang.Name
    if (-not (Test-Path $inPath)) {
        Write-Warning "Skip missing $($lang.Input)"
        continue
    }
    Write-Host "md-log $($lang.Name) ..."
    $args = @(
        "--input", $inPath,
        "--output", $outPath,
        "--preset", $lang.Preset,
        "--frontmatter"
    )
    & md-log @args 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Write-Warning "md-log failed for $($lang.Name); exit=$LASTEXITCODE" }
    $summary += [PSCustomObject]@{ Type = "log"; Name = $lang.Name; Output = $outPath }
}

# Archive ingest
$tarPath = Join-Path $ArchDir "multi-service.tar.gz"
if (Test-Path $tarPath) {
    $outArch = Join-Path $LogOut "archive-tar"
    Write-Host "md-log archive (tar.gz) ..."
    & md-log --input $tarPath --output $outArch --preset generic --frontmatter 2>&1 | Out-Host
    if ($LASTEXITCODE -eq 0) {
        $summary += [PSCustomObject]@{ Type = "log"; Name = "archive-tar"; Output = $outArch }
    } else {
        Write-Warning "md-log archive-tar failed"
    }
}

# OTEL exports
if (Test-Cmd "md-otel") {
    foreach ($otelFile in @("otlp-traces.json", "otlp-logs.json")) {
        $inp = Join-Path $OtelRoot $otelFile
        if (-not (Test-Path $inp)) { continue }
        $base = [System.IO.Path]::GetFileNameWithoutExtension($otelFile)
        $out = Join-Path $OtelOut $base
        Write-Host "md-otel $base ..."
        & md-otel --input $inp --output $out 2>&1 | Out-Host
        $summary += [PSCustomObject]@{ Type = "otel"; Name = $base; Output = $out }
    }
}

# Cross-source: python log + otel dir
$pyOut = Join-Path $LogOut "python-cross"
Write-Host "md-log python + cross-source ..."
& md-log `
    --config (Join-Path $LogRoot "run-config.yaml") `
    --input (Join-Path $LogRoot "python\app.log") `
    --output $pyOut 2>&1 | Out-Host
$summary += [PSCustomObject]@{ Type = "log"; Name = "python-cross"; Output = $pyOut }

$manifest = Join-Path $LogOut "manifest.json"
$summary | ConvertTo-Json -Depth 3 | Set-Content -Path $manifest -Encoding utf8
Write-Host "Done. Manifest: $manifest"
exit 0
