param([string]$Image = '0ad-wasm-phase3:o3-lto-cached')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$probePath = Join-Path $PSScriptRoot 'phase4-entry-probe.py'
$evidencePath = Join-Path $projectRoot 'docs/wasm/evidence/phase4/entry-probe'
New-Item -ItemType Directory -Force $evidencePath | Out-Null
$imageMetadata = & docker image inspect $Image
if ($LASTEXITCODE -ne 0) { throw 'Cached image unavailable; no image is pulled automatically.' }
$imageMetadata | Set-Content (Join-Path $evidencePath 'image.json') -Encoding utf8
& docker run --rm --network none --memory 8g --cpus 2 `
    --mount "type=bind,source=$probePath,target=/opt/phase4-entry-probe.py,readonly" `
    --mount "type=bind,source=$evidencePath,target=/evidence" `
    --entrypoint python3 $Image /opt/phase4-entry-probe.py --output /evidence
$probeExitCode = $LASTEXITCODE
$probeExitCode | Set-Content (Join-Path $evidencePath 'exit-code.txt')
if ($probeExitCode -ne 0) { throw "Application compile probe failed ($probeExitCode); inspect $evidencePath/report.json and logs." }
