param([string]$Output = 'docs/wasm/evidence/phase3/windows-hardware.json')
$ErrorActionPreference = 'Stop'
$phase3Hardware = @{
    recordedAt = (Get-Date).ToUniversalTime().ToString('o')
    cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors)
    gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,DriverDate,AdapterRAM,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate)
    system = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory
    os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber
    powerPlan = (& powercfg /getactivescheme | Out-String).Trim()
    note = 'Correlacionar con renderer WebGL del informe: la GPU instalada no prueba aceleracion efectiva.'
}
New-Item -ItemType Directory -Force (Split-Path -Parent ([IO.Path]::GetFullPath($Output))) | Out-Null
$phase3Hardware | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $Output
