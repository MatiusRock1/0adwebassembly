"""Engine command transport and pipeline warm-up of the WebGPU render worker, in Chrome.

Every run of one invocation shares a Chrome profile, so the pipeline list that a
run stores in IndexedDB is the warm list of the next run. A run is
TRANSPORT:CACHE: TRANSPORT ring (the engine publishes to the render worker
through shared memory) or relay (?commandRing=0, every call through the window),
CACHE cache or nocache (?pipelineCache=0). Each run starts the original menus,
opens the benchmark match in fullscreen and records render worker snapshots at
the menu, after the match setup and around the measured window: pipeline
compiles and the draws that waited for them, the worker's busy time per frame,
the delivery latency of engine calls and the engine frames. Diagnostic only;
displayed frames (PresentMon) are measured by benchmark-phase4-5-standalone.py.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from playwright.sync_api import sync_playwright

os.environ.setdefault('SCENE_AUTO_FULLSCREEN', '1')
from benchmark_lock import BenchmarkLock
from phase4_flow import open_original_match
from phase4_workload import MANIFEST, populate
from phase4_browser import enter_fullscreen
from phase45_window_focus import activate_browser_window

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[1]

# Helpers of verify-graphics-profile.py, whose file name cannot be imported directly.
spec = importlib.util.spec_from_file_location('graphics_profile', SCRIPTS / 'verify-graphics-profile.py')
graphics_profile = importlib.util.module_from_spec(spec); spec.loader.exec_module(graphics_profile)
wait_url, start_game, stop_game, frame_metrics, gpu_preference = (graphics_profile.wait_url, graphics_profile.start_game,
    graphics_profile.stop_game, graphics_profile.frame_metrics, graphics_profile.gpu_preference)
RENDERER_ERRORS = graphics_profile.RENDERER_ERRORS
SNAPSHOT = 'async()=>window.application.webgpuBackend.snapshot()'
COUNTERS = ('pipelineCompiles', 'pipelineWarmCompiles', 'pipelineWarmHits', 'pipelineContentHits', 'pipelineWaits',
            'pipelineWaitMilliseconds', 'pipelineCompileMilliseconds', 'frames', 'draws', 'stageMilliseconds')


def difference(after, before):
    """Counters between two snapshots; histograms element by element."""
    stats = {key: round(after['stats'][key] - before['stats'][key], 3) for key in COUNTERS}
    work = {key: round(after['work'][key] - before['work'][key], 3) for key in ('busyMilliseconds', 'frames')}
    work['frameHistogram'] = [a - b for a, b in zip(after['work']['frameHistogram'], before['work']['frameHistogram'])]
    work['meanBusyMillisecondsPerFrame'] = round(work['busyMilliseconds'] / work['frames'], 3) if work['frames'] else None
    delivery = {key: round(after['delivery'][key] - before['delivery'][key], 3) for key in ('ring', 'relay', 'totalMilliseconds')}
    delivery['histogram'] = [a - b for a, b in zip(after['delivery']['histogram'], before['delivery']['histogram'])]
    calls = delivery['ring'] + delivery['relay']
    delivery['meanMilliseconds'] = round(delivery['totalMilliseconds'] / calls, 4) if calls else None
    queue = {key: round(after['commandQueue'][key] - before['commandQueue'][key], 3) for key in ('consumed', 'totalWaitMilliseconds')}
    return dict(stats=stats, work=work, delivery=delivery, commandQueue=queue,
                presentation={key: after['presentation'][key] - before['presentation'][key] for key in ('pacedPresents', 'pacedHolds')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--runs', nargs='+', required=True, metavar='TRANSPORT:CACHE',
                        help='e.g. relay:nocache ring:cache ring:cache (TRANSPORT ring|relay, CACHE cache|nocache)')
    parser.add_argument('--workload', choices=['skirmish', 'combat'], default='skirmish')
    parser.add_argument('--warmup-seconds', type=int, default=30)
    parser.add_argument('--measure-seconds', type=int, default=60)
    parser.add_argument('--port', type=int, default=8099)
    parser.add_argument('--cdp-port', type=int, default=9231)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    runs = [tuple(run.split(':')) for run in args.runs]
    if any(len(run) != 2 or run[0] not in ('ring', 'relay') or run[1] not in ('cache', 'nocache') for run in runs):
        parser.error('Runs are TRANSPORT:CACHE with TRANSPORT ring|relay and CACHE cache|nocache')
    package = args.package.resolve()
    output = (args.output or ROOT / 'docs/wasm/evidence/phase4-5' /
              ('render-transport-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
    output.mkdir(parents=True, exist_ok=False)
    chrome = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'
    report = dict(passed=False, package=str(package), chromeGpuPreference=gpu_preference(), runs=[], errors=[], console=[])
    server = browser_process = None
    logs = []
    profile = ROOT / 'wasm/build/phase4-5/render-transport-chrome'
    try:
        with BenchmarkLock(), sync_playwright() as playwright:
            server_log = (output / 'server.log').open('w'); logs.append(server_log)
            server = subprocess.Popen([sys.executable, str(SCRIPTS / 'serve-phase2.py'), '--port', str(args.port),
                                       '--directory', str(package)], cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            wait_url(f'http://localhost:{args.port}/application.html', server)
            if profile.exists():
                shutil.rmtree(profile)
            browser_log = (output / 'browser.log').open('w'); logs.append(browser_log)
            browser_process = subprocess.Popen([str(chrome), f'--user-data-dir={profile}', f'--remote-debugging-port={args.cdp_port}',
                                                '--remote-debugging-address=127.0.0.1', '--no-first-run', '--no-default-browser-check',
                                                '--force-high-performance-gpu', '--new-window', 'about:blank'],
                                               stdout=browser_log, stderr=subprocess.STDOUT)
            wait_url(f'http://127.0.0.1:{args.cdp_port}/json/version', browser_process)
            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{args.cdp_port}')
            report['browserVersion'] = browser.version
            page = browser.contexts[0].pages[0]
            page.on('pageerror', lambda error: report['errors'].append(str(error)))
            page.on('console', lambda message: report['console'].append(message.text))
            gui = lambda code: page.evaluate('(code)=>window.evaluateOriginalGUI(code)', code)
            for index, (transport, cache) in enumerate(runs, 1):
                run = dict(transport=transport, cache=cache)
                report['runs'].append(run)
                console_start = len(report['console'])
                query = '&'.join(['automation=1'] + (['commandRing=0'] if transport == 'relay' else []) +
                                 (['pipelineCache=0'] if cache == 'nocache' else []))
                print(f'RUN {index}: {transport} {cache}', flush=True)
                start_game(page, f'http://localhost:{args.port}/application.html?{query}', 'webgpu')
                menu = page.evaluate(SNAPSHOT)
                run['menu'] = dict(stats={key: menu['stats'][key] for key in COUNTERS}, commandRing=menu['commandRing'],
                                   pipelineCache=menu['pipelineCache'])
                if (transport == 'ring') != menu['commandRing']['attached']:
                    raise AssertionError(f"Transport {transport} but commandRing.attached={menu['commandRing']['attached']}")
                run['attributes'] = open_original_match(gui, MANIFEST['settings'])
                setup = populate(gui, page.wait_for_timeout, args.workload)
                run['setupUnits'] = {player['player']: len(player['units']) for player in setup['state']['players']}
                matched = page.evaluate(SNAPSHOT)
                run['matchLoad'] = difference(matched, menu)
                cdp = browser.new_browser_cdp_session()
                owner = next(int(process['id']) for process in cdp.send('SystemInfo.getProcessInfo')['processInfo']
                             if process['type'].lower() == 'browser')
                run['gpuDevices'] = cdp.send('SystemInfo.getInfo')['gpu']['devices']
                cdp.detach()
                try:
                    activate_browser_window(owner)
                except RuntimeError as error:
                    run['activationWarning'] = str(error)
                run['fullscreen'] = enter_fullscreen(page, browser)['dimensions']
                page.wait_for_timeout(args.warmup_seconds * 1000)
                before = page.evaluate(SNAPSHOT)
                page.evaluate('window.application.applicationFrames.length=0')
                start = page.evaluate('performance.now()')
                page.wait_for_timeout(args.measure_seconds * 1000)
                end = page.evaluate('performance.now()')
                after = page.evaluate(SNAPSHOT)
                frames = [frame for frame in page.evaluate('window.application.applicationFrames')
                          if start <= frame['receivedMs'] <= end and frame['gameStarted']]
                run['frames'] = frame_metrics(frames)
                run['measured'] = difference(after, before)
                run['final'] = dict(commandRing=after['commandRing'], pipelineCache=after['pipelineCache'],
                                    deliveryMinMilliseconds=after['delivery']['minMilliseconds'],
                                    deliveryMaxMilliseconds=after['delivery']['maxMilliseconds'])
                print('MATCH', json.dumps(run['matchLoad']['stats']), flush=True)
                print('MEASURED', json.dumps(dict(frames=run['frames'], work=run['measured']['work'],
                                                  delivery=run['measured']['delivery'])), flush=True)
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
    summary = [dict(transport=run['transport'], cache=run['cache'],
                    matchPipelineCompiles=run.get('matchLoad', {}).get('stats', {}).get('pipelineCompiles'),
                    matchPipelineWaits=run.get('matchLoad', {}).get('stats', {}).get('pipelineWaits'),
                    matchPipelineWaitMs=run.get('matchLoad', {}).get('stats', {}).get('pipelineWaitMilliseconds'),
                    warmHits=run.get('matchLoad', {}).get('stats', {}).get('pipelineWarmHits'),
                    fps=run.get('frames', {}).get('fps'), p95=run.get('frames', {}).get('intervalMs', {}).get('p95'),
                    busyMsPerFrame=run.get('measured', {}).get('work', {}).get('meanBusyMillisecondsPerFrame'),
                    deliveryMeanMs=run.get('measured', {}).get('delivery', {}).get('meanMilliseconds'),
                    deliveryHistogram=run.get('measured', {}).get('delivery', {}).get('histogram')) for run in report['runs']]
    print(json.dumps(dict(passed=report['passed'], failure=report.get('failure'), runs=summary), indent=2))
    print('EVIDENCE', output, flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
