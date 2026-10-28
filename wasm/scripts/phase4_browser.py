"""Observe asynchronous browser teardown without hiding live workers."""
import time
import os
import json
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# The prepared Playwright driver uses this flag to disable focus emulation on
# its own page session. A separate CDP session cannot reliably override it.
os.environ['SCENE_REAL_WINDOW']='1'


# Defaults preserve the frozen phase-4 harness; phase 4.5 opts in explicitly.
APPLICATION_URL=os.environ.get('SCENE_APPLICATION_URL','http://localhost:8091/application.html?automation=1')
CDP_URL=os.environ.get('SCENE_CDP_URL','http://127.0.0.1:9226')
EVIDENCE_ROOT=os.environ.get('SCENE_EVIDENCE_ROOT','docs/wasm/evidence/phase4')

def start_application(page,url=APPLICATION_URL):
    if not hasattr(page,'_renderer_errors'):
        page._renderer_errors=[]
        def inspect_console(message):
            try:event=json.loads(message.text)
            except (TypeError,ValueError):return
            if isinstance(event,dict) and (event.get('type')=='uncaptured-error' or
                (event.get('type')=='engine-device-lost' and not event.get('expected'))):
                page._renderer_errors.append(event)
        page.on('console',inspect_console)
    page.goto(url)
    backend=os.environ.get('SCENE_RENDERER','gl')
    if backend not in ('gl','webgpu'):raise ValueError('Unknown SCENE_RENDERER: '+backend)
    if backend=='webgpu' or page.locator('#renderer-backend').count():
        page.locator('#renderer-backend').select_option('webgl' if backend=='gl' else backend)
    page.locator('#start').click()

def assert_renderer_clean(page):
    assert not getattr(page,'_renderer_errors',[]),getattr(page,'_renderer_errors',[])

def renderer_diagnostics(page):
    """Read the actual old GL context without modifying the frozen launcher."""
    if page.evaluate('Boolean(window.rendererDiagnostics)'):
        return page.evaluate('window.rendererDiagnostics')
    if os.environ.get('SCENE_RENDERER','gl')!='gl':raise RuntimeError('Missing WebGPU renderer diagnostics')
    return page.evaluate('''()=>{
      const gl=document.getElementById('canvas').getContext('webgl2');
      if(!gl)throw new Error('Frozen baseline has no actual WebGL2 context');
      const info=gl.getExtension('WEBGL_debug_renderer_info');
      return {backend:'webgl',source:'existing frozen-baseline GL context',
        renderer:info?gl.getParameter(info.UNMASKED_RENDERER_WEBGL):null,
        version:gl.getParameter(gl.VERSION)};
    }''')


def new_test_page(browser):
    """Recover only prior task tabs in the dedicated test-browser profile."""
    context=browser.contexts[0]
    previous=list(context.pages)
    page=context.new_page()
    page.bring_to_front()
    for old in previous:
        if old.url.startswith(APPLICATION_URL.split('?')[0]):
            old.close()
    return page


def move_original_pointer(page, x, y):
    """Move trusted input to an engine pixel, including SDL's locked cursor."""
    box = page.locator('#canvas').bounding_box()
    locked = page.evaluate('document.pointerLockElement===document.getElementById("canvas")')
    if not locked:
        page.mouse.move(box['x'] + x * box['width'] / 1920,
                        box['y'] + y * box['height'] / 1080)
        return
    import ctypes
    assert page.evaluate('document.hasFocus()'), 'Real mouse input requires foreground game focus'
    owner=getattr(page,'_phase4_browser_pid',None)
    if os.name=='nt' and owner is not None:
        from phase45_window_focus import foreground_window
        foreground_window(owner)
    scale = page.evaluate('devicePixelRatio')
    for unused in range(100):
        packed = page.evaluate('application.ccall("Phase4MousePosition","number",[],[])')
        dx, dy = x - (packed & 65535), y - ((packed >> 16) & 65535)
        if abs(dx) <= 1 and abs(dy) <= 1:
            return
        def step(error, ratio):
            if abs(error) <= 1: return 0
            amount = max(-64, min(64, int(error * ratio * scale / 2)))
            return amount or (1 if error > 0 else -1)
        previous_frame=page.evaluate('application.applicationState.frame')
        ctypes.windll.user32.mouse_event(1, step(dx, box['width']/1920),
            step(dy, box['height']/1080), 0, 0)
        # Read SDL only after the queued event and its atomic position have
        # crossed the engine loop. A fixed 100 ms delay overshoots on slow
        # frames because several corrections use the same stale position.
        # With present pacing several frames can be in flight, so a presented
        # frame may predate the move: wait for SDL's position itself to change.
        try:
            page.wait_for_function('before=>application.ccall("Phase4MousePosition","number",[],[])!==before',arg=packed,timeout=2000)
        except PlaywrightTimeoutError:
            page.wait_for_function('frame=>application.applicationState.frame>frame+1',arg=previous_frame,timeout=15000)
    raise AssertionError(f'Original locked cursor did not reach {(x,y)}: {packed & 65535,packed >> 16}')


def enter_fullscreen(page, browser):
    """Require OS fullscreen, full display coverage and 1080p render size."""
    page.bring_to_front()
    target_session=page.context.new_cdp_session(page)
    # Element fullscreen alone is insufficient: independently require the OS
    # window state, physical display coverage and real focus below.
    target_session.send('Emulation.setFocusEmulationEnabled',dict(enabled=False))
    target=target_session.send('Target.getTargetInfo')['targetInfo']['targetId']
    target_session.detach()
    session=browser.new_browser_cdp_session()
    window=session.send('Browser.getWindowForTarget',dict(targetId=target))
    if os.name=='nt':
        from phase45_window_focus import wait_foreground_window
        owners=[process for process in session.send('SystemInfo.getProcessInfo')['processInfo'] if process['type']=='browser']
        assert len(owners)==1,owners
        page._phase4_browser_pid=int(owners[0]['id'])
        wait_foreground_window(page._phase4_browser_pid,
            timeout_seconds=int(os.environ.get('SCENE_FOREGROUND_TIMEOUT_MS','180000'))/1000,
            poll=lambda seconds:page.wait_for_timeout(seconds*1000))
    if not page.evaluate('document.fullscreenElement === (document.getElementById("game-surface") || document.getElementById("canvas"))'):
        if os.environ.get('SCENE_AUTO_FULLSCREEN')=='1':
            page.locator('#fullscreen').click()
            print('VISIBLE_FULLSCREEN_BUTTON_CLICKED_BY_TEST',flush=True)
        else:print('WAITING_FOR_VISIBLE_FULLSCREEN_BUTTON',flush=True)
    page.wait_for_function('document.fullscreenElement === (document.getElementById("game-surface") || document.getElementById("canvas")) && document.getElementById("canvas").width===1920 && document.getElementById("canvas").height===1080 && innerWidth===screen.width && innerHeight===screen.height',timeout=int(os.environ.get('SCENE_FULLSCREEN_TIMEOUT_MS','180000')))
    page.wait_for_timeout(1000)
    window=session.send('Browser.getWindowForTarget',dict(targetId=target))
    dimensions=page.evaluate('''()=>{const r=document.getElementById('canvas').getBoundingClientRect();
      return {inner:[innerWidth,innerHeight],screen:[screen.width,screen.height],dpr:devicePixelRatio,focused:document.hasFocus(),canvasCSS:[r.width,r.height]};}''')
    if os.name=='nt':
        from phase45_window_focus import foreground_window
        owners=[process for process in session.send('SystemInfo.getProcessInfo')['processInfo'] if process['type']=='browser']
        assert len(owners)==1,owners
        page._phase4_browser_pid=int(owners[0]['id'])
        # DOM focus is insufficient when Windows refuses activation. Verify
        # the physical owner before sending any OS-relative mouse movement.
        dimensions['foregroundWindow']=foreground_window(page._phase4_browser_pid)
    session.detach()
    assert window['bounds']['windowState']=='fullscreen',window
    assert dimensions['inner']==dimensions['screen'],dimensions
    assert dimensions['focused'],dimensions
    if page.locator('#game-surface').count():
        assert abs(dimensions['canvasCSS'][0]/dimensions['canvasCSS'][1]-16/9)<.001,('Fullscreen stretched the original image',dimensions)
    move_original_pointer(page,960,540)
    return dict(window=window,dimensions=dimensions,internalResolution=[1920,1080])


def observe_shutdown(page, browser, seconds=10):
    page.evaluate('async()=>{await window.applicationCleanup;}')
    samples = []
    started = time.monotonic()
    while True:
        sdk = page.evaluate('window.application.getApplicationWorkerState()')
        workers = [worker.url for worker in page.workers]
        samples.append(dict(seconds=time.monotonic() - started, sdk=sdk, workers=workers))
        if not workers and not sdk['running'] and not sdk['pooled'] and not sdk['pthreads']:
            break
        if time.monotonic() - started >= seconds:
            break
        page.wait_for_timeout(250)
    # Chromium's live target inventory corroborates the Playwright events.
    session = browser.new_browser_cdp_session()
    targets = session.send('Target.getTargets')['targetInfos']
    application_workers = [target for target in targets
                           if target['type'] == 'worker' and 'pyrogenesis-application.mjs' in target['url']]
    session.detach()
    return dict(samples=samples, sdk=sdk, workers=workers, liveApplicationTargets=application_workers)
