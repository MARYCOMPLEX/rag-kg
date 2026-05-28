param(
  [int]$BackendPort = 8013,
  [int]$FrontendPort = 5181,
  [string]$BackendHost = "127.0.0.1",
  [switch]$StartInfra
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ServeDir = Join-Path $Root "serve"
$WebDir = Join-Path $Root "web"
$LogDir = Join-Path $Root ".agent-logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Assert-PortFree([int]$Port) {
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if ($listener) {
    $pidList = ($listener | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
    throw "Port $Port is already in use by PID(s): $pidList"
  }
}

Assert-PortFree $BackendPort
Assert-PortFree $FrontendPort

if ($StartInfra) {
  Push-Location $ServeDir
  try {
    docker compose -f infra/docker-compose.yml up -d
  }
  finally {
    Pop-Location
  }
}

Push-Location $ServeDir
try {
  if (-not (Test-Path ".venv")) {
    uv sync
  }
}
finally {
  Pop-Location
}

Push-Location $WebDir
try {
  if (-not (Test-Path "node_modules")) {
    pnpm install
  }
}
finally {
  Pop-Location
}

$backendUrl = "http://$BackendHost`:$BackendPort"

$backendCmd = @"
`$env:NO_PROXY='localhost,127.0.0.1,::1'
`$env:no_proxy='localhost,127.0.0.1,::1'
Set-Location -LiteralPath '$ServeDir'
uv run uvicorn apps.api.main:app --host $BackendHost --port $BackendPort
"@

$backend = Start-Process -FilePath "powershell.exe" `
  -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd) `
  -RedirectStandardOutput (Join-Path $LogDir "local-backend-$BackendPort.out.log") `
  -RedirectStandardError (Join-Path $LogDir "local-backend-$BackendPort.err.log") `
  -WindowStyle Hidden `
  -PassThru
Set-Content -Path (Join-Path $LogDir "local-backend.pid") -Value $backend.Id

$workerCmd = @"
`$env:NO_PROXY='localhost,127.0.0.1,::1'
`$env:no_proxy='localhost,127.0.0.1,::1'
Set-Location -LiteralPath '$ServeDir'
uv run arq apps.worker.main.WorkerSettings
"@

$worker = Start-Process -FilePath "powershell.exe" `
  -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $workerCmd) `
  -RedirectStandardOutput (Join-Path $LogDir "local-worker.out.log") `
  -RedirectStandardError (Join-Path $LogDir "local-worker.err.log") `
  -WindowStyle Hidden `
  -PassThru
Set-Content -Path (Join-Path $LogDir "local-worker.pid") -Value $worker.Id

$frontendCmd = @"
`$env:VITE_DATA_SOURCE='api'
`$env:VITE_API_PROXY_TARGET='$backendUrl'
Set-Location -LiteralPath '$WebDir'
pnpm dev --host $BackendHost --port $FrontendPort
"@

$frontend = Start-Process -FilePath "powershell.exe" `
  -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $frontendCmd) `
  -RedirectStandardOutput (Join-Path $LogDir "local-frontend-$FrontendPort.out.log") `
  -RedirectStandardError (Join-Path $LogDir "local-frontend-$FrontendPort.err.log") `
  -WindowStyle Hidden `
  -PassThru
Set-Content -Path (Join-Path $LogDir "local-frontend.pid") -Value $frontend.Id

Write-Host "Backend API:  $backendUrl"
Write-Host "Worker PID:   $($worker.Id)"
Write-Host "Frontend UI:  http://$BackendHost`:$FrontendPort"
Write-Host "Logs:         $LogDir"
Write-Host "Run scripts/verify-local.ps1 -BackendPort $BackendPort -FrontendPort $FrontendPort to smoke test."
