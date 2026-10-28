param([ValidateSet('toolchain', 'bindings', 'shader-toolchain', 'shaders', 'engine', 'engine-wasm-eh', 'engine-audio-error', 'engine-audio-after-present', 'engine-audio-worker', 'engine-timer-monotonic', 'engine-simd', 'engine-browser-perf', 'engine-ai-worker', 'engine-transfer', 'scripting', 'link', 'link-wasm-eh', 'link-audio-error', 'link-audio-after-present', 'link-audio-worker', 'link-timer-monotonic', 'link-simd', 'link-browser-perf', 'link-ai-worker', 'link-transfer', 'package', 'all')][string]$Action = 'bindings',
      [ValidateSet('cached','hot-o2','hot-o3','portable','portable-hot-o2','portable-hot-o3','portable-fixed-o3','portable-switch-o2','portable-switch-o3','portable-underflow-o3','portable-cache-count-o3','portable-guards-o3')][string]$ScriptingProfile = 'cached')
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$output = Join-Path $workspace 'wasm/build/phase4-5'
New-Item -ItemType Directory -Force $output | Out-Null
$lock = Get-Content -Raw (Join-Path $workspace 'wasm/docker/phase4-5-toolchain.lock.json') | ConvertFrom-Json
if ($Action -eq 'all') {
    $steps = @('toolchain','shader-toolchain','shaders','engine')
    if ($ScriptingProfile -ne 'cached') { $steps += 'scripting' }
    $steps += @('link','package')
    foreach ($step in $steps) { & $PSCommandPath -Action $step -ScriptingProfile $ScriptingProfile }
    return
}
if ($Action -eq 'package') {
    & python (Join-Path $PSScriptRoot 'phase4-5-package.py')
    if ($LASTEXITCODE) { throw 'WebGPU packaging failed' }
    return
}
if ($Action -in @('shaders','engine','engine-wasm-eh','engine-audio-error','engine-audio-after-present','engine-audio-worker','engine-timer-monotonic', 'engine-simd', 'engine-browser-perf', 'engine-ai-worker', 'engine-transfer','scripting','link','link-wasm-eh','link-audio-error','link-audio-after-present','link-audio-worker','link-timer-monotonic', 'link-simd', 'link-browser-perf', 'link-ai-worker', 'link-transfer')) {
    $mounts = @('--mount', "type=bind,source=$workspace,target=/workspace,readonly",
                '--mount', "type=bind,source=$output,target=/phase45-build",
                '--mount', "type=bind,source=$(Join-Path $workspace 'wasm/build/phase4'),target=/phase4-build,readonly",
                '--mount', "type=bind,source=$(Join-Path $workspace 'wasm/browser'),target=/phase4-browser,readonly",
                '--mount', "type=bind,source=$(Join-Path $workspace 'wasm/harness'),target=/phase4-harness,readonly")
    if ($Action -eq 'scripting' -and $ScriptingProfile.StartsWith('portable')) {
        # Mozilla exports both String.h and string.h. Build on Linux rather
        # than collapse these distinct wrappers on a Windows bind mount.
        $previousPortable = Join-Path $output 'spidermonkey-portable/build'
        if (Test-Path -LiteralPath $previousPortable) {
            $mounts += @('--mount',"type=bind,source=$previousPortable,target=/portable-previous,readonly")
        }
        $mounts += @('--mount','type=volume,source=0ad-phase45-spidermonkey-portable,target=/phase45-build/spidermonkey-portable/build')
    }
    $runner = @('run','--rm','--network','none','--memory','8g','--cpus','2') + $mounts + @('--entrypoint','python3','0ad-wasm-phase4-5:shaders')
    if ($Action -eq 'shaders') {
        & docker @runner /workspace/wasm/scripts/phase4-5-scene-requests.py
        if ($LASTEXITCODE) { throw 'Material shader request generation failed' }
        & docker @runner /workspace/wasm/scripts/phase4-5-shaders.py
        if ($LASTEXITCODE) { throw 'Base WGSL shader conversion failed' }
        & docker @runner /workspace/wasm/scripts/phase4-5-shaders.py --requests /phase45-build/scene-requests.json
    } elseif ($Action -eq 'engine') {
        & docker @runner /workspace/wasm/scripts/phase4-5-engine-build.py
    } elseif ($Action -eq 'engine-wasm-eh') {
        $nativeScriptingLibrary = if ($ScriptingProfile -eq 'cached') { '/spike/mozjs-128.13.0/build-wasm/js/src/build/libjs_static.a' } else { "/phase45-build/spidermonkey-$ScriptingProfile/libjs_static.a" }
        & docker @runner /workspace/wasm/scripts/phase4-5-wasm-eh-build.py --spidermonkey-library $nativeScriptingLibrary
    } elseif ($Action -eq 'engine-audio-error') {
        & docker @runner /workspace/wasm/scripts/phase4-5-audio-error-build.py
    } elseif ($Action -eq 'engine-audio-after-present') {
        & docker @runner /workspace/wasm/scripts/phase4-5-audio-error-build.py --after-present
    } elseif ($Action -eq 'engine-audio-worker') {
        & docker @runner /workspace/wasm/scripts/phase4-5-audio-error-build.py --worker-ensure
    } elseif ($Action -eq 'engine-timer-monotonic') {
        & docker @runner /workspace/wasm/scripts/phase4-5-timer-build.py
    } elseif ($Action -eq 'engine-simd') {
        & docker @runner /workspace/wasm/scripts/phase4-5-simd-build.py
    } elseif ($Action -eq 'engine-transfer') {
        & docker @runner /workspace/wasm/scripts/phase4-5-transfer-build.py
    } elseif ($Action -eq 'engine-ai-worker') {
        & docker @runner /workspace/wasm/scripts/phase4-5-ai-worker-build.py
    } elseif ($Action -eq 'engine-browser-perf') {
        & docker @runner /workspace/wasm/scripts/phase4-5-browser-perf-build.py
    } elseif ($Action -eq 'scripting') {
        if ($ScriptingProfile -eq 'portable') {
            & docker @runner /workspace/wasm/scripts/phase4-5-portable-scripting-build.py
        } elseif ($ScriptingProfile -eq 'portable-fixed-o3') {
            & docker @runner /workspace/wasm/scripts/phase4-5-scripting-build.py --portable --optimization O3 --upstream-dispatch-fix
        } elseif ($ScriptingProfile -eq 'portable-underflow-o3') {
            & docker @runner /workspace/wasm/scripts/phase4-5-scripting-build.py --portable --optimization O3 --upstream-dispatch-fix --switch-dispatch --call-underflow
        } elseif ($ScriptingProfile -eq 'portable-guards-o3') {
            & docker @runner /workspace/wasm/scripts/phase4-5-scripting-build.py --portable --optimization O3 --upstream-dispatch-fix --switch-dispatch --pure-cacheir-guards
        } elseif ($ScriptingProfile -eq 'portable-cache-count-o3') {
            & docker @runner /workspace/wasm/scripts/phase4-5-scripting-build.py --portable --optimization O3 --upstream-dispatch-fix --switch-dispatch --missing-cacheop-counts
        } elseif ($ScriptingProfile -in @('portable-switch-o2','portable-switch-o3')) {
            $switchOptimization = if ($ScriptingProfile -eq 'portable-switch-o2') { 'O2' } else { 'O3' }
            & docker @runner /workspace/wasm/scripts/phase4-5-scripting-build.py --portable --optimization $switchOptimization --upstream-dispatch-fix --switch-dispatch
        } elseif ($ScriptingProfile.StartsWith('portable-hot-')) {
            $portableOptimization = if ($ScriptingProfile -eq 'portable-hot-o2') { 'O2' } else { 'O3' }
            & docker @runner /workspace/wasm/scripts/phase4-5-scripting-build.py --portable --optimization $portableOptimization
        } else {
            $optimization = if ($ScriptingProfile -eq 'hot-o2') { 'O2' } else { 'O3' }
            & docker @runner /workspace/wasm/scripts/phase4-5-scripting-build.py --optimization $optimization
        }
    } else {
        New-Item -ItemType Directory -Force (Join-Path $output 'linked') | Out-Null
        $scriptingArgs = @()
        if ($ScriptingProfile -ne 'cached') { $scriptingArgs = @('--spidermonkey-library',"/phase45-build/spidermonkey-$ScriptingProfile/libjs_static.a") }
        if ($Action -in @('link-wasm-eh','link-audio-error','link-audio-after-present','link-audio-worker','link-timer-monotonic', 'link-simd', 'link-browser-perf', 'link-ai-worker', 'link-transfer')) {
            $nativeVariant = if ($Action -eq 'link-transfer') { 'transfer' } elseif ($Action -eq 'link-ai-worker') { 'ai-worker' } elseif ($Action -eq 'link-browser-perf') { 'browser-perf' } elseif ($Action -eq 'link-simd') { 'simd' } elseif ($Action -eq 'link-timer-monotonic') { 'timer-monotonic' } elseif ($Action -eq 'link-audio-worker') { 'audio-worker' } elseif ($Action -eq 'link-audio-after-present') { 'audio-after-present' } elseif ($Action -eq 'link-audio-error') { 'audio-error' } else { 'wasm-eh' }
            New-Item -ItemType Directory -Force (Join-Path $output "linked-$nativeVariant") | Out-Null
            $browserArgs = @()
            if ($Action -in @('link-browser-perf','link-ai-worker','link-transfer')) { $browserArgs = @('--jspi') }
            & docker @runner /workspace/wasm/scripts/phase4-link.py --build "/phase45-build/application-$nativeVariant" --output "/phase45-build/linked-$nativeVariant" --release --exception-mode wasm @scriptingArgs @browserArgs
        } else {
            & docker @runner /workspace/wasm/scripts/phase4-link.py --build /phase45-build/application --output /phase45-build/linked --release @scriptingArgs
        }
    }
    if ($LASTEXITCODE) { throw "WebGPU $Action failed ($LASTEXITCODE)" }
    return
}
if ($Action -eq 'shader-toolchain') {
    & docker build --memory 8g -f (Join-Path $workspace 'wasm/docker/Dockerfile.phase4-5-shaders') -t 0ad-wasm-phase4-5:shaders (Join-Path $workspace 'wasm/docker')
    if ($LASTEXITCODE) { throw 'Shader toolchain build failed' }
    & docker image inspect 0ad-wasm-phase4-5:shaders --format '{{.Id}}' | Set-Content (Join-Path $output 'shader-toolchain-image-id.txt')
    return
}
if ($Action -eq 'toolchain') {
    $actualBase = & docker image inspect $lock.baseImage --format '{{.Id}}'
    if ($LASTEXITCODE -or $actualBase -ne $lock.baseImageId) { throw 'Phase 4 base image differs from the lock; review the toolchain before rebuilding.' }
    # Windows PowerShell treats Docker's normal progress on stderr as errors.
    # Preserve the log and judge the native command by its exit code.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker build --memory 8g -f (Join-Path $workspace 'wasm/docker/Dockerfile.phase4-5-toolchain') -t 0ad-wasm-phase4-5:toolchain (Join-Path $workspace 'wasm/docker') 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath (Join-Path $output 'toolchain-build.log')
    } finally { $ErrorActionPreference = $previousPreference }
} else {
    & docker run --rm --network none --memory 8g --cpus 2 `
        --mount "type=bind,source=$(Join-Path $workspace 'wasm/scripts'),target=/phase45-scripts,readonly" `
        --mount "type=bind,source=$(Join-Path $workspace 'wasm/probes'),target=/phase45-probes,readonly" `
        --mount "type=bind,source=$(Join-Path $workspace 'wasm/docker'),target=/phase45-config,readonly" `
        --mount "type=bind,source=$output,target=/phase45-build" `
        --entrypoint python3 0ad-wasm-phase4-5:toolchain /phase45-scripts/phase4-5-bindings.py
}
if ($LASTEXITCODE) { throw "Phase 4.5 $Action failed ($LASTEXITCODE)" }
& docker image inspect 0ad-wasm-phase4-5:toolchain --format '{{.Id}}' | Set-Content (Join-Path $output 'toolchain-image-id.txt')
if ($LASTEXITCODE) { throw 'Could not record the toolchain image ID' }
