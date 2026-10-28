param(
    [ValidateSet('All','Functional','Performance','Plan')][string]$Mode = 'All',
    [ValidateSet('webgpu','webgl','native')][string[]]$Backends = @('webgpu','webgl','native'),
    [int]$Repetitions = 3,
    [int]$WarmupSeconds = 120,
    [int]$DurationSeconds = 900
)
$ErrorActionPreference = 'Stop'
$Backends = @($Backends | ForEach-Object { $_.ToLowerInvariant() })
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $workspace 'wasm/.venv-phase3/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing prepared Python/Playwright environment: wasm/.venv-phase3' }
Write-Host 'Ejecutor independiente sin Computer Use ni capturas durante las mediciones.'
Write-Host 'La prueba activa pantalla completa y verifica el foco real; mantenga el juego visible.'
Push-Location $workspace
try {
    if ($Mode -in @('All','Functional','Plan')) {
        $arguments = @((Join-Path $PSScriptRoot 'verify-phase4-5-standalone.py'))
        if ($Mode -eq 'Plan') { $arguments += '--dry-run' }
        & $python @arguments
        if ($LASTEXITCODE) { throw 'Functional checks failed; inspect the preserved evidence before measuring.' }
    }
    if ($Mode -in @('All','Performance','Plan')) {
        $arguments = @((Join-Path $PSScriptRoot 'benchmark-phase4-5-standalone.py'),
            '--repetitions', "$Repetitions", '--warmup-seconds', "$WarmupSeconds", '--duration-seconds', "$DurationSeconds", '--backends') + $Backends
        if ($Mode -eq 'Plan') { $arguments += '--dry-run' }
        & $python @arguments
        if ($LASTEXITCODE) { throw 'Measurement or performance gate failed; inspect summary.json and raw CSVs.' }
    }
} finally { Pop-Location }
