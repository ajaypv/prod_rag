param(
    [string]$Tenant = "demo",
    [string]$Product = "nimbusflow",
    [string]$Version = "1.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sampleRoot = Join-Path $projectRoot "samples\b2b-saas"
$queryFile = Join-Path $projectRoot "samples\b2b-saas-demo-queries.jsonl"

Set-Location $projectRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot ".uv-cache"

Write-Host "Ingesting fictional NimbusFlow documents..."
uv run prodrag ingest $sampleRoot --tenant $Tenant --product $Product --version $Version

Write-Host "Running demo queries..."
foreach ($line in Get-Content -LiteralPath $queryFile) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        continue
    }
    $case = $line | ConvertFrom-Json
    Write-Host ""
    Write-Host ("Purpose: " + $case.purpose)
    Write-Host ("Question: " + $case.question)
    uv run prodrag query $case.question --tenant $Tenant --product $Product --version $Version
}
