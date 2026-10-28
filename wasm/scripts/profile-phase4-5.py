"""Short, instrumented diagnostic. Never performance acceptance evidence."""
import os
os.environ['SCENE_REAL_WINDOW']='1'
os.environ['SCENE_CDP_URL']='http://localhost:9229'
os.environ['SCENE_APPLICATION_URL']='http://localhost:8097/application.html?automation=1'
os.environ['SCENE_RENDERER']='webgpu'
os.environ['SCENE_AUTO_FULLSCREEN']='1'
import argparse
import base64
import importlib.util
import json
import hashlib
import shutil
from pathlib import Path
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import start_application,new_test_page,enter_fullscreen,observe_shutdown,assert_renderer_clean
from phase4_flow import open_original_match,checkpoint,parity_settings
from phase45_simulation_snapshot import preserve_save,debug_scopes
from phase4_workload import MANIFEST,apply_graphics_profile,populate,live_units
from phase45_window_focus import activate_browser_window,foreground_window

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('standalone',Path(__file__).with_name('benchmark-phase4-5-standalone.py'))
standalone=importlib.util.module_from_spec(spec);spec.loader.exec_module(standalone)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=30)
    parser.add_argument('--replenish-while-sampling',action='store_true',help='Keep the combat replenishment cadence during CDP sampling, with timestamps.')
    parser.add_argument('--settle-seconds',type=int,default=60)
    parser.add_argument('--workload',choices=['skirmish','combat'],default='skirmish')
    parser.add_argument('--background-functional',action='store_true',help='Profile CPU work at 1080p without requiring physical foreground; never use for FPS acceptance.')
    parser.add_argument('--original-profiler',action='store_true',help='Save the original engine profiler through Shift+F11 after CDP sampling; never part of an FPS capture.')
    parser.add_argument('--webgpu-directory',type=Path,default=ROOT/'wasm/dist/application-phase4-5',help='Explicit isolated candidate package to profile.')
    parser.add_argument('--cacheir-counts',action='store_true',help='Read unsupported-opcode counters from an explicitly instrumented diagnostic VM.')
    parser.add_argument('--audio-worker-checks',action='store_true',help='After sampling, check original pause/resume/music-stop/restart against actual SDK playback state.')
    parser.add_argument('--ai-worker-mode',choices=['sync','isolated-sync','threaded'],help='Select the experimental AI mode explicitly; never a native comparison.')
    parser.add_argument('--simulation-checkpoints',type=int,nargs='+',help='Save exact original simulation checkpoints with fixed parity settings and no benchmark population commands; not FPS evidence.')
    parser.add_argument('--ai-guest-samples',action='store_true',help='Read cooperative guest source samples from a separate diagnostic AI or simulation build; never FPS evidence.')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    if args.simulation_checkpoints and (args.simulation_checkpoints!=sorted(set(args.simulation_checkpoints)) or args.simulation_checkpoints[0]<=0):
        parser.error('Simulation checkpoints must be positive, unique and increasing')
    package=args.webgpu_directory.resolve()
    report=dict(passed=False,diagnosticOnly=True,performanceAcceptance=False,errors=[],console=[],workload=args.workload)
    report['packageDirectory']=str(package)
    report['aiWorkerMode']=args.ai_worker_mode
    report['buildSHA256']=standalone.fingerprint(package)
    symbols=package/'pyrogenesis-application.mjs.symbols'
    if symbols.is_file():
        shutil.copy2(symbols,args.output/'engine-symbols.txt')
        report['symbolsSHA256']=hashlib.sha256(symbols.read_bytes()).hexdigest()
    if (package/'link-report.json').is_file():shutil.copy2(package/'link-report.json',args.output/'link-report.json')
    standalone.require_free_port(8097);standalone.require_free_port(9229)
    with (args.output/'server.log').open('w') as log:
        server=subprocess.Popen([sys.executable,str(ROOT/'wasm/scripts/serve-phase2.py'),'--port','8097','--directory',str(package)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        chrome=None
        try:
            standalone.wait_url('http://localhost:8097/application.html',server)
            browser_profile=ROOT/'wasm/build/phase4-5'/('profile-'+str(os.getpid()))
            # A reused PID must not inherit another build's IndexedDB archives or config.
            if browser_profile.exists():shutil.rmtree(browser_profile)
            chrome=subprocess.Popen([str(Path(os.environ['ProgramFiles'])/'Google/Chrome/Application/chrome.exe'),
                '--user-data-dir='+str(browser_profile),
                '--remote-debugging-port=9229','--remote-debugging-address=127.0.0.1',
                '--no-first-run','--no-default-browser-check','--force-high-performance-gpu','--new-window',os.environ['SCENE_APPLICATION_URL']])
            standalone.wait_url('http://localhost:9229/json/version',chrome)
            with BenchmarkLock(),sync_playwright() as p:
                browser=p.chromium.connect_over_cdp(os.environ['SCENE_CDP_URL'])
                page=new_test_page(browser)
                page.on('pageerror',lambda error:report['errors'].append(str(error)))
                page.on('console',lambda message:report['console'].append(message.text))
                gui=lambda code:page.evaluate('code=>evaluateOriginalGUI(code)',code)
                try:
                    url=os.environ['SCENE_APPLICATION_URL']
                    if args.ai_worker_mode:url+='&aiworker='+args.ai_worker_mode
                    report['applicationURL']=url
                    start_application(page,url=url)
                    page.wait_for_function('window.application?.applicationState',timeout=180000)
                    apply_graphics_profile(gui,MANIFEST['graphicsProfile'])
                    report['attributes']=open_original_match(gui,parity_settings() if args.simulation_checkpoints else MANIFEST['settings'])
                    if not args.simulation_checkpoints:
                        report['setup']=populate(gui,page.wait_for_timeout,args.workload)
                    root=browser.new_browser_cdp_session()
                    owners=[x for x in root.send('SystemInfo.getProcessInfo')['processInfo'] if x['type']=='browser']
                    report['backgroundFunctional']=args.background_functional
                    if args.background_functional:
                        gui('Engine.PauseOnFocusLoss(false); "functional diagnostic only"')
                        page.evaluate('application.ccall("Phase4Resize",null,["number","number"],[1920,1080])')
                        page.wait_for_function('application.applicationState.width===1920 && application.applicationState.height===1080',timeout=30000)
                    else:
                        try:activate_browser_window(int(owners[0]['id']))
                        except RuntimeError as error:report['initialActivationFailure']=str(error)
                        report['fullscreen']=enter_fullscreen(page,browser)
                        try:report['foregroundWindow']=foreground_window(int(owners[0]['id']))
                        except RuntimeError as error:report['foregroundFailure']=str(error)
                    report['environment']=page.evaluate('({focused:document.hasFocus(),hidden:document.hidden,fullscreen:!!document.fullscreenElement})')
                    if args.simulation_checkpoints:
                        report['checkpoints']=[]
                        report['checkpointScope']='Original deterministic match, exact simulation time, unmodified SaveGame serialization; not FPS or complete gameplay acceptance'
                        for target in args.simulation_checkpoints:
                            state=checkpoint(gui,target)
                            payload=page.evaluate('application.FS.readFile("/logs/sim_dump.txt",{encoding:"utf8"})').replace('\r\n','\n').encode()
                            (args.output/f'state-{target}.txt').write_bytes(payload)
                            name=f'ai-checkpoint-{target}'
                            gui('Engine.SaveGame('+json.dumps(name)+',"AI worker semantic checkpoint",{}); "saved"')
                            encoded=page.evaluate('''name=>{
                              const bytes=application.FS.readFile('/data/saves/'+name+'.0adsave'),parts=[];
                              for(let i=0;i<bytes.length;i+=32768)parts.push(String.fromCharCode(...bytes.subarray(i,i+32768)));
                              return btoa(parts.join(''));
                            }''',name)
                            report['checkpoints'].append(dict(simulationMs=target,state=state,
                                **preserve_save(base64.b64decode(encoded),args.output,target),**debug_scopes(payload)))
                            engine_errors=[line for line in report['console'] if 'ERROR:' in line]
                            assert not engine_errors,engine_errors
                            (args.output/'checkpoint-progress.json').write_text(json.dumps(report['checkpoints'],indent=2))
                            print('AI_SIMULATION_CHECKPOINT',args.ai_worker_mode,target,report['checkpoints'][-1]['serializedSHA256'],flush=True)
                        gui('Engine.SetPaused(false,false); "resume after semantic checks"')
                    if args.workload=='combat':
                        report['settleScope']='Functional crash diagnostic with original battle/replenishment; transient unit counts below 200 do not qualify as a performance run'
                        deadline=time.monotonic()+args.settle_seconds
                        report['settleSamples']=[]
                        while time.monotonic()<deadline:
                            page.wait_for_timeout(min(MANIFEST['workloads']['combat']['reinforcementSeconds']*1000,max(1,(deadline-time.monotonic())*1000)))
                            assert_renderer_clean(page)
                            replenished=populate(gui,page.wait_for_timeout,'combat',initial=False)
                            count=live_units(replenished['state'])
                            report['settleSamples'].append(dict(elapsedSeconds=args.settle_seconds-max(0,deadline-time.monotonic()),liveUnitsAfterReplenishment=count))
                            (args.output/'progress.json').write_text(json.dumps(report['settleSamples'],indent=2))
                            print('FUNCTIONAL_COMBAT_STRESS',round(report['settleSamples'][-1]['elapsedSeconds']),count,flush=True)
                    else:page.wait_for_timeout(args.settle_seconds*1000)
                    root=page.context.new_cdp_session(page)
                    attached=[]
                    root.on('Target.attachedToTarget',lambda event:attached.append(event))
                    root.send('Target.setAutoAttach',dict(autoAttach=True,waitForDebuggerOnStart=False,flatten=False))
                    page.wait_for_timeout(1000)
                    replies={};sequence=0
                    def receive(event):
                        message=json.loads(event['message'])
                        if 'id' in message:replies[(event['sessionId'],message['id'])]=message
                    root.on('Target.receivedMessageFromTarget',receive)
                    def command(session,method,params=None):
                        nonlocal sequence
                        sequence+=1;key=(session,sequence)
                        root.send('Target.sendMessageToTarget',dict(sessionId=session,message=json.dumps(dict(id=sequence,method=method,params=params or {}))))
                        deadline=time.monotonic()+30
                        while key not in replies and time.monotonic()<deadline:page.wait_for_timeout(20)
                        response=replies.pop(key)
                        if 'error' in response:raise RuntimeError(response)
                        return response.get('result',{})
                    sessions=[]
                    report['attachedWorkerTargets']=attached
                    # Diagnostic-only outer-call timings. Never installed by
                    # the physical FPS benchmark or during its capture window.
                    report['initialRendererWork']=page.evaluate('''async()=>{
                      const b=application.webgpuBackend;
                      return b.remote ? await b.snapshot() : {stats:{...b.stats}};
                    }''')
                    page.evaluate('''()=>{
                      const b=application.webgpuBackend,original=b.call;
                      if(b.remote)return;
                      if(typeof original!=='function')throw new Error('Backend call profiler unavailable');
                      b.phase45CallProfile={original,methods:Object.create(null),startedMs:performance.now(),initialFrames:b.stats.frames};
                      b.call=function(method,args,data){
                        const started=performance.now();
                        try{return original.call(this,method,args,data);}
                        finally{
                          const stats=this.phase45CallProfile.methods[method]??={calls:0,totalMilliseconds:0,maxMilliseconds:0,bytes:0};
                          const elapsed=performance.now()-started;
                          stats.calls++;stats.totalMilliseconds+=elapsed;stats.maxMilliseconds=Math.max(stats.maxMilliseconds,elapsed);stats.bytes+=data?.byteLength||0;
                        }
                      };
                    }''')
                    if args.cacheir_counts:
                        report['cacheIRBefore']=page.evaluate('''()=>{
                          const m=application,n=m.ccall('Phase45MissingCacheIRSize','number',[],[]),p=m.ccall('Phase45MissingCacheIRCounts','number',[],[])>>>2;
                          const heap=new Uint32Array(m.webgpuBackend.heap().buffer);
                          return {timeMs:performance.now(),counts:Array.from({length:n},(_,i)=>Atomics.load(heap,p+i))};
                        }''')
                    if args.ai_guest_samples:
                        report['aiGuestBefore']=page.evaluate('JSON.parse(application.ccall("Phase45AIGuestProfile","string",[],[]))')
                    sim_timing_js='''(()=>{try{return JSON.parse(application.ccall("Phase45SimTiming","string",[],[]));}
                        catch(error){return null;}})()'''
                    sim_timing_before=page.evaluate(sim_timing_js)
                    root.send('Profiler.enable')
                    root.send('Profiler.setSamplingInterval',dict(interval=1000))
                    root.send('Profiler.start')
                    for event in attached:
                        target=event['targetInfo'];session=event['sessionId']
                        if target['type']!='worker':continue
                        command(session,'Profiler.enable')
                        command(session,'Profiler.setSamplingInterval',dict(interval=1000))
                        command(session,'Profiler.start')
                        sessions.append((target,session))
                    print('DIAGNOSTIC_PROFILING',len(sessions),'targets',args.seconds,'seconds',flush=True)
                    if args.replenish_while_sampling and args.workload=='combat':
                        report['samplingReplenishment']=[]
                        sampling_deadline=time.monotonic()+args.seconds
                        while time.monotonic()<sampling_deadline:
                            page.wait_for_timeout(min(MANIFEST['workloads']['combat']['reinforcementSeconds']*1000,max(1,(sampling_deadline-time.monotonic())*1000)))
                            started=page.evaluate('performance.now()')
                            replenished=populate(gui,page.wait_for_timeout,'combat',initial=False)
                            report['samplingReplenishment'].append(dict(pageStartMs=started,pageEndMs=page.evaluate('performance.now()'),trace=replenished['trace']))
                    else:page.wait_for_timeout(args.seconds*1000)
                    report['profiles']=[]
                    main_profile=root.send('Profiler.stop')['profile']
                    (args.output/'cpu-main.cpuprofile').write_text(json.dumps(main_profile))
                    report['profiles'].append(dict(target=dict(type='page',url=page.url),file='cpu-main.cpuprofile',samples=len(main_profile.get('samples',[]))))
                    for index,(target,session) in enumerate(sessions):
                        profile=command(session,'Profiler.stop')['profile']
                        name=f'cpu-{index}.cpuprofile'
                        (args.output/name).write_text(json.dumps(profile))
                        report['profiles'].append(dict(target=target,file=name,samples=len(profile.get('samples',[]))))
                        root.send('Target.detachFromTarget',dict(sessionId=session))
                    assert sessions,'No engine workers were profiled'
                    if args.cacheir_counts:
                        report['cacheIRAfter']=page.evaluate('''()=>{
                          const m=application,n=m.ccall('Phase45MissingCacheIRSize','number',[],[]),p=m.ccall('Phase45MissingCacheIRCounts','number',[],[])>>>2;
                          const heap=new Uint32Array(m.webgpuBackend.heap().buffer);
                          return {timeMs:performance.now(),counts:Array.from({length:n},(_,i)=>Atomics.load(heap,p+i)),names:Array.from({length:n},(_,i)=>m.ccall('Phase45MissingCacheIRName','string',['number'],[i]))};
                        }''')
                        before=report['cacheIRBefore'];after=report['cacheIRAfter']
                        assert len(before['counts'])==len(after['counts'])==len(after['names'])
                        report['missingCacheIROps']=sorted([dict(op=name,count=(last-first)&0xffffffff) for name,first,last in zip(after['names'],before['counts'],after['counts']) if last!=first],key=lambda row:row['count'],reverse=True)
                        report['missingCacheIRScope']='Unsupported-opcode counts during this instrumented window; no exclusive cost attribution or FPS acceptance.'
                        (args.output/'cacheir-counts.json').write_text(json.dumps(dict(diagnosticOnly=True,performanceAcceptance=False,
                            milliseconds=after['timeMs']-before['timeMs'],counts=report['missingCacheIROps'],scope=report['missingCacheIRScope']),indent=2))
                    if args.ai_guest_samples:
                        after=page.evaluate('JSON.parse(application.ccall("Phase45AIGuestProfile","string",[],[]))')
                        before=report['aiGuestBefore']
                        initial={(s['file'],s['line']):s['hits'] for s in before['samples']}
                        samples=[dict(s,hits=s['hits']-initial.get((s['file'],s['line']),0)) for s in after['samples']]
                        data=dict(diagnosticOnly=True,performanceAcceptance=False,periodMs=after.get('periodMs',10),
                            scope='Cooperative interrupt locations, biased by VM checkpoints; not exclusive CPU time.',
                            samples=sorted([s for s in samples if s['hits']>0],key=lambda s:s['hits'],reverse=True),
                            maxDelayUs=after.get('maxDelayUs',0),
                            **{key:after.get(key,0)-before.get(key,0) for key in ['requests','noCaller','overflow','late']})
                        if 'slowStacks' in after:
                            # Builds with per-computation stacks: keep only the sampling window.
                            for table in ['slowStacks','otherStacks']:
                                prior={s['stack']:s['hits'] for s in before.get(table,[])}
                                data[table]=sorted([dict(s,hits=s['hits']-prior.get(s['stack'],0)) for s in after[table]
                                    if s['hits']>prior.get(s['stack'],0)],key=lambda s:s['hits'],reverse=True)
                            data.update(slowThresholdMs=after['slowThresholdMs'],
                                **{key:after[key]-before.get(key,0) for key in ['slowComputations','slowMilliseconds','otherComputations','otherMilliseconds']})
                        (args.output/'ai-guest-profile.json').write_text(json.dumps(data,indent=2))
                        report['aiGuestProfile']=data
                    report['aiKernelStats']=page.evaluate('''(()=>{try{return JSON.parse(application.ccall("Phase45AIKernelStats","string",[],[]));}
                        catch(error){return null;}})()''')
                    sim_timing_after=page.evaluate(sim_timing_js)
                    if sim_timing_before and sim_timing_after:
                        # Diagnostic builds only: keep the sampling window by subtracting the earlier totals.
                        timing=dict(diagnosticOnly=True,performanceAcceptance=False,slowThresholdMs=sim_timing_after['slowThresholdMs'],
                            **{key:sim_timing_after[key]-sim_timing_before[key] for key in ['slowTurns','slowMs','slowUnattributedMs','otherTurns','otherMs','otherUnattributedMs']})
                        for table in ['slow','other']:
                            prior={row['key']:row for row in sim_timing_before[table]}
                            rows=[]
                            for row in sim_timing_after[table]:
                                was=prior.get(row['key'],dict(calls=0,ms=0))
                                if row['calls']>was['calls']:
                                    rows.append(dict(key=row['key'],calls=row['calls']-was['calls'],ms=row['ms']-was['ms'],maxMsSinceStart=row['maxMs']))
                            timing[table]=sorted(rows,key=lambda row:row['ms'],reverse=True)
                        # Turns over the worst-turn threshold since the start, with their largest rows.
                        timing['worstSinceStart']=sim_timing_after.get('worst',[])
                        timing['wrappedFunctions']=sim_timing_after.get('wrappedFunctions')
                        (args.output/'sim-timing.json').write_text(json.dumps(timing,indent=2))
                        report['simTiming']={key:value for key,value in timing.items() if key not in ('slow','other')}
                    report['variationMemoStats']=page.evaluate('''(()=>{try{return JSON.parse(application.ccall("Phase45VariationMemoStats","string",[],[]));}
                        catch(error){return null;}})()''')
                    report['simKernelStats']=page.evaluate('''(()=>{try{return JSON.parse(application.ccall("Phase45SimKernelStats","string",[],[]));}
                        catch(error){return null;}})()''')
                    report['frames']=page.evaluate('application.applicationFrames')
                    report['finalRendererWork']=page.evaluate('''async()=>{
                      const b=application.webgpuBackend;
                      return b.remote ? await b.snapshot() : {stats:{...b.stats}};
                    }''')
                    report['rendererStats']=report['finalRendererWork']['stats']
                    report['bridgeCallTiming']=page.evaluate('''()=>{
                      const b=application.webgpuBackend,p=b.phase45CallProfile;
                      if(b.remote)return {available:false,reason:'Encoding occurs in the render worker; window backend.call is not used'};
                      return {methods:p.methods,elapsedMilliseconds:performance.now()-p.startedMs,frames:b.stats.frames-p.initialFrames};
                    }''')
                    report['bridgeCallTimingScope']='Instrumented CPU time and counts of outer backend calls; excludes GPU completion and is not FPS acceptance evidence'
                    if args.original_profiler:
                        assert not args.background_functional,'Original profiler hotkey requires actual game focus'
                        # Use the original save hotkey without opening its overlay.
                        # CDP sampling has ended, and this tool never records FPS.
                        page.keyboard.press('Shift+F11')
                        paths=['/logs/profile.txt','/data/logs/profile.txt']
                        page.wait_for_function('paths=>paths.some(path=>application.FS.analyzePath(path).exists)',arg=paths,timeout=15000)
                        snapshot=page.evaluate('paths=>{const path=paths.find(path=>application.FS.analyzePath(path).exists);return {path,text:application.FS.readFile(path,{encoding:"utf8"})};}',paths)
                        (args.output/'original-profile.txt').write_text(snapshot['text'],encoding='utf8')
                        report['originalProfiler']=dict(path=snapshot['path'],SHA256=hashlib.sha256(snapshot['text'].encode()).hexdigest(),scope='Original hierarchical engine/AI profiler snapshot, saved after CDP sampling; not FPS evidence')
                    if args.audio_worker_checks:
                        from phase45_audio_checks import verify_worker_audio
                        report['audioWorkerChecks']=verify_worker_audio(page,gui,package)
                    assert_renderer_clean(page)
                    report['engineErrors']=[line for line in report['console'] if 'ERROR:' in line]
                    assert not report['engineErrors'],report['engineErrors']
                    assert not report['errors']
                    report['passed']=True
                except Exception as error:
                    import traceback
                    report.update(failure=str(error),traceback=traceback.format_exc())
                finally:
                    try:
                        page.evaluate('''()=>{
                          const b=window.application?.webgpuBackend;
                          if(b?.phase45CallProfile){b.call=b.phase45CallProfile.original;delete b.phase45CallProfile;}
                        }''')
                        if page.evaluate('!!document.fullscreenElement'):page.evaluate('document.exitFullscreen()')
                        page.locator('#close').click()
                        page.wait_for_function('window.applicationResult!==null',timeout=60000)
                        report['shutdown']=observe_shutdown(page,browser)
                        report['exitCode']=page.evaluate('applicationResult.code')
                        assert report['exitCode']==0 and not report['shutdown']['workers']
                    except Exception as error:report.update(passed=False,teardownFailure=str(error))
        finally:
            if chrome:
                report['browserExitBeforeCleanup']=chrome.poll()
                try:standalone.close_browser('http://localhost:9229',chrome)
                except Exception as error:report['browserCloseFailure']=str(error)
                report['browserExitAfterCleanup']=chrome.poll()
            server.terminate();server.wait(timeout=15)
            report['engineErrors']=[line for line in report['console'] if 'ERROR:' in line]
            if report['engineErrors']:
                report['passed']=False
                report.setdefault('failure','Engine logged errors; runtime diagnostic is invalid')
            (args.output/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(passed=report['passed'],failure=report.get('failure'),profileCount=len(report.get('profiles',[])),foregroundFailure=report.get('foregroundFailure')),indent=2),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
