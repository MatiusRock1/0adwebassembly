param([int]$MemoryGiB = 8)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$buildContext = Join-Path $projectRoot 'wasm'
$dockerFile = Join-Path $buildContext 'docker/spidermonkey.Dockerfile'
$evidenceDir = Join-Path $projectRoot 'docs/wasm/evidence/spidermonkey'
$artifactDir = Join-Path $projectRoot 'wasm/dist/headless'
$baselineId = & docker image ls --filter 'reference=0ad-wasm-native-baseline:phase1' --format '{{.ID}}'
if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar Docker.' }
if (-not $baselineId) {
    & docker buildx build --resource "memory=$($MemoryGiB)g" --build-arg NATIVE_JOBS=2 --target native-final --load -t 0ad-wasm-native-baseline:phase1 -f (Join-Path $buildContext 'docker/native.Dockerfile') $buildContext
    if ($LASTEXITCODE -ne 0) { throw 'Baseline nativo fallo.' }
}
& docker buildx build --resource "memory=$($MemoryGiB)g" --target phase1-evidence --output "type=local,dest=$evidenceDir" -f $dockerFile $buildContext
if ($LASTEXITCODE -ne 0) { throw 'Build de evidencia fallo.' }
$status = (Get-Content (Join-Path $evidenceDir 'parity/status.txt') -Raw).Trim()
if ($status -ne 'PARITY_PASSED') { throw "Paridad fallo: $status; revisar $evidenceDir" }
& docker buildx build --resource "memory=$($MemoryGiB)g" --target phase1-artifacts --output "type=local,dest=$artifactDir" -f $dockerFile $buildContext
if ($LASTEXITCODE -ne 0) { throw 'Exportacion de artefactos fallo.' }
Write-Host "100 turnos, RNG y promesas: paridad nativo/WASM OK. Artefactos: $artifactDir"
