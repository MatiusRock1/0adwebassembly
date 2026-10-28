param([Alias('Profile')][ValidateSet('debug','o2','o3','o3-lto')][string]$BuildProfile = 'o2', [int]$MemoryGiB = 8, [switch]$VerifyParity, [Alias('Context')][ValidateSet('proxied','owned')][string]$ContextMode = 'proxied')
$ErrorActionPreference = 'Stop'
$phase3Arguments = @((Join-Path $PSScriptRoot 'phase3-build.py'), '--profile', $BuildProfile, '--context', $ContextMode, '--memory-gib', $MemoryGiB)
if ($VerifyParity) { $phase3Arguments += '--verify-parity' }
& python @phase3Arguments
if ($LASTEXITCODE -ne 0) { throw 'Fase 3 fallo; revisar docs/wasm/evidence/phase3.' }