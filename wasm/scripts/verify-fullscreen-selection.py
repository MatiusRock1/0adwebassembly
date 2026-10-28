"""Check actual fullscreen picking at every supported render scale."""
import os
os.environ['SCENE_REAL_WINDOW'] = '1'
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from scene_surface import assert_surface

output = Path('docs/wasm/evidence/phase3/fullscreen-selection')
output.mkdir(parents=True, exist_ok=True)
report = {'passed': False, 'cases': []}
with BenchmarkLock(), sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=False,
                                args=['--force-high-performance-gpu'])
    page = browser.new_page(no_viewport=True)
    try:
        page.goto('http://localhost:8089/scene.html')
        page.wait_for_function('window.sceneState?.ready', timeout=240000)
        for scale in ['1', '0.75', '0.5']:
            page.locator('#render-scale').select_option(scale)
            page.locator('#fullscreen').click()
            page.wait_for_function('document.fullscreenElement !== null')
            page.wait_for_function('window.sceneState.metrics.width === Math.round(innerWidth * devicePixelRatio * Number(document.querySelector("#render-scale").value))')
            page.wait_for_timeout(1000)
            metrics = page.evaluate('window.sceneState.metrics')
            assert_surface(page, metrics['width'], metrics['height'])
            box = page.locator('#canvas').bounding_box()
            page.mouse.click(box['x'] + metrics['screenX'] * box['width'] / metrics['width'],
                             box['y'] + metrics['screenY'] * box['height'] / metrics['height'])
            page.wait_for_function('window.sceneState.metrics.selected === 8', timeout=5000)
            before = page.evaluate('window.sceneState.events.filter(x => x.startsWith("SCENE_WALK_QUEUED ")).length')
            page.mouse.click(box['x'] + metrics['screenX'] * box['width'] / metrics['width'],
                             box['y'] + metrics['screenY'] * box['height'] / metrics['height'], button='right')
            page.wait_for_function('window.sceneState.events.filter(x => x.startsWith("SCENE_WALK_QUEUED ")).length > ' + str(before), timeout=5000)
            report['cases'].append({'scale': scale, 'leftSelectionPassed': True,
                                    'rightCommandPassed': True, 'surfaceVerified': True,
                                    'metrics': page.evaluate('window.sceneState.metrics')})
            page.screenshot(path=str(output / f'scale-{scale}.png'))
            page.keyboard.press('Escape')
            page.wait_for_function('document.fullscreenElement === null')
            page.locator('[data-key="KeyR"]').click()
            page.wait_for_function('window.sceneState.metrics.selected === 0')
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error)
        report['state'] = page.evaluate('window.sceneState')
        page.screenshot(path=str(output / 'failure.png'))
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        browser.close()
