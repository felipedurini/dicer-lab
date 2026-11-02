param([switch]$Stop)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv-web\Scripts\python.exe"
$webDir = Join-Path $projectRoot "apps\web"
$nextCli = Join-Path $webDir "node_modules\next\dist\bin\next"
$dataDir = Join-Path $projectRoot ".local\dicer-web"
$stateFile = Join-Path $dataDir "web-processes.json"
$apiLog = Join-Path $dataDir "api.log"
$apiErrorLog = Join-Path $dataDir "api-error.log"
$webLog = Join-Path $dataDir "web.log"
$webErrorLog = Join-Path $dataDir "web-error.log"

function Test-HttpReady([string]$Uri) {
  try { $null = Invoke-WebRequest -Uri $Uri -TimeoutSec 2 -UseBasicParsing; return $true }
  catch { return $false }
}

function Wait-HttpReady([string]$Uri, [int]$Seconds) {
  $until = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $until) {
    if (Test-HttpReady $Uri) { return $true }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

if ($Stop) {
  if (-not (Test-Path $stateFile)) { Write-Host "No hay procesos de Dicer Lab registrados para detener."; exit 0 }
  $state = Get-Content -Raw $stateFile | ConvertFrom-Json
  foreach ($entry in $state.processes) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.pid)" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -like "*$($entry.commandMatch)*") {
      & taskkill.exe /PID $entry.pid /T /F | Out-Null
      Write-Host "Detenido PID $($entry.pid) ($($entry.name))."
    }
  }
  Remove-Item -LiteralPath $stateFile -Force
  exit 0
}

if (-not (Test-Path $pythonExe)) {
  Write-Host "Creando el entorno Python del proyecto..."
  & py -3.13 -m venv --clear (Join-Path $projectRoot ".venv-web")
  if ($LASTEXITCODE -ne 0) { throw "No se pudo crear .venv-web con Python 3.13. Instala Python 3.13 y vuelve a ejecutar este script." }
}

if (-not (Test-Path $pythonExe)) { throw "No se encontro Python en $pythonExe" }
& $pythonExe -c "import fastapi, numpy, jwt, uvicorn"
if ($LASTEXITCODE -ne 0) {
  Write-Host "Instalando dependencias cientificas y del API..."
  & $pythonExe -m pip install -r (Join-Path $projectRoot "requirements.txt")
  if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de requirements.txt" }
  & $pythonExe -m pip install --require-hashes -r (Join-Path $projectRoot "services\simulator_api\requirements.lock")
  if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de requirements.lock" }
}

$node = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $node) { throw "No se encontro Node.js. Instala Node.js 24 y vuelve a ejecutar este script." }
if (-not (Test-Path $nextCli)) {
  $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if (-not $npm) { throw "No se encontro npm.cmd para instalar la interfaz web." }
  Write-Host "Instalando dependencias de la interfaz web..."
  Push-Location $projectRoot
  try { & $npm.Source --prefix apps/web ci; if ($LASTEXITCODE -ne 0) { throw "Fallo npm ci" } }
  finally { Pop-Location }
}

New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
$started = @()

try {
  if (-not (Test-HttpReady "http://127.0.0.1:8000/health/live")) {
    $api = Start-Process -FilePath $pythonExe -ArgumentList "-m services.simulator_api" -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $apiLog -RedirectStandardError $apiErrorLog -PassThru
    $started += [pscustomobject]@{ pid = $api.Id; name = "API Python"; commandMatch = "services.simulator_api" }
    if (-not (Wait-HttpReady "http://127.0.0.1:8000/health/live" 45)) { throw "El API Python no respondio en 45 s. Revisa $apiErrorLog" }
  }

  if (-not (Test-HttpReady "http://127.0.0.1:3000/lab")) {
    $web = Start-Process -FilePath $node.Source -ArgumentList "`"$nextCli`" dev --hostname 127.0.0.1" -WorkingDirectory $webDir -WindowStyle Hidden -RedirectStandardOutput $webLog -RedirectStandardError $webErrorLog -PassThru
    $started += [pscustomobject]@{ pid = $web.Id; name = "Next.js"; commandMatch = "next\dist\bin\next" }
    if (-not (Wait-HttpReady "http://127.0.0.1:3000/lab" 90)) { throw "Next.js no respondio en 90 s. Revisa $webErrorLog" }
  }

  $preview = @{
    web_schema_version = 1
    construct = @{
      length_nt = 315; phase_origin_nt = 0
      segments = @(
        @{ segment_id = "seg_a"; gene_id = "gene_a"; start = 0; end = 105 },
        @{ segment_id = "seg_b"; gene_id = "gene_b"; start = 105; end = 210 },
        @{ segment_id = "seg_c"; gene_id = "gene_c"; start = 210; end = 315 }
      )
    }
    p22 = 0.5; f_left = 0.5; seed = 101
    epsilon = @{ type = "constant"; schema_version = 1; epsilon = 0.1 }
  }
  $json = $preview | ConvertTo-Json -Depth 8 -Compress
  $result = Invoke-RestMethod -Uri "http://127.0.0.1:3000/api/v1/trajectories" -Method Post -ContentType "application/json" -Body $json -TimeoutSec 30
  if ($result.events.Count -lt 1 -or -not $result.trajectory_hash) { throw "El preview BFF/API no devolvio una trayectoria valida." }

  $existing = @()
  if (Test-Path $stateFile) { $existing = @((Get-Content -Raw $stateFile | ConvertFrom-Json).processes) }
  $combined = @($existing + $started)
  @{ processes = $combined } | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $stateFile
  Write-Host "Dicer Lab esta funcionando. Preview real: $($result.events.Count) eventos, hash $($result.trajectory_hash.Substring(0, 12))."
  Write-Host "API:      http://127.0.0.1:8000"
  Write-Host "Frontend: http://127.0.0.1:3000/lab"
  Write-Host "Logs:     $dataDir"
  Start-Process "http://127.0.0.1:3000/lab"
}
catch {
  foreach ($entry in $started) { Stop-Process -Id $entry.pid -Force -ErrorAction SilentlyContinue }
  throw
}
