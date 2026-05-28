param(
  [int[]]$Ports = @(),
  [switch]$StopOrchestrator
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root ".agent-logs"

function Stop-Tree([int]$ProcessId) {
  $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $ProcessId }
  foreach ($child in $children) {
    Stop-Tree -ProcessId ([int]$child.ProcessId)
  }
  Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

$pidFiles = @("local-frontend.pid", "local-backend.pid", "local-worker.pid")
if ($StopOrchestrator) {
  $pidFiles += "issue-orchestrator.pid"
}

foreach ($pidFile in $pidFiles) {
  $path = Join-Path $LogDir $pidFile
  if (Test-Path $path) {
    $raw = Get-Content -Path $path -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($raw -match '^\d+$') {
      Stop-Tree -ProcessId ([int]$raw)
      Write-Host "Stopped PID $raw from $pidFile"
    }
  }
}

foreach ($port in $Ports) {
  $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
  foreach ($listener in $listeners) {
    Stop-Tree -ProcessId ([int]$listener.OwningProcess)
    Write-Host "Stopped listener on port $port, PID $($listener.OwningProcess)"
  }
}
