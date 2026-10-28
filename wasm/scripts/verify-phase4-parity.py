from phase4_browser import APPLICATION_URL, CDP_URL, EVIDENCE_ROOT, start_application, assert_renderer_clean
"""Compare original full-game native/WASM dumps at exact simulation times."""
import argparse
import hashlib
import json
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_flow import open_original_match, checkpoint, parity_settings
from phase4_browser import observe_shutdown, enter_fullscreen, new_test_page
from phase45_simulation_snapshot import debug_scopes,preserve_save
from phase45_benchmark_contract import fingerprint

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--evidence', type=Path, default=(Path(EVIDENCE_ROOT)/'full-game-parity'))
parser.add_argument('--systems', action='store_true')
parser.add_argument('--advanced', action='store_true')
parser.add_argument('--capture', action='store_true')
parser.add_argument('--build',type=Path,help='Local packaged build being served; record its hashes explicitly.')
args = parser.parse_args()
args.evidence.mkdir(parents=True, exist_ok=True)
native = json.loads((args.native / 'report.json').read_text())
if not native['passed'] or native.get('exitCode')!=0 or native.get('closeFailure'):
    raise SystemExit('Native checkpoints must pass first.')
if not all('serializedSHA256' in entry for entry in native['checkpoints']):
    raise SystemExit('Regenerate the native checkpoints with original simulation.dat snapshots first.')
report = dict(passed=False, phase4Accepted=False, errors=[], console=[], checkpoints=[],
              nativeReference=str((args.native/'report.json').resolve()),
              comparisonScope='Original simulation.dat, every non-local debug component, original GUI state and command traces; full raw debug retained separately')
if args.build:report['buildSHA256']=fingerprint(args.build)
report['focusPolicy']='Original PauseOnFocusLoss(false) for functional checkpoints, matching the native reference; not performance acceptance'
with BenchmarkLock(), sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    report['browserVersion']=browser.version
    page = new_test_page(browser)
    page.bring_to_front()
    page.on('pageerror', lambda error: report['errors'].append(str(error)))
    page.on('console', lambda message: report['console'].append(message.text))
    page.add_init_script('''window.parityFocusTrace=[];
      for(const name of ['focus','blur','visibilitychange'])
        (name==='visibilitychange'?document:window).addEventListener(name,()=>{
          parityFocusTrace.push({event:name,at:performance.now(),focused:document.hasFocus(),hidden:document.hidden});
        });''')
    def gui(code):
        assert_renderer_clean(page)
        return page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    def checkpoint_diagnostics():
        state=page.evaluate('''({focused:document.hasFocus(),hidden:document.hidden,
          fullscreen:!!document.fullscreenElement,frame:window.application?.applicationState,
          focusTrace:window.parityFocusTrace})''')
        report['checkpointEnvironment']=state
        return state
    gui.checkpoint_diagnostics=checkpoint_diagnostics
    try:
        start_application(page)
        page.wait_for_function('window.application?.applicationState || window.applicationResult', timeout=600000)
        assert page.evaluate('window.applicationResult === null')
        gui('Engine.PauseOnFocusLoss(false); "functional checkpoint focus policy"')
        report['fullscreen']=enter_fullscreen(page,browser)
        if args.capture:
            from phase4_capture import capture_settings
        report['attributes'] = open_original_match(gui, capture_settings() if args.capture else parity_settings(),native['attributes'])
        assert report['attributes']==native['attributes'], 'Native/browser original match attributes differ'
        def save_checkpoint(stage, target, state):
            baseline = next(entry for entry in native['checkpoints'] if entry['simulationMs'] == target)
            payload = page.evaluate('window.application.FS.readFile("/logs/sim_dump.txt",{encoding:"utf8"})').replace('\r\n', '\n').encode()
            destination = args.evidence / f'state-{target}.txt'
            destination.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            name=f'phase45-parity-{target}'
            gui('Engine.SaveGame('+json.dumps(name)+',"Phase 4.5 original simulation checkpoint",{}); "saved"')
            encoded=page.evaluate('''name=>{
              const bytes=application.FS.readFile('/data/saves/'+name+'.0adsave'),parts=[];
              for(let i=0;i<bytes.length;i+=32768)parts.push(String.fromCharCode(...bytes.subarray(i,i+32768)));
              return btoa(parts.join(''));
            }''',name)
            snapshot=preserve_save(base64.b64decode(encoded),args.evidence,target)
            scopes=debug_scopes(payload)
            comparison = dict(simulationMs=target, SHA256=digest, nativeSHA256=baseline['SHA256'],
                              dumpMatches=digest == baseline['SHA256'], state=state,
                              GUIStateMatches=state == baseline['state'],**snapshot,**scopes,
                              synchronizedStateMatches=snapshot['serializedSHA256']==baseline['serializedSHA256'],
                              nativeSerializedSHA256=baseline['serializedSHA256'],
                              nonLocalDebugMatches=scopes['nonLocalDebugSHA256']==baseline['nonLocalDebugSHA256'],
                              nativeNonLocalDebugSHA256=baseline['nonLocalDebugSHA256'])
            report['checkpoints'].append(comparison)
            (args.evidence / 'progress.json').write_text(json.dumps(report, indent=2))
            print('FULL_GAME_CHECKPOINT', target,'serialized',comparison['synchronizedStateMatches'],
                  'nonlocal-debug',comparison['nonLocalDebugMatches'],'raw-debug',comparison['dumpMatches'], flush=True)
            assert comparison['synchronizedStateMatches'], 'Original simulation.dat diverges at ' + str(target)
            assert comparison['nonLocalDebugMatches'], 'Non-local original debug state diverges at ' + str(target)
            assert comparison['GUIStateMatches'], 'Original GUI simulation state diverges at ' + str(target)
        if args.capture:
            from phase4_capture import run_capture
            report['capture']=run_capture(gui,save_checkpoint)
            assert report['capture']['commands']==native['capture']['commands'],'Original capture commands differ'
        elif args.systems or args.advanced:
            from phase4_systems import run_systems
            report['systems'] = run_systems(gui, save_checkpoint)
            assert report['systems']['commands'] == native['systems']['commands'], 'Original command traces differ'
            if args.advanced:
                from phase4_systems import run_advanced
                report['advanced'] = run_advanced(gui, save_checkpoint)
                assert report['advanced']['setup'] == native['advanced']['setup'], 'Original advanced command setup differs'
                assert report['advanced']['tradeCommand'] == native['advanced']['tradeCommand'], 'Original trade commands differ'
        else:
            for baseline in native['checkpoints']:
                target = baseline['simulationMs']
                save_checkpoint('parity', target, checkpoint(gui, target))
        page.screenshot(path=str(args.evidence / 'original-parity-session.png'))
        assert_renderer_clean(page)
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error)
        try:
            page.screenshot(path=str(args.evidence / 'failure.png'))
        except Exception:
            pass
    finally:
        (args.evidence / 'report.json').write_text(json.dumps(report, indent=2))
        try:
            if page.evaluate('!!window.application && window.applicationResult === null'):
                if not page.evaluate('!!window.application.applicationState'):
                    report['startupAborted'] = True
                    page.close()
                else:
                    if page.evaluate('document.fullscreenElement!==null'):page.evaluate('document.exitFullscreen()')
                    page.locator('#close').click()
                    page.wait_for_function('window.applicationResult !== null', timeout=60000)
                    report['shutdown'] = observe_shutdown(page, browser)
                    assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets'],report['shutdown']
                    assert page.evaluate('window.applicationResult.code')==0
        except Exception as error:
            report['teardownFailure'] = str(error);report['passed']=False
        (args.evidence / 'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps({key: report.get(key) for key in ['passed', 'failure', 'errors']}, indent=2))
raise SystemExit(0 if report['passed'] else 1)
