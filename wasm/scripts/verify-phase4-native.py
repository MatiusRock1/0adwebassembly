"""Visible original Windows game with exact-time simulation checkpoints."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from benchmark_lock import BenchmarkLock
from phase4_flow import open_original_match, checkpoint, parity_settings
from phase45_simulation_snapshot import debug_scopes,preserve_save

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence', type=Path, default=Path('docs/wasm/evidence/phase4/native-parity'))
parser.add_argument('--systems', action='store_true')
parser.add_argument('--advanced', action='store_true')
parser.add_argument('--capture', action='store_true')
parser.add_argument('--visible', action='store_true')
parser.add_argument('--fullscreen',action='store_true',help='Use the original fullscreen window for functional checkpoints.')
args = parser.parse_args()
args.evidence.mkdir(parents=True, exist_ok=True)
mailbox = Path(tempfile.mkdtemp(prefix='0ad-phase4-native-'))
root = Path('wasm/build/native-phase4').resolve()
report = dict(passed=False, phase4Accepted=False, checkpoints=[])
report['fullscreenRequested']=args.fullscreen
report['focusPolicy']='Original pauseonfocusloss=false and SDL minimize-on-focus-loss disabled for functional checkpoints; not a performance measurement'
report['mailbox'] = str(mailbox)
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 1  # Win32 SW_SHOWNORMAL
with BenchmarkLock(), (args.evidence / 'native.log').open('w', encoding='utf-8') as log:
    executable = root / 'binaries/system/pyrogenesis.exe'
    report['executableSHA256'] = hashlib.sha256(executable.read_bytes()).hexdigest()
    if args.visible:
        from phase4_native import NativeApplication
        application=NativeApplication(log,fullscreen=args.fullscreen,pause_on_focus_loss=False)
        process=application.process
        mailbox=application.mailbox
        report['mailbox']=str(mailbox)
        report['visibleDesktopVerified']=True
    else:
        process = subprocess.Popen([str(executable), '-writableRoot', '-mod=public',
        '-conf=windowed:'+str(not args.fullscreen).lower(), '-conf=xres:1920', '-conf=yres:1080', '-conf=pauseonfocusloss:false',
        '-conf=locale:en_US', '-conf=userreport.enabledversion:0'],
        cwd=root / 'binaries/system', startupinfo=startup, stdout=log, stderr=subprocess.STDOUT,
        env=dict(os.environ, PHASE4_NATIVE_AUTOMATION=str(mailbox),SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS='0'))

    sequence = 0
    def gui(code):
        global sequence
        sequence += 1
        response = mailbox / f'response-{sequence}.txt'
        ready = mailbox / f'ready-{sequence}'
        pending = mailbox / 'request.tmp'
        pending.write_text(code, encoding='utf-8')
        pending.replace(mailbox / f'request-{sequence}.js')
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if ready.exists():
                try:
                    result = response.read_text(encoding='utf-8')
                except PermissionError:
                    time.sleep(0.01)
                    continue
                if result == 'SCRIPT_EVALUATION_FAILED':
                    raise RuntimeError(result + ': ' + code)
                return result
            if process.poll() is not None:
                raise RuntimeError('Original native game exited: ' + str(process.returncode))
            time.sleep(0.005)
        raise TimeoutError('Native GUI request: ' + code)

    try:
        if args.capture:
            from phase4_capture import capture_settings
        report['attributes'] = open_original_match(gui, capture_settings() if args.capture else parity_settings())
        report['initialProbe'] = gui('JSON.stringify({state:Engine.GuiInterfaceCall("GetSimulationState",{}),paused:Engine.IsPaused(),rate:Engine.GetSimRate(),player:Engine.GetPlayerID()})')
        print('NATIVE_INITIAL_PROBE', report['initialProbe'][:250], flush=True)
        report['arrowProbe'] = gui('(()=>{return "hello";})()')
        print('NATIVE_ARROW_PROBE', report['arrowProbe'], flush=True)
        def save_checkpoint(stage, target, state):
            dumps = list(root.glob('**/logs/sim_dump.txt'))
            if len(dumps) != 1:
                raise RuntimeError('Ambiguous original dump path: ' + str(dumps))
            payload = dumps[0].read_bytes().replace(b'\r\n', b'\n')
            destination = args.evidence / f'state-{target}.txt'
            destination.write_bytes(payload)
            name=f'phase45-parity-{target}'
            gui('Engine.SaveGame('+json.dumps(name)+',"Phase 4.5 original simulation checkpoint",{}); "saved"')
            saves=list(root.glob('**/saves/'+name+'.0adsave'))
            assert len(saves)==1,('Original native save missing or ambiguous',saves)
            snapshot=preserve_save(saves[0].read_bytes(),args.evidence,target)
            report['checkpoints'].append(dict(simulationMs=target, state=state,
                stage=stage,SHA256=hashlib.sha256(payload).hexdigest(), file=str(destination),
                **snapshot,**debug_scopes(payload)))
            (args.evidence / 'progress.json').write_text(json.dumps(report, indent=2))
            print('NATIVE_CHECKPOINT', target, report['checkpoints'][-1]['SHA256'], flush=True)
        if args.capture:
            from phase4_capture import run_capture
            report['capture']=run_capture(gui,save_checkpoint)
        elif args.systems or args.advanced:
            from phase4_systems import run_systems
            report['systems'] = run_systems(gui, save_checkpoint)
            if args.advanced:
                from phase4_systems import run_advanced
                report['advanced'] = run_advanced(gui, save_checkpoint)
        else:
            for target in [10000, 12000, 14000]:
                save_checkpoint('parity', target, checkpoint(gui, target))
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error)
    finally:
        (args.evidence / 'report.json').write_text(json.dumps(report, indent=2))
        # Keep the last native state visibly paused for inspection, then close
        # through the original SDL quit event rather than terminating the game.
        if process.poll() is None:
            try:
                gui('Engine.Exit(0); "ok"')
                report['exitCode'] = process.wait(timeout=60)
                assert report['exitCode']==0
            except Exception as error:
                report['closeFailure'] = str(error);report['passed']=False
        else:
            report['exitCode']=process.returncode
            if report['exitCode']!=0:report['passed']=False
        (args.evidence / 'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps({key: report.get(key) for key in ['passed', 'failure', 'exitCode', 'closeFailure']}, indent=2))
raise SystemExit(0 if report['passed'] else 1)
