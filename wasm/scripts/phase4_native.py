"""Visible native original application and numbered GUI test mailbox."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import json
import uuid

class VisibleNativeProcess:
    def __init__(self,status):
        self.status=status
        self.pid=json.loads(status.read_text())['pid']
        self.returncode=None
    def poll(self):
        try:
            state=json.loads(self.status.read_text())
        except (PermissionError,json.JSONDecodeError):
            return None
        self.returncode=state.get('exitCode')
        return self.returncode
    def wait(self,timeout=60):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if self.poll() is not None:return self.returncode
            time.sleep(.05)
        raise TimeoutError('Visible native game has not exited')

class NativeApplication:
    def __init__(self, log, fullscreen=False, visible=True, pause_on_focus_loss=None, fixed_frame_frequency=None):
        self.root=Path('wasm/build/native-phase4').resolve()
        self.executable=self.root/'binaries/system/pyrogenesis.exe'
        self.mailbox=Path(tempfile.mkdtemp(prefix='0ad-phase4-native-'))
        self.sequence=0
        if visible:
            jobs=Path('wasm/build/phase4-native-visible').resolve();jobs.mkdir(parents=True,exist_ok=True)
            run=uuid.uuid4().hex
            self.mailbox=jobs/run;self.mailbox.mkdir()
            (jobs/'request.json').write_text(json.dumps(dict(run=run,fullscreen=fullscreen)))
            status=self.mailbox/'status.json'
            print('WAITING_FOR_VISIBLE_NATIVE_LAUNCHER',run,flush=True)
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                if status.exists():
                    try:state=json.loads(status.read_text())
                    except (PermissionError,json.JSONDecodeError):time.sleep(.05);continue
                    if state.get('error'):raise RuntimeError(state['error'])
                    self.process=VisibleNativeProcess(status)
                    print('WAITING_FOR_VISIBLE_NATIVE_READY',str(self.mailbox/'desktop-ready'),flush=True)
                    ready_deadline=time.monotonic()+180
                    while time.monotonic()<ready_deadline:
                        if (self.mailbox/'desktop-ready').exists():return
                        if self.process.poll() is not None:raise RuntimeError('Native game exited before desktop verification')
                        time.sleep(.1)
                    raise TimeoutError('Native window must be verified in the visible desktop before testing')
                time.sleep(.1)
            raise TimeoutError('Launch Phase4VisibleNative.exe in the visible desktop')
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=1
        focus_options=[] if pause_on_focus_loss is None else ['-conf=pauseonfocusloss:'+str(pause_on_focus_loss).lower()]
        if fixed_frame_frequency is not None:
            if fixed_frame_frequency!=60:raise ValueError('Only the declared 60 Hz functional snapshot clock is supported')
            focus_options.append('-fixed-frame-frequency=60')
        environment=dict(os.environ,PHASE4_NATIVE_AUTOMATION=str(self.mailbox))
        if pause_on_focus_loss is False:environment['SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS']='0'
        self.process=subprocess.Popen([str(self.executable),'-writableRoot','-mod=public',
            '-conf=windowed:'+str(not fullscreen).lower(),'-conf=xres:1920','-conf=yres:1080',
            '-conf=borderless.fullscreen:false','-conf=locale:en_US','-conf=userreport.enabledversion:0','-conf=vsync:true',*focus_options],
            cwd=self.executable.parent,startupinfo=startup,stdout=log,stderr=subprocess.STDOUT,
            env=environment)

    def gui(self,code):
        self.sequence+=1
        response=self.mailbox/f'response-{self.sequence}.txt';ready=self.mailbox/f'ready-{self.sequence}'
        pending=self.mailbox/'request.tmp';pending.write_text(code,encoding='utf-8')
        pending.replace(self.mailbox/f'request-{self.sequence}.js')
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if ready.exists():
                try:result=response.read_text(encoding='utf-8')
                except PermissionError:time.sleep(.01);continue
                if result=='SCRIPT_EVALUATION_FAILED':raise RuntimeError(result+': '+code)
                return result
            if self.process.poll() is not None:raise RuntimeError('Native process exited: '+str(self.process.returncode))
            time.sleep(.005)
        raise TimeoutError('Native GUI request: '+code)

    def close(self):
        if self.process.poll() is None:self.gui('Engine.Exit(0); "ok"')
        return self.process.wait(timeout=60)
