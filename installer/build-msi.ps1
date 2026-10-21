# Builds dist\VVGenerator-<version>.msi on Windows. Requires the .NET SDK (8+).
param([string]$Version = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $Version) {
    $Version = (Get-Content "$root\VVGenerator\VVGenerator.manifest" -Raw | ConvertFrom-Json).version
}
if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
    dotnet tool install --global wix --version 4.0.5
    $env:PATH += ";$env:USERPROFILE\.dotnet\tools"
}
New-Item -ItemType Directory -Force -Path "$root\dist" | Out-Null
wix build "$root\installer\VVGenerator.wxs" -d Version=$Version -d SourceDir="$root\VVGenerator" -o "$root\dist\VVGenerator-$Version.msi"
Write-Host "Built: $root\dist\VVGenerator-$Version.msi"
