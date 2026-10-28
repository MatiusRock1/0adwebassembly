param([int]$MemoryGiB = 8, [switch]$Verify, [switch]$NativeMap, [switch]$Audit, [switch]$LinkProbe, [switch]$Map, [switch]$Scene, [int]$SceneDurationSeconds = 900)
$ErrorActionPreference = 'Stop'
$arguments = @((Join-Path $PSScriptRoot 'phase2-build.py'), '--memory-gib', $MemoryGiB)
if ($Verify) { $arguments += '--verify' }
if ($NativeMap) { $arguments += '--native-map' }
if ($Audit) { $arguments += '--audit' }
if ($LinkProbe) { $arguments += '--link-probe' }
if ($Map) { $arguments += '--map' }
if ($Scene) { $arguments += @('--scene', '--scene-duration-seconds', $SceneDurationSeconds) }
& python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Fase 2 fallo; revisar docs/wasm/evidence/phase2.' }
