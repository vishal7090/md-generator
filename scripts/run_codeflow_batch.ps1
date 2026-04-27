$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Task\Project\md-generator"
$BaseOut = Join-Path $RepoRoot "docs\codeflow"
New-Item -ItemType Directory -Force -Path $BaseOut | Out-Null
$env:PYTHONPATH = Join-Path $RepoRoot "src"
Set-Location $RepoRoot

$projects = @(
    @{ Name = "document-qa"; Src = "C:\Task\Project\document-qa" },
    @{ Name = "BowlingGame"; Src = "C:\MyWork\workspace\BowlingGame" },
    @{ Name = "mtb"; Src = "C:\MyWork\workspace\mtb" },
    @{ Name = "react-design-patterns-2895130"; Src = "C:\MyWork\react_workspace\react-design-patterns-2895130" },
    @{ Name = "html-to-pdf-to-images"; Src = "C:\Task\Project\html-to-pdf-to-images" }
)

foreach ($p in $projects) {
    if (-not (Test-Path -LiteralPath $p.Src)) {
        Write-Host "SKIP (missing): $($p.Src)"
        continue
    }
    $out = Join-Path $BaseOut $p.Name
    Write-Host "=== SCAN $($p.Name) -> $out ==="
    $args = @(
        "-m", "md_generator.codeflow.cli.main", "scan",
        $p.Src,
        "--output", $out,
        "--formats", "md,mermaid,json,html",
        "--depth", "8",
        "--lang", "mixed"
    )
    & python @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED $($p.Name) exit $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}
Write-Host "Done. Output under $BaseOut"
