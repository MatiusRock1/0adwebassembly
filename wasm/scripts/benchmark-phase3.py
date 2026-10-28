"""Fixed camera/no-command measurement independent of interaction acceptance."""
import argparse
import os
import re
os.environ["SCENE_REAL_WINDOW"] = "1"
import json
import subprocess
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from scene_surface import assert_surface

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://localhost:8080/scene.html')
parser.add_argument('--channel', choices=['msedge', 'chrome'], default='msedge')
parser.add_argument('--warmup-seconds', type=int, default=120)
parser.add_argument('--duration-seconds', type=int, default=900)
parser.add_argument('--resolution', choices=['640,480', '1920,1080'], default='1920,1080')
parser.add_argument('--trace', action='store_true', help='Diagnostic compositor trace; adds profiling overhead')
parser.add_argument('--fullscreen', action=argparse.BooleanOptionalAction, default=True)
parser.add_argument('--presentmon', type=Path, help='Optional verified portable PresentMon executable (Windows)')
parser.add_argument('--angle', choices=['gl', 'd3d11'], help='Explicit ANGLE backend for matched native/browser GPU comparison')
parser.add_argument('--high-performance-gpu', action='store_true', help='Request the same discrete GPU preferred by the native Windows game')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.warmup_seconds < 0 or args.duration_seconds <= 0:
    parser.error('Invalid measurement window')
result = {'frames': [], 'errors': [], 'acceptance': 'PENDING'}
with BenchmarkLock(), sync_playwright() as p:
    launch_args = ['--use-angle=' + args.angle] if args.angle else []
    if args.high_performance_gpu:
        launch_args.append('--force-high-performance-gpu')
    result['launchArguments'] = launch_args
    browser = p.chromium.launch(channel=args.channel, headless=False, args=launch_args)
    page = browser.new_page(no_viewport=True)
    page.add_init_script("""window.sceneWindowEvents = []; for (const type of ['blur','focus','fullscreenchange','visibilitychange']) { (type === 'blur' || type === 'focus' ? window : document).addEventListener(type, () => window.sceneWindowEvents.push({type, timeMs: performance.now(), focused: document.hasFocus(), hidden: document.hidden, fullscreen: Boolean(document.fullscreenElement)})); }""")
    page.on('pageerror', lambda error: result['errors'].append(str(error)))
    trace_session = None
    trace_stream = []
    presentmon = None
    presentmon_log = None
    try:
        url = urlsplit(args.url)
        parameters = dict(parse_qsl(url.query)); parameters['benchmark'] = '1'
        benchmark_url = urlunsplit(url._replace(query=urlencode(parameters)))
        result['url'] = benchmark_url
        page.goto(benchmark_url)
        page.wait_for_function('window.sceneState?.ready || window.sceneResult', timeout=240000)
        assert page.evaluate('window.sceneState.ready && !window.sceneResult')
        result['hardware'] = page.evaluate('window.sceneHardware')
        result['playerColors'] = page.evaluate("JSON.parse(window.sceneState.events.find(line => line.startsWith('SCENE_PLAYER_COLORS '))?.slice(20) ?? 'null')")
        result['browserVersion'] = browser.version
        result['build'] = page.evaluate("fetch('./build-profile.json').then(r => r.ok ? r.json() : null).catch(() => null)")
        result['benchmarkContract'] = (result['build'] or {}).get('benchmarkContract')
        if args.presentmon:
            process_info = browser.new_browser_cdp_session().send('SystemInfo.getProcessInfo')['processInfo']
            gpu = [process for process in process_info if process['type'].lower() == 'gpu']
            assert len(gpu) == 1, 'Cannot identify isolated browser GPU process'
            result['presentationProcessId'] = gpu[0]['id']
            result['presentmonCsv'] = str(args.output.with_suffix('.presentmon.csv'))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            presentmon_log = args.output.with_suffix('.presentmon.log').open('w', encoding='utf-8')
            presentmon = subprocess.Popen([str(args.presentmon.resolve()), '--process_id', str(gpu[0]['id']),
                '--timed', str(args.warmup_seconds + args.duration_seconds + 90), '--terminate_after_timed',
                '--no_console_stats', '--session_name', '0ad-phase3-' + str(gpu[0]['id']),
                '--output_file', str(args.output.with_suffix('.presentmon.csv').resolve()),
                '--write_display_metadata', '--qpc_time_ms'], stdout=presentmon_log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            page.wait_for_timeout(45000)
        width, height = map(int, args.resolution.split(','))
        if page.evaluate('window.sceneState.metrics.width') != width:
            page.locator('#resolution').select_option(args.resolution)
        page.wait_for_function('window.sceneState.metrics.width === ' + str(width), timeout=60000)
        if args.fullscreen:
            page.locator('#fullscreen').click()
            page.wait_for_function('document.fullscreenElement === document.querySelector("#canvas")')
            page.wait_for_function('window.sceneState.metrics.width === 1920 && window.sceneState.metrics.height === 1080', timeout=60000)
        result['fullscreen'] = page.evaluate('document.fullscreenElement === document.querySelector("#canvas")')
        browser_cdp = browser.new_browser_cdp_session()
        target_id = page.context.new_cdp_session(page).send('Target.getTargetInfo')['targetInfo']['targetId']
        for attempt in range(40):
            result['browserWindow'] = browser_cdp.send('Browser.getWindowForTarget', {'targetId': target_id})
            if not args.fullscreen or result['browserWindow']['bounds']['windowState'] == 'fullscreen':
                break
            page.wait_for_timeout(250)
        if args.fullscreen:
            assert result['browserWindow']['bounds']['windowState'] == 'fullscreen', 'DOM fullscreen did not hide browser chrome'
            page.wait_for_function('window.sceneState.metrics.width === 1920 && window.sceneState.metrics.height === 1080', timeout=60000)
        if args.fullscreen:
            before = page.evaluate('window.sceneFrames.at(-1)?.frame ?? 0')
            page.wait_for_function('(before) => window.sceneFrames.at(-1)?.frame >= before + 2 && window.sceneFrames.at(-1)?.height === 1080', arg=before)
        page.locator('#canvas').focus()
        page.wait_for_timeout(1000)
        if page.evaluate('window.sceneFrames.at(-1)?.paused'):
            resume_frame = page.evaluate('window.sceneFrames.at(-1).frame')
            page.locator('#canvas').press('Space')
            page.wait_for_function('(before) => window.sceneFrames.at(-1)?.frame > before && window.sceneFrames.at(-1)?.paused === false', arg=resume_frame)
        page.wait_for_function('window.sceneFrames.at(-1)?.paused === false')
        result['surface'] = assert_surface(page, width, height)
        page.locator('#canvas').focus()
        result['hardware'] = page.evaluate('window.sceneHardware')
        assert not any(name in result['hardware']['renderer'].lower() for name in ['swiftshader', 'basic render', 'llvmpipe', 'software']), 'Software renderer cannot satisfy the hardware benchmark'
        result['browserVersion'] = browser.version
        result['build'] = page.evaluate("fetch('./build-profile.json').then(r => r.ok ? r.json() : null).catch(() => null)")
        page.evaluate('window.sceneFrames.length = 0')
        result['measurementStartQpcMs'] = time.perf_counter() * 1000
        result['warmupSeconds'] = args.warmup_seconds
        result['durationSeconds'] = args.duration_seconds
        if args.trace:
            trace_session = browser.new_browser_cdp_session()
            trace_session.on('Tracing.tracingComplete', lambda data: trace_stream.append(data))
            result['traceCategoriesAvailable'] = trace_session.send('Tracing.getCategories')['categories']
            trace_session.send('Tracing.start', {'categories': 'viz,cc,gpu,benchmark,blink.user_timing,disabled-by-default-devtools.timeline.frame',
                                                'options': 'record-continuously', 'transferMode': 'ReturnAsStream'})
        deadline = time.monotonic() + args.warmup_seconds + args.duration_seconds + 2
        result['memorySamples'] = []
        while time.monotonic() < deadline:
            if args.output.with_suffix('.stop').exists():
                raise RuntimeError('Benchmark cancelled via its stop file')
            page.wait_for_timeout(min(15000, max(1, (deadline - time.monotonic()) * 1000)))
            assert page.evaluate('window.sceneResult === null')
            assert page.evaluate('window.sceneFrames.at(-1)?.paused === false'), 'Simulation paused; measurement is invalid'
            if args.fullscreen:
                assert page.evaluate('document.fullscreenElement === document.querySelector("#canvas")'), 'Fullscreen exited during measurement'
            result['memorySamples'].append(page.evaluate('({jsBytes: performance.memory?.usedJSHeapSize ?? null, wasmBytes: window.sceneFrames.at(-1)?.wasmHeapBytes ?? null, tick: window.sceneFrames.at(-1)?.tick ?? null, paused: window.sceneFrames.at(-1)?.paused ?? null})'))
            args.output.with_suffix('.progress.json').write_text(json.dumps({'url': result['url'], 'elapsedSeconds': round(args.warmup_seconds + args.duration_seconds + 2 - max(0, deadline-time.monotonic())), 'sample': result['memorySamples'][-1], 'measurementComplete': False}), encoding='utf-8')
            print('BENCHMARK_PROGRESS ' + str(round(args.warmup_seconds + args.duration_seconds + 2 - max(0, deadline-time.monotonic()))) + 's ' + str(result['memorySamples'][-1]), flush=True)
        result['measurementCompleted'] = True
        result['windowEvents'] = page.evaluate('window.sceneWindowEvents')
        result['lastStats'] = page.evaluate('window.sceneState.metrics')
        result['frames'] = page.evaluate('window.sceneFrames')
        result['jsLongTasks'] = page.evaluate('window.sceneJsLongTasks ?? []')
        if args.fullscreen:
            page.keyboard.press('Escape')
            page.wait_for_function('document.fullscreenElement === null')
        page.locator('[data-key="Escape"]').click()
        page.wait_for_function('window.sceneResult !== null', timeout=60000)
        result['exit'] = page.evaluate('window.sceneResult')
        assert result['exit']['passed'] and not result['errors']
    except Exception as error:
        result['failure'] = str(error)
        try:
            result['frames'] = page.evaluate('window.sceneFrames ?? []')
            result['state'] = page.evaluate('window.sceneState')
            result['windowEvents'] = page.evaluate('window.sceneWindowEvents')
            result['browserWindowAtFailure'] = browser_cdp.send('Browser.getWindowForTarget', {'targetId': target_id})
        except Exception:
            pass
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if presentmon:
            if presentmon.poll() is None:
                subprocess.run([str(args.presentmon.resolve()), '--session_name', '0ad-phase3-' + str(result['presentationProcessId']), '--terminate_existing_session'], stdout=presentmon_log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=15)
            try:
                result['presentmonExitCode'] = presentmon.wait(timeout=30)
            except subprocess.TimeoutExpired:
                subprocess.run([str(args.presentmon.resolve()), '--session_name', '0ad-phase3-' + str(result['presentationProcessId']), '--terminate_existing_session'], stdout=presentmon_log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=15)
                presentmon.terminate(); presentmon.wait(timeout=10)
                result['presentmonFailure'] = 'Capture did not stop within deadline'
            presentmon_log.close()
            capture_text = args.output.with_suffix('.presentmon.log').read_text(encoding='utf-8', errors='replace')
            result['presentmonEventsLost'] = sum(int(count) for count in re.findall(r'(\d+) ETW events were lost', capture_text))
        if trace_session:
            try:
                trace_session.send('Tracing.end')
                trace_deadline = time.monotonic() + 20
                while not trace_stream and time.monotonic() < trace_deadline:
                    page.wait_for_timeout(100)
                assert trace_stream, 'No trace completion event'
                handle = trace_stream[0]['stream']
                result['traceCompletion'] = trace_stream[0]
                trace_path = args.output.with_suffix('.trace.json')
                with trace_path.open('w', encoding='utf-8') as trace_file:
                    while True:
                        chunk = trace_session.send('IO.read', {'handle': handle, 'size': 1048576})
                        trace_file.write(chunk['data'])
                        if chunk.get('eof'):
                            break
                trace_session.send('IO.close', {'handle': handle})
                result['traceFile'] = str(trace_path)
            except Exception as error:
                result['traceFailure'] = str(error)
        args.output.with_suffix('.progress.json').write_text(json.dumps({'measurementComplete': bool(result.get('measurementCompleted')), 'runtimePassed': not bool(result.get('failure')), 'failure': result.get('failure')}), encoding='utf-8')
        args.output.write_text(json.dumps(result, indent=2))
        browser.close()
