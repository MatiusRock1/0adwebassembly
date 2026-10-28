"""Visual/attachment regression for proxied resize and native fullscreen."""
import argparse
import os
os.environ["SCENE_REAL_WINDOW"] = "1"
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from scene_surface import assert_surface

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://localhost:8089/scene.html')
parser.add_argument('--output-directory', type=Path, default=Path('docs/wasm/evidence/phase3/corrected-surface'))
args = parser.parse_args()
args.output_directory.mkdir(parents=True, exist_ok=True)
report = {'passed': False, 'surfaces': []}
with BenchmarkLock(), sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=False, args=['--force-high-performance-gpu'])
    page = browser.new_page(no_viewport=True)
    try:
        page.goto(args.url)
        page.wait_for_function('window.sceneState?.ready', timeout=240000)
        for resolution in ['800,600', '1920,1080', '640,480']:
            width, height = map(int, resolution.split(','))
            page.locator('#resolution').select_option(resolution)
            page.wait_for_function('(size) => window.sceneFrames.at(-1)?.width === size[0] && window.sceneFrames.at(-1)?.height === size[1]', arg=[width, height])
            report['surfaces'].append(assert_surface(page, width, height))
            page.locator('#canvas').screenshot(path=str(args.output_directory / (resolution.replace(',', 'x') + '.png')))
        page.locator('#fullscreen').click()
        page.wait_for_function('document.fullscreenElement === document.querySelector("#canvas")')
        page.wait_for_timeout(1500)
        surface = assert_surface(page, *page.evaluate('[canvas.width, canvas.height]'))
        cdp = page.context.new_cdp_session(page)
        report['window'] = cdp.send('Browser.getWindowForTarget')
        report['surfaces'].append(surface)
        page.screenshot(path=str(args.output_directory / 'fullscreen.png'))
        assert report['window']['bounds']['windowState'] == 'fullscreen'
        page.keyboard.press('Escape')
        page.wait_for_function('document.fullscreenElement === null')
        page.locator('[data-key="Escape"]').click()
        page.wait_for_function('window.sceneResult !== null')
        assert page.evaluate('window.sceneResult.passed')
        report['passed'] = True
    except BaseException as error:
        report['failure'] = str(error)
        raise
    finally:
        (args.output_directory / 'surface.json').write_text(json.dumps(report, indent=2))
        browser.close()
