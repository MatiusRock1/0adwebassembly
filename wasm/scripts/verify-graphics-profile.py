"""Automatic graphics profile in the installed Chrome, on the GPU Windows assigns to it.

Chrome starts without --force-high-performance-gpu (unless that option is
given), so the per-app GPU preference of Windows decides the adapter. Each run
starts the original menus with ?graphics=<mode> and records the detected GPU,
the chosen profile, config/local.cfg, the effective settings (the ConfigDB
"user" view: default.cfg, local.cfg and user.cfg) and the GPU guide of the page,
on load and after the start. --check-user-override saves one option to
user.cfg, restarts and checks that it wins over local.cfg. A run marked
":measure" opens the benchmark match in fullscreen (1920x1080) and records
engine frames and the 3D engine use of Chrome's GPU process (Windows GPU counters).
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
import traceback
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

os.environ.setdefault('SCENE_AUTO_FULLSCREEN', '1')
from benchmark_lock import BenchmarkLock
from phase4_flow import open_original_match
from phase4_workload import MANIFEST, populate
from phase4_browser import enter_fullscreen, observe_shutdown
from phase45_window_focus import activate_browser_window

ROOT = Path(__file__).resolve().parents[2]
KEYS = ['shadows', 'shadowquality', 'shadowpcf', 'textures.quality', 'textures.maxanisotropy', 'postproc',
        'antialiasing', 'sharpening', 'smoothlos', 'watereffects', 'waterfancyeffects', 'waterrealdepth',
        'waterreflection', 'waterrefraction', 'max_actor_quality', 'materialmgr.quality', 'particles',
        'silhouettes', 'fog', 'gpuskinning']
RENDERER_ERRORS = ('missing-shader-variant', 'uncaptured-error', 'validation-error', 'engine-device-lost')
GUIDE_STATE = '''()=>{const panel=document.querySelector('#gpu-guide');
  if(panel.hidden)return {guide:null};
  return {guide:[...panel.querySelectorAll('[data-guide]')].find(part=>!part.hidden).dataset.guide,
    openOS:[...panel.querySelectorAll('[data-os]')].filter(section=>section.open).map(section=>section.dataset.os),
    title:panel.querySelector(':scope>summary').textContent};}'''


def wait_url(url, process, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Child exited before becoming ready: ' + url)
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.2)
    raise TimeoutError(url)


def config_value(value):
    """A launcher setting as ConfigDB_GetValue returns it."""
    return 'true' if value is True else 'false' if value is False else str(value)


def default_values(package):
    """Top-level values of the packaged default.cfg (before its first section)."""
    values = {}
    for line in (package / 'data/config/default.cfg').read_text(encoding='utf-8').splitlines():
        line = line.split(';', 1)[0].strip()
        if line.startswith('['):
            break
        if '=' in line:
            key, value = (part.strip() for part in line.split('=', 1))
            if key in KEYS:
                values[key] = value.strip('"')
    return values


def gpu_preference():
    """Windows' per-app GPU preference of the installed Chrome (1 = power saving, 2 = high performance)."""
    command = ('(Get-ItemProperty -Path "HKCU:\\Software\\Microsoft\\DirectX\\UserGpuPreferences" -ErrorAction SilentlyContinue)'
               '."C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"')
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True,
                            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    return result.stdout.strip() or None


def start_gpu_counter(process_id, seconds):
    """Sample the 3D engine use of one process once per second, per adapter."""
    script = (f'Get-Counter -Counter "\\GPU Engine(pid_{process_id}_*engtype_3D)\\Utilization Percentage" '
              f'-SampleInterval 1 -MaxSamples {seconds} | ForEach-Object {{ ,@($_.CounterSamples | '
              'ForEach-Object { [pscustomobject]@{ i = $_.InstanceName; u = $_.CookedValue } }) } | ConvertTo-Json -Depth 4 -Compress')
    return subprocess.Popen(['powershell', '-NoProfile', '-Command', script], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)


def gpu_counter_result(process):
    try:
        output, errors = process.communicate(timeout=60)
        samples = json.loads(output) if output.strip() else []
    except Exception as error:  # Diagnostic only; the frame metrics do not depend on it.
        return dict(error=str(error))
    adapters = {}
    for sample in samples:
        totals = {}
        # Windows PowerShell 5.1 serializes each per-sample array as {"value": [...], "Count": n}.
        instances = sample['value'] if isinstance(sample, dict) and 'value' in sample else sample
        for instance in (instances if isinstance(instances, list) else [instances]):
            luid = '_'.join(instance['i'].split('_luid_')[1].split('_')[:2])
            totals[luid] = totals.get(luid, 0) + instance['u']
        for luid, total in totals.items():
            adapters.setdefault(luid, []).append(total)
    return dict(samples=len(samples), errors=errors.strip() or None,
                meanUtilizationPercent={luid: round(statistics.mean(values), 1) for luid, values in adapters.items()},
                p95UtilizationPercent={luid: round(sorted(values)[max(0, math.ceil(.95 * len(values)) - 1)], 1)
                                       for luid, values in adapters.items()})


def frame_metrics(frames):
    times = [frame['receivedMs'] for frame in frames]
    intervals = sorted(b - a for a, b in zip(times, times[1:]))
    if len(intervals) < 10:
        return dict(frames=len(frames), error='Too few frames')
    quantile = lambda q: round(intervals[min(len(intervals) - 1, int(q * len(intervals)))], 2)
    return dict(frames=len(frames), seconds=round((times[-1] - times[0]) / 1000, 2),
                fps=round((len(times) - 1) * 1000 / (times[-1] - times[0]), 2),
                intervalMs=dict(p50=quantile(.5), p95=quantile(.95), p99=quantile(.99), max=round(intervals[-1], 2)),
                intervalsOver50ms=sum(value > 50 for value in intervals), intervalsOver100ms=sum(value > 100 for value in intervals),
                updateMsMedian=round(statistics.median(frame['updateMilliseconds'] for frame in frames), 2),
                pausedFrames=sum(bool(frame['paused']) for frame in frames))


def start_game(page, url, backend):
    """Returns the GPU guide the page showed before the start."""
    page.goto(url)
    guide = page.evaluate(GUIDE_STATE)
    page.locator('#renderer-backend').select_option('webgpu' if backend == 'webgpu' else 'webgl')
    page.locator('#start').click()
    # The first start fills the IndexedDB block cache from the local server.
    page.wait_for_function('window.application?.applicationState?.frame > 0 || window.applicationResult', timeout=900000)
    result = page.evaluate('window.applicationResult')
    if result is not None:
        raise RuntimeError('Engine stopped during startup: ' + json.dumps(result))
    return guide


def stop_game(page, browser):
    if page.evaluate('document.fullscreenElement !== null'):
        page.evaluate('document.exitFullscreen()')
    if page.evaluate('window.application?.applicationState && window.applicationResult === null'):
        page.locator('#close').click()
        page.wait_for_function('window.applicationResult !== null', timeout=60000)
    shutdown = observe_shutdown(page, browser)
    return dict(exitCode=page.evaluate('window.applicationResult?.code ?? null'),
                workers=shutdown['workers'], liveApplicationTargets=shutdown['liveApplicationTargets'])


def read_profile(page, gui, package):
    profile = page.evaluate('window.graphicsProfile')
    local = page.evaluate('''()=>{const path='/data/config/local.cfg';
      return window.application.FS.analyzePath(path).exists?window.application.FS.readFile(path,{encoding:'utf8'}):null;}''')
    effective = json.loads(gui('JSON.stringify(Object.fromEntries(' + json.dumps(KEYS) +
                               '.map(key=>[key,Engine.ConfigDB_GetValue("user",key)])))'))
    if profile['profile'] == 'low':
        expected = {key: config_value(value) for key, value in profile['settings'].items()}
        if local is None:
            raise AssertionError('Low profile chosen but config/local.cfg is missing')
    else:
        expected = default_values(package)
        if local is not None:
            raise AssertionError('Original profile chosen but config/local.cfg exists')
    mismatched = {key: dict(effective=effective.get(key), expected=value)
                  for key, value in expected.items() if effective.get(key) != value}
    return dict(graphicsProfile=profile, localConfig=local, effectiveSettings=effective, expectedSettings=expected,
                mismatchedSettings=mismatched, renderer=page.evaluate('window.rendererDiagnostics'),
                gpuInfoText=page.locator('#gpu-info').inner_text(), gpuGuide=page.evaluate(GUIDE_STATE))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--runs', nargs='+', required=True, metavar='BACKEND:MODE[:measure]',
                        help='e.g. gl:auto webgpu:original:measure webgpu:auto:measure (backend gl or webgpu; '
                             'mode auto, low or original; ":measure" adds the fullscreen frame measurement)')
    parser.add_argument('--expect-profile', choices=['low', 'original'], help='Profile that auto mode must choose on this GPU.')
    parser.add_argument('--check-user-override', action='store_true', help='After the first run, check that user.cfg wins over local.cfg.')
    parser.add_argument('--expect-guide', choices=['dedicated', 'acceleration', 'none'],
                        help='GPU guide the page must show on load and after the start.')
    parser.add_argument('--force-high-performance-gpu', action='store_true',
                        help='Start Chrome with --force-high-performance-gpu (ignored if Windows sets power saving for Chrome).')
    parser.add_argument('--measure-seconds', type=int, default=60)
    parser.add_argument('--warmup-seconds', type=int, default=30)
    parser.add_argument('--workload', choices=['skirmish', 'combat'], default='skirmish')
    parser.add_argument('--port', type=int, default=8099)
    parser.add_argument('--cdp-port', type=int, default=9231)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    runs = [tuple(run.split(':')) for run in args.runs]
    if any(len(run) not in (2, 3) or run[0] not in ('gl', 'webgpu') or run[1] not in ('auto', 'low', 'original') or
           run[2:] not in ((), ('measure',)) for run in runs):
        parser.error('Runs are BACKEND:MODE[:measure] with BACKEND gl|webgpu and MODE auto|low|original')
    package = args.package.resolve()
    output = (args.output or ROOT / 'docs/wasm/evidence/phase4-5' /
              ('graphics-profile-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
    output.mkdir(parents=True, exist_ok=False)
    chrome = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'
    report = dict(passed=False, package=str(package), chromeGpuPreference=gpu_preference(),
                  forceHighPerformanceGpu=args.force_high_performance_gpu, runs=[], errors=[], console=[])
    server = browser_process = None
    logs = []
    profile = ROOT / 'wasm/build/phase4-5/graphics-profile-chrome'
    try:
        with BenchmarkLock(), sync_playwright() as playwright:
            server_log = (output / 'server.log').open('w'); logs.append(server_log)
            server = subprocess.Popen([sys.executable, str(ROOT / 'wasm/scripts/serve-phase2.py'), '--port', str(args.port),
                                       '--directory', str(package)], cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            wait_url(f'http://localhost:{args.port}/application.html', server)
            if profile.exists():
                shutil.rmtree(profile)
            browser_log = (output / 'browser.log').open('w'); logs.append(browser_log)
            # Without --force-high-performance-gpu the GPU is the one Windows assigns to Chrome.
            browser_process = subprocess.Popen([str(chrome), f'--user-data-dir={profile}', f'--remote-debugging-port={args.cdp_port}',
                                                '--remote-debugging-address=127.0.0.1', '--no-first-run', '--no-default-browser-check',
                                                *(['--force-high-performance-gpu'] if args.force_high_performance_gpu else []),
                                                '--new-window', 'about:blank'], stdout=browser_log, stderr=subprocess.STDOUT)
            wait_url(f'http://127.0.0.1:{args.cdp_port}/json/version', browser_process)
            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{args.cdp_port}')
            report['browserVersion'] = browser.version
            page = browser.contexts[0].pages[0]
            page.on('pageerror', lambda error: report['errors'].append(str(error)))
            page.on('console', lambda message: report['console'].append(message.text))
            gui = lambda code: page.evaluate('(code)=>window.evaluateOriginalGUI(code)', code)
            for index, (backend, mode, *measure) in enumerate(runs, 1):
                run = dict(backend=backend, mode=mode, measured=bool(measure))
                report['runs'].append(run)
                console_start = len(report['console'])
                url = f'http://localhost:{args.port}/application.html?automation=1&graphics={mode}'
                print(f'RUN {index}: {backend} {mode}', flush=True)
                run['gpuGuideAtLoad'] = start_game(page, url, backend)
                run.update(read_profile(page, gui, package))
                if mode == 'auto' and args.expect_profile and run['graphicsProfile']['profile'] != args.expect_profile:
                    raise AssertionError(f"Auto mode chose {run['graphicsProfile']['profile']}, expected {args.expect_profile}")
                guides = [run['gpuGuideAtLoad']['guide'] or 'none', run['gpuGuide']['guide'] or 'none']
                if args.expect_guide and guides != [args.expect_guide] * 2:
                    raise AssertionError(f'GPU guide on load and after the start: {guides}, expected {args.expect_guide}')
                if run['mismatchedSettings']:
                    raise AssertionError('Effective settings differ from the profile: ' + json.dumps(run['mismatchedSettings']))
                print('PROFILE', json.dumps(dict(profile=run['graphicsProfile']['profile'], gpu=run['graphicsProfile']['gpu'],
                                                 guide=run['gpuGuide'])), flush=True)
                if args.check_user_override and index == 1 and run['graphicsProfile']['profile'] == 'low':
                    # The player raises one option in the original options and saves it.
                    assert gui('String(Engine.ConfigDB_CreateValue("user","textures.quality","2") && Engine.ConfigDB_SaveChanges("user"))') == 'true'
                    page.evaluate('async()=>{await window.application.persistentConfig?.flush();}')
                    run['shutdownBeforeOverride'] = stop_game(page, browser)
                    start_game(page, url, backend)
                    override = read_profile(page, gui, package)
                    run['userOverride'] = dict(textureQuality=override['effectiveSettings']['textures.quality'],
                                               shadowQuality=override['effectiveSettings']['shadowquality'],
                                               localConfigPresent=override['localConfig'] is not None)
                    if run['userOverride'] != dict(textureQuality='2', shadowQuality='-1', localConfigPresent=True):
                        raise AssertionError('user.cfg did not take precedence over local.cfg: ' + json.dumps(run['userOverride']))
                    assert gui('String(Engine.ConfigDB_RemoveValueAndSave("user","textures.quality"))') == 'true'
                    page.evaluate('async()=>{await window.application.persistentConfig?.flush();}')
                if measure:
                    run['attributes'] = open_original_match(gui, MANIFEST['settings'])
                    setup = populate(gui, page.wait_for_timeout, args.workload)
                    run['setupUnits'] = {player['player']: len(player['units']) for player in setup['state']['players']}
                    cdp = browser.new_browser_cdp_session()
                    processes = cdp.send('SystemInfo.getProcessInfo')['processInfo']
                    owner = next(int(process['id']) for process in processes if process['type'].lower() == 'browser')
                    gpu_process = next(int(process['id']) for process in processes if process['type'].lower() == 'gpu')
                    run['gpuInfo'] = cdp.send('SystemInfo.getInfo')['gpu']['devices']
                    cdp.detach()
                    try:
                        activate_browser_window(owner)
                    except RuntimeError as error:
                        run['activationWarning'] = str(error)
                    run['fullscreen'] = enter_fullscreen(page, browser)['dimensions']
                    page.wait_for_timeout(args.warmup_seconds * 1000)
                    page.evaluate('window.application.applicationFrames.length=0')
                    start = page.evaluate('performance.now()')
                    counter = start_gpu_counter(gpu_process, args.measure_seconds)
                    page.wait_for_timeout(args.measure_seconds * 1000)
                    end = page.evaluate('performance.now()')
                    frames = [frame for frame in page.evaluate('window.application.applicationFrames')
                              if start <= frame['receivedMs'] <= end and frame['gameStarted']]
                    run['frames'] = frame_metrics(frames)
                    run['gpuEngine3D'] = gpu_counter_result(counter)
                    page.screenshot(path=str(output / f'{index}-{backend}-{mode}.png'))
                    print('FRAMES', json.dumps(run['frames']), 'GPU', json.dumps(run['gpuEngine3D'].get('meanUtilizationPercent')), flush=True)
                run['rendererErrors'] = [line for line in report['console'][console_start:] if any(kind in line for kind in RENDERER_ERRORS)]
                run['engineErrors'] = [line for line in report['console'][console_start:] if 'ERROR:' in line]
                run['shutdown'] = stop_game(page, browser)
                if run['rendererErrors'] or run['engineErrors']:
                    raise AssertionError('Renderer or engine errors: ' + json.dumps(run['rendererErrors'] + run['engineErrors'])[:2000])
                if run['shutdown']['exitCode'] != 0:
                    raise AssertionError('Engine exit code ' + str(run['shutdown']['exitCode']))
            report['passed'] = not report['errors']
            browser.new_browser_cdp_session().send('Browser.close')
    except Exception as error:
        report['failure'] = str(error)
        report['traceback'] = traceback.format_exc()
    finally:
        if browser_process and browser_process.poll() is None:
            try:
                browser_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                browser_process.kill()
        if browser_process:
            # The profile holds a ~0.5 GiB copy of the archive cache; nothing reuses it.
            shutil.rmtree(profile, ignore_errors=True)
        if server:
            server.terminate()
            server.wait(timeout=10)
        for log in logs:
            log.close()
        (output / 'report.json').write_text(json.dumps(report, indent=2))
    summary = [dict(backend=run['backend'], mode=run['mode'], profile=run.get('graphicsProfile', {}).get('profile'),
                    gpu=run.get('graphicsProfile', {}).get('gpu', {}).get('name'), category=run.get('graphicsProfile', {}).get('gpu', {}).get('category'),
                    guide=run.get('gpuGuide', {}).get('guide'),
                    fps=run.get('frames', {}).get('fps'), p95=run.get('frames', {}).get('intervalMs', {}).get('p95'),
                    gpu3d=run.get('gpuEngine3D', {}).get('meanUtilizationPercent')) for run in report['runs']]
    print(json.dumps(dict(passed=report['passed'], failure=report.get('failure'), runs=summary), indent=2))
    print('EVIDENCE', output, flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
