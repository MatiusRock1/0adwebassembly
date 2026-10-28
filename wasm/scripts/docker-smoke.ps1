$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$image = 'emscripten/emsdk:4.0.10'
& docker info --format '{{.OSType}}'
if ($LASTEXITCODE -ne 0) { throw 'No se puede acceder a Docker Desktop. Ejecutar desde PowerShell con acceso a Docker.' }
# /src evita el espacio en la ruta Windows; no se modifica la carpeta original.
& docker run --rm --mount "type=bind,source=$root,target=/src" --workdir /src $image bash wasm/scripts/build-smoke.sh
if ($LASTEXITCODE -ne 0) { throw 'La prueba WASM fallo; revisar wasm/dist/smoke-build.log si se genero.' }
& docker image inspect $image --format '{{json .RepoDigests}}' | Set-Content (Join-Path $root 'wasm/dist/docker-image-digests.txt')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo registrar el digest de la imagen.' }
