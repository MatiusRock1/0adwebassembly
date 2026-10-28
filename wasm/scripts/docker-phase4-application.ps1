param([ValidateSet('build', 'link')][string]$Action = 'build')
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$mounts = @()
foreach ($pair in @(@('wasm/scripts','/phase4-scripts'), @('wasm/harness','/phase4-harness'), @('wasm/browser','/phase4-browser'), @('wasm/build/phase4','/phase4-build'), @('wasm/dist/application-phase4','/phase4-dist'))) {
    $mounts += @('--mount', "type=bind,source=$(Join-Path $workspace $pair[0]),target=$($pair[1])")
}
$arguments = if ($Action -eq 'build') { @('/phase4-scripts/phase4-application-build.py','--output','/phase4-build','--audio') } else { @('/phase4-scripts/phase4-link.py','--build','/phase4-build','--output','/phase4-dist') }
& docker run --rm --network none --memory 8g --cpus 2 @mounts --entrypoint python3 0ad-wasm-phase4:dependencies @arguments
if ($LASTEXITCODE) { throw "Phase 4 $Action failed ($LASTEXITCODE)" }
