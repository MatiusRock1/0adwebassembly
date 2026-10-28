"""Original native renderer PNGs at the browser reference camera and tick.

F2 is posted only to the test game's verified HWND. Images come
from the original renderer screenshot function, not desktop capture.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import time
import traceback
from benchmark_lock import BenchmarkLock
from phase4_native import NativeApplication
from phase4_flow import open_original_match,parity_settings,checkpoint
from phase4_workload import graphics_settings

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--reference',type=Path,required=True)
args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
reference=json.loads(args.reference.read_text())
if not reference['passed']:raise RuntimeError('Browser reference must pass first')
report=dict(passed=False,visualParityAccepted=False,phase45Accepted=False,
    visualContract=reference['visualContract'],captureMethod='Original native F2 renderer PNG/readback; no desktop capture')
user32=ctypes.WinDLL('user32',use_last_error=True)
user32.GetForegroundWindow.restype=wintypes.HWND
user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user32.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user32.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
with BenchmarkLock(),(args.evidence/'native.log').open('w',encoding='utf-8') as log:
    application=NativeApplication(log,fullscreen=False,visible=False,pause_on_focus_loss=False,
        fixed_frame_frequency=reference['visualContract'].get('fixedFrameFrequency'))
    report['functionalFixedFrameFrequency']=reference['visualContract'].get('fixedFrameFrequency')
    report['windowMode']='Original 1920x1080 windowed client for functional F2 capture; fullscreen performance is a separate test'
    report['focusPolicy']='Original pauseonfocusloss=false and SDL minimize-on-focus-loss disabled for functional render capture only; not a performance measurement'
    def capture(name):
        windows=[]
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        @callback_type
        def visit(candidate,unused):
            owner=wintypes.DWORD();user32.GetWindowThreadProcessId(candidate,ctypes.byref(owner))
            rect=wintypes.RECT();user32.GetClientRect(candidate,ctypes.byref(rect))
            if owner.value==application.process.pid and user32.IsWindowVisible(candidate) and not user32.IsIconic(candidate) and [rect.right-rect.left,rect.bottom-rect.top]==[1920,1080]:windows.append(candidate)
            return True
        user32.EnumWindows(visit,0)
        assert len(windows)==1,('Original native capture window missing or ambiguous',windows)
        hwnd=windows[0]
        report['captureWindow']=dict(hwnd=hwnd,owner=application.process.pid,foreground=hwnd==user32.GetForegroundWindow())
        rect=wintypes.RECT();assert user32.GetClientRect(hwnd,ctypes.byref(rect))
        assert [rect.right-rect.left,rect.bottom-rect.top]==[1920,1080]
        directory=application.root/'binaries/data/screenshots';directory.mkdir(parents=True,exist_ok=True)
        before=set(directory.glob('*.png'))
        assert user32.PostMessageW(hwnd,0x100,0x71,1|(0x3c<<16))
        time.sleep(.05)
        assert user32.PostMessageW(hwnd,0x101,0x71,1|(0x3c<<16)|(1<<30)|(1<<31))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            files=set(directory.glob('*.png'))-before
            if len(files)==1:
                try:
                    data=next(iter(files)).read_bytes()
                    if data[:8]==b'\x89PNG\r\n\x1a\n' and data[-8:-4]==b'IEND':
                        (args.evidence/name).write_bytes(data);return
                except PermissionError:pass
            elif len(files)>1:raise RuntimeError('Ambiguous original screenshot output')
            if application.process.poll() is not None:raise RuntimeError('Native game exited during screenshot')
            time.sleep(.05)
        raise TimeoutError('Original native F2 screenshot')
    try:
        report['executableSHA256']=hashlib.sha256(application.executable.read_bytes()).hexdigest()
        report['attributes']=open_original_match(application.gui,parity_settings(),reference['attributes'])
        application.gui('''(()=>{for(const [key,value] of Object.entries(PROFILE))Engine.ConfigDB_CreateValue("user",key,value);return "temporary matched graphics";})()'''.replace('PROFILE',json.dumps(reference['visualContract']['graphicsProfile'])))
        report['simulation']=checkpoint(application.gui,reference['visualContract']['simulationMs'])
        application.gui('g_Selection.reset();g_Selection.setHighlightList([]);"clear original selection and hover"')
        dump=application.root/'binaries/logs/sim_dump.txt'
        report['simulationSHA256']=hashlib.sha256(dump.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        report['graphicsSettings']=graphics_settings(application.gui)
        camera=reference['cameraRequest'];report['cameraRequest']=camera
        values=[camera['position'][key] for key in ('x','y','z')]+[camera['rotation'][key] for key in ('x','y')]+[camera['zoom']]
        application.gui('Engine.SetCameraData('+','.join(map(str,values))+'); "camera"')
        time.sleep(2)
        application.gui('g_Selection.reset();g_Selection.setHighlightList([]);"clear original selection and hover"')
        report['camera']=json.loads(application.gui('JSON.stringify({position:Engine.GetCameraPosition(),rotation:Engine.GetCameraRotation(),zoom:Engine.GetCameraZoom()})'))
        for key in ('attributes','simulationSHA256','graphicsSettings','camera'):
            assert report[key]==reference[key],('Native visual prerequisite mismatch',key,report[key],reference[key])
        capture('original-matched.png')
        for value,label in [('false','hard'),('true','pcf')]:
            application.gui('Engine.ConfigDB_CreateValue("user","shadowpcf","'+value+'"); "shadow"')
            time.sleep(1.5);capture('original-shadow-'+label+'.png')
        system_info=application.root/'binaries/logs/system_info.txt'
        (args.evidence/'system-info.txt').write_bytes(system_info.read_bytes())
        report['renderer']=dict(backend='native',source='Original renderer system-info.txt')
        report['passed']=True
    except Exception as error:
        report['failure']=str(error);report['traceback']=traceback.format_exc()
    finally:
        try:
            report['exitCode']=application.close()
            assert report['exitCode']==0
        except Exception as error:
            report['closeFailure']=str(error);report['passed']=False
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ('passed','failure','exitCode')},indent=2))
raise SystemExit(0 if report['passed'] else 1)
