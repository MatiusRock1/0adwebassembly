"""Opt out of Playwright 1.56's focus emulation for native fullscreen tests.

Only patch a workspace-local test environment; the game/browser are untouched.
Default Playwright behavior remains unchanged unless SCENE_REAL_WINDOW=1.
"""
import hashlib
import json
from pathlib import Path
import playwright

root = Path(__file__).resolve().parents[2]
driver = Path(playwright.__file__).resolve().parent / 'driver/package/lib/server/chromium/crPage.js'
if root not in driver.parents:
    raise SystemExit('Use a workspace-local virtual environment; external installations are not modified')
source = driver.read_text(encoding='utf-8')
original = 'this._client.send("Emulation.setFocusEmulationEnabled", { enabled: true })'
replacement = 'this._client.send("Emulation.setFocusEmulationEnabled", { enabled: process.env.SCENE_REAL_WINDOW !== "1" })'
if replacement in source:
    print('Real-window opt-in already available')
else:
    if source.count(original) != 1:
        raise SystemExit('Unsupported Playwright driver; inspect focus emulation before modifying')
    before = hashlib.sha256(driver.read_bytes()).hexdigest()
    driver.write_text(source.replace(original, replacement), encoding='utf-8')
    evidence = root / 'docs/wasm/evidence/phase3/playwright-real-focus-patch.json'
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({'dependency': 'workspace-private Playwright driver',
                                   'file': str(driver), 'originalSHA256': before,
                                   'patchedSHA256': hashlib.sha256(driver.read_bytes()).hexdigest(),
                                   'change': 'SCENE_REAL_WINDOW=1 disables original-session focus emulation; default unchanged',
                                   'purpose': 'Verify real fullscreen/focus; game runtime unaffected'}, indent=2))
    print('Real-window opt-in prepared')
