"""Visible native full-game comparison using the identical workload manifest."""
import argparse
import csv
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
from benchmark_lock import BenchmarkLock
from phase4_native import NativeApplication
from phase4_flow import open_original_match
from phase4_workload import MANIFEST,MANIFEST_PATH,populate,observe,observe_counts,live_units,graphics_settings,apply_graphics_profile
from phase45_benchmark_contract import assess_backlog,assess_simulation_rate
from phase45_window_focus import activate_browser_window

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workload',choices=['skirmish','combat'],required=True)
parser.add_argument('--warmup-seconds',type=int,default=120)
parser.add_argument('--duration-seconds',type=int,default=900)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--direct-desktop',action='store_true',help='Launch in the operator terminal session; do not wait for the Computer Use helper.')
args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
report=dict(passed=False,phase4Accepted=False,frames=[],samples=[],commandTrace=[],workload=args.workload,
    warmupSeconds=args.warmup_seconds,durationSeconds=args.duration_seconds,manifest=MANIFEST,
    manifestSHA256=hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest())
report['harnessSHA256']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    for name in [Path(__file__).name,'phase4_workload.py','phase4_flow.py','phase4_native.py','phase45_window_focus.py']}
presentmon=Path('wasm/build/tools/PresentMon-2.6.0-x64.exe').resolve()
user32=ctypes.WinDLL('user32',use_last_error=True)
user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user32.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user32.IsWindowVisible.argtypes=[wintypes.HWND]
user32.GetForegroundWindow.restype=wintypes.HWND
callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
def window_surface(pid):
    foreground_owner=wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),ctypes.byref(foreground_owner))
    assert foreground_owner.value==pid,'Native game lost actual foreground focus'
    windows=[]
    def visit(hwnd,lparam):
        owner=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid and user32.IsWindowVisible(hwnd):
            rect=wintypes.RECT();user32.GetClientRect(hwnd,ctypes.byref(rect))
            windows.append(dict(hwnd=int(hwnd),width=rect.right-rect.left,height=rect.bottom-rect.top,minimized=bool(user32.IsIconic(hwnd))))
        return True
    callback=callback_type(visit);user32.EnumWindows(callback,0)
    assert any(w['width']==1920 and w['height']==1080 and not w['minimized'] for w in windows),windows
    return windows
capture=None;application=None
with BenchmarkLock(),args.output.with_suffix('.native.log').open('w') as log,args.output.with_suffix('.presentmon.log').open('w') as capture_log:
    try:
        application=NativeApplication(log,fullscreen=True,visible=not args.direct_desktop)
        report['executableSHA256']=hashlib.sha256(application.executable.read_bytes()).hexdigest()
        report['applicationArguments']=getattr(application.process,'args',[])
        assert not any(value.startswith('-fixed-frame-frequency') for value in report['applicationArguments']),'Fixed simulation clock is forbidden in performance measurements'
        report['attributes']=open_original_match(application.gui,MANIFEST['settings'])
        apply_graphics_profile(application.gui,MANIFEST['graphicsProfile'])
        # Written by the running original renderer, rather than inferred from
        # installed adapters or Windows graphics preferences.
        system_info=application.root/'binaries/logs/system_info.txt'
        system_text=system_info.read_text(encoding='utf-8',errors='replace')
        fields=dict(re.findall(r'^(Video Card|Video Driver|Video Mode)\s*:\s*(.+)$',system_text,re.MULTILINE))
        assert all(fields.get(key) for key in ('Video Card','Video Driver','Video Mode')),fields
        report['renderer']=dict(backend='native',renderer=fields['Video Card'].strip(),
            driver=fields['Video Driver'].strip(),videoMode=fields['Video Mode'].strip(),
            source='Original renderer system_info.txt',
            systemInfoSHA256=hashlib.sha256(system_info.read_bytes()).hexdigest())
        args.output.with_suffix('.system-info.txt').write_text(system_text,encoding='utf-8')
        report['graphicsSettings']=graphics_settings(application.gui)
        # This existing PID-based helper also activates a native window. Do it
        # once during setup; never repair lost focus during warmup/measurement.
        report['setupActivation']=activate_browser_window(application.process.pid)
        report['setup']=populate(application.gui,lambda ms:time.sleep(ms/1000),args.workload)
        report['commandTrace'].extend(report['setup']['trace'])
        report['nativeWindow']=window_surface(application.process.pid)
        report['fullscreen']=True;report['presentationProcessId']=application.process.pid
        report['presentmonCsv']=str(args.output.with_suffix('.presentmon.csv').resolve())
        session='0ad-native-phase4-'+str(application.process.pid)
        capture=subprocess.Popen([str(presentmon),'--process_id',str(application.process.pid),
            '--timed',str(args.warmup_seconds+args.duration_seconds+90),'--terminate_after_timed',
            '--no_console_stats','--session_name',session,'--output_file',report['presentmonCsv'],
            '--write_display_metadata','--qpc_time_ms'],stdout=capture_log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(10)
        report['measurementStartQpcMs']=time.perf_counter()*1000
        initial_state_start=time.perf_counter()*1000
        report['initialState']=observe(application.gui)
        report['initialStateIntervalQpcMs']=[initial_state_start,time.perf_counter()*1000]
        deadline=time.monotonic()+args.warmup_seconds+args.duration_seconds
        while time.monotonic()<deadline:
            time.sleep(min(MANIFEST['workloads'][args.workload]['reinforcementSeconds'],max(.001,deadline-time.monotonic())))
            surface=window_surface(application.process.pid)
            observation_started=time.perf_counter()
            state=observe_counts(application.gui)
            observation_ms=(time.perf_counter()-observation_started)*1000
            units=live_units(state)
            assert state['rate']==1 and not state['paused'] and units>=MANIFEST['minimumLiveUnits']
            report['samples'].append(dict(qpcMs=time.perf_counter()*1000,surface=surface,state=state,liveUnits=units,observationMilliseconds=observation_ms))
            maintenance_started=time.perf_counter()
            report['commandTrace'].extend(populate(application.gui,lambda ms:time.sleep(ms/1000),args.workload,initial=False)['trace'])
            report['samples'][-1]['workloadMaintenanceMilliseconds']=(time.perf_counter()-maintenance_started)*1000
            print('NATIVE_FULL_GAME',args.workload,round(args.warmup_seconds+args.duration_seconds-max(0,deadline-time.monotonic())),units,flush=True)
        last_state_start=time.perf_counter()*1000
        report['lastState']=observe(application.gui)
        report['lastStateIntervalQpcMs']=[last_state_start,time.perf_counter()*1000]
        report['simulationTiming']=assess_simulation_rate(report)
        report['tickRate']=report['simulationTiming'].get('rate',0)
        # Preserve physical presentation diagnostics even when the completed
        # run fails simulation speed or backlog. Neither acceptance gate changes.
        report['measurementCompleted']=True
        report['backlog']=assess_backlog(report)
        assert report['simulationTiming']['withinTolerance'],report['simulationTiming']
        assert report['backlog']['nonGrowing'],report['backlog']
        report['passed']=True
    except Exception as error:report['failure']=str(error)
    finally:
        if capture:
            subprocess.run([str(presentmon),'--session_name',session,'--terminate_existing_session'],stdout=capture_log,stderr=subprocess.STDOUT,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
            report['presentmonExitCode']=capture.wait(timeout=30)
        capture_log.flush()
        report['presentmonEventsLost']=sum(int(n) for n in re.findall(r'(\d+) ETW events were lost',args.output.with_suffix('.presentmon.log').read_text(errors='replace')))
        if application:
            try:
                report['exitCode']=application.close()
                assert report['exitCode']==0
            except Exception as error:
                report['closeFailure']=str(error);report['passed']=False
        if report.get('measurementCompleted'):
            spec=importlib.util.spec_from_file_location('presentation',Path(__file__).with_name('analyze-presentation.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with Path(report['presentmonCsv']).open(encoding='utf-8-sig',newline='') as stream:
                report['presentation']=module.analyze(report,list(csv.DictReader(stream)))
            # Native physical comparison has Win32 surface samples, no C++ draw
            # observer. Keep the shared analyzer's draw-validation gate false.
            report['presentation']['nativeSurfaceSamplesVerified']=True
        args.output.write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ['passed','failure','tickRate','presentation']},indent=2))
raise SystemExit(0 if report['passed'] else 1)
