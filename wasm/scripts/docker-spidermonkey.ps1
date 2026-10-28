param([int]$MemoryGiB = 8)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$dockerFile = Join-Path $projectRoot 'wasm/docker/spidermonkey.Dockerfile'
$buildContext = Join-Path $projectRoot 'wasm'
$evidenceDir = Join-Path $projectRoot 'docs/wasm/evidence/spidermonkey'
& docker buildx build --resource "memory=$($MemoryGiB)g" --progress plain --target spike-runtime-evidence --output "type=local,dest=$evidenceDir" -f $dockerFile $buildContext
if ($LASTEXITCODE -ne 0) { throw 'Docker build fallo; revisar su diagnostico.' }
$status = (Get-Content -LiteralPath (Join-Path $evidenceDir 'runtime-status.txt') -Raw).Trim()
if ($status -ne 'RUNTIME_PROBE_PASSED') { throw "SpiderMonkey WASM: $status. Revisar los logs en $evidenceDir" }
Write-Host 'SpiderMonkey WASM: bindings C++/JS, GC y 3 contextos OK (Node).'
