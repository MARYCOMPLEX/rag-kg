param(
  [int]$BackendPort = 8013,
  [int]$FrontendPort = 5181,
  [string]$HostName = "127.0.0.1",
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$WebDir = Join-Path $Root "web"
$backend = "http://$HostName`:$BackendPort"
$frontend = "http://$HostName`:$FrontendPort"

function Get-Json($Uri) {
  $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 20
  if ($response.Headers["Content-Type"] -notmatch "application/json") {
    throw "$Uri returned $($response.Headers["Content-Type"]), expected application/json"
  }
  return $response.Content | ConvertFrom-Json
}

Write-Host "Checking backend $backend"
$health = Get-Json "$backend/healthz"
Write-Host "healthz: $($health.status)"

$libraries = Get-Json "$backend/api/libraries"
$libraryIds = @($libraries | ForEach-Object { $_.id })
if ($libraryIds -notcontains "rag-agent") {
  throw "rag-agent is missing from /api/libraries"
}
Write-Host "backend libraries include rag-agent"

Write-Host "Checking Vite proxy $frontend"
$proxyLibraries = Get-Json "$frontend/api/libraries"
$proxyIds = @($proxyLibraries | ForEach-Object { $_.id })
if ($proxyIds -notcontains "rag-agent") {
  throw "rag-agent is missing from proxied /api/libraries"
}
Write-Host "frontend proxy returns backend JSON"

Push-Location $WebDir
try {
  $env:VITE_DATA_SOURCE = "api"
  $env:VITE_API_PROXY_TARGET = $backend
  pnpm typecheck
  if (-not $SkipBuild) {
    pnpm build
  }
}
finally {
  Pop-Location
}

Write-Host "Local smoke verification passed."
