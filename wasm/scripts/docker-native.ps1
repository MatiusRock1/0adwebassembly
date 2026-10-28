param([int]$Jobs = 2, [int]$MemoryGiB = 8)
$ErrorActionPreference = 'Stop'
if ($Jobs -lt 1) { throw 'Jobs debe ser positivo.' }
if ($MemoryGiB -lt 1) { throw 'MemoryGiB debe ser positivo.' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$evidence = Join-Path $root 'docs/wasm/evidence'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$pin = (Get-Content (Join-Path $root 'BASE_COMMIT.txt') -Raw).Trim()
if ($pin -notmatch '^[0-9a-f]{40}$') { throw 'BASE_COMMIT invalido.' }
$dockerfile = Join-Path $root 'wasm/docker/native.Dockerfile'
$context = Join-Path $root 'wasm'
# Windows PowerShell 5 convierte stderr nativo en ErrorRecord; Docker usa
# stderr tambien para progreso normal. Evaluar el exit code del proceso.
$savedPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & docker buildx build --load --resource "memory=${MemoryGiB}g" --progress plain --target native-final --build-arg "BASE_COMMIT=$pin" --build-arg "NATIVE_JOBS=$Jobs" -t 0ad-wasm-native-baseline:phase1 -f $dockerfile $context 2>&1 | ForEach-Object { $_.ToString() } | Tee-Object -FilePath (Join-Path $evidence 'native-image-build.log')
    $buildExit = $LASTEXITCODE
} finally { $ErrorActionPreference = $savedPreference }
if ($buildExit -ne 0) { throw 'Build o tests fallaron; revisar native-image-build.log.' }
& docker image inspect 0ad-wasm-native-baseline:phase1 --format '{{.Id}}' | Set-Content (Join-Path $evidence 'native-image-id.txt')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo registrar la imagen.' }
& docker buildx build --resource "memory=${MemoryGiB}g" --progress plain --target native-evidence --build-arg "BASE_COMMIT=$pin" --build-arg "NATIVE_JOBS=$Jobs" --output "type=local,dest=$evidence" -f $dockerfile $context
if ($LASTEXITCODE -ne 0) { throw 'La imagen esta construida, pero fallo la exportacion de evidencia.' }
