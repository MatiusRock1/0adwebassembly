param([int]$Port = 8080, [string]$Directory = (Join-Path $PSScriptRoot "../dist/scene-browser"), [switch]$Background)
$ErrorActionPreference = 'Stop'
$sceneServerScript = Join-Path $PSScriptRoot 'serve-phase2.py'
$sceneServerDirectory = [System.IO.Path]::GetFullPath($Directory)
if ($Background) {
    $sceneServerEvidence = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../docs/wasm/evidence/phase2'))
    $sceneServerProcess = Start-Process -WindowStyle Hidden -FilePath (Get-Command python).Source -ArgumentList @('-u', ('"' + $sceneServerScript + '"'), '--directory', ('"' + $sceneServerDirectory + '"'), '--port', $Port) -RedirectStandardOutput (Join-Path $sceneServerEvidence 'localhost-server.log') -RedirectStandardError (Join-Path $sceneServerEvidence 'localhost-server-error.log') -PassThru
    @{ pid = $sceneServerProcess.Id; url = "http://localhost:$Port/scene.html"; directory = $sceneServerDirectory } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $sceneServerEvidence 'localhost-server.json')
    Write-Output "http://localhost:$Port/scene.html (PID $($sceneServerProcess.Id))"
} else {
    & python $sceneServerScript --port $Port --directory $sceneServerDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Servidor local fallo.' }
}
