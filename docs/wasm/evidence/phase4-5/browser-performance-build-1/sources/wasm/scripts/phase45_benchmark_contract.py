"""Plan and assess independent measurements without requiring a GUI or GPU."""
import hashlib
import json
import math
from pathlib import Path

PIN='40b8794eecb9618da69e10bacffa8814c561aa51'
WORKLOADS=('skirmish','combat')


def assess_simulation_rate(report):
    """Bound elapsed time by actual original-state observation intervals.

    Reading the state and maintaining the workload can cross the nominal
    deadline. Never divide those extra simulation turns by the shorter plan.
    """
    initial=report.get('initialStateIntervalQpcMs',[])
    final=report.get('lastStateIntervalQpcMs',[])
    if any(not isinstance(interval,(list,tuple)) or len(interval)!=2 or any(not isinstance(value,(int,float)) or not math.isfinite(value) for value in interval)
           or interval[1]<interval[0] for interval in [initial,final]):
        return dict(withinTolerance=False,reason='Missing/invalid observation time bounds')
    minimum=(final[0]-initial[1])/1000
    maximum=(final[1]-initial[0])/1000
    if minimum<=0:return dict(withinTolerance=False,reason='Observation intervals overlap')
    simulation=(report['lastState']['simulation']['timeElapsed']-report['initialState']['simulation']['timeElapsed'])/1000
    low=simulation/maximum;high=simulation/minimum
    return dict(withinTolerance=simulation>=0 and low>.98 and high<1.02,
        rate=simulation/((minimum+maximum)/2),minimumRate=low,maximumRate=high,
        elapsedSecondsBounds=[minimum,maximum],simulationSeconds=simulation,
        scope='Actual monotonic host intervals enclosing original simulation-state reads; strict +/-2% for the entire uncertainty interval')

def assess_backlog(report):
    states=[report.get('initialState',{})]+[s.get('state',{}) for s in report.get('samples',[])]+[report.get('lastState',{})]
    values=[state['pendingTurns'] for state in states if isinstance(state.get('pendingTurns'),int)]
    if len(values)<7:return dict(nonGrowing=False,reason='Insufficient original turn backlog samples',samples=values)
    first=max(values[:3]);last=max(values[-3:]);peak=max(values)
    return dict(nonGrowing=last<=first and peak<=first+1,initialMax=first,finalMax=last,maximum=peak,samples=values,
        tolerance='No sustained increase; allow one transient pending turn above the initial sample window')

def make_plan(backends,repetitions,warmup,duration,workloads=WORKLOADS):
    if not backends or len(set(backends))!=len(backends) or any(b not in ('webgpu','webgl','native') for b in backends):
        raise ValueError('Choose distinct backends: webgpu, webgl, native')
    if repetitions<1 or warmup<0 or duration<1:raise ValueError('Invalid run lengths')
    if not workloads or len(set(workloads))!=len(workloads) or any(w not in WORKLOADS for w in workloads):
        raise ValueError('Choose distinct workloads: skirmish, combat')
    return [dict(backend=backend,workload=workload,repetition=repetition,
                 warmupSeconds=warmup,durationSeconds=duration)
            for repetition in range(1,repetitions+1) for workload in workloads for backend in backends]

def fingerprint(directory):
    result={}
    for name in ('pyrogenesis-application.mjs','pyrogenesis-application.wasm','application.html','application.mjs',
                 'application-data.json','webgpu-shaders.json','renderer-session.mjs','webgpu-engine.mjs','webgpu-border.mjs','webgpu-upload.mjs','webgpu-dispatch.mjs','webgpu-upload-probe.mjs','application-pointer.mjs','application-failure.mjs',
                 'webgpu-bundles.mjs','webgpu-bundles-probe.mjs',
                 'shared-request.mjs','webgpu-worker-bridge.mjs','webgpu-render-worker.mjs',
                 'webgpu-pipeline-pending.mjs','application-archives.mjs','archive-worker.mjs','archive-blocks.mjs','archive-blocks.json'):
        path=Path(directory)/name
        if path.is_file():
            with path.open('rb') as stream:result[name]=hashlib.file_digest(stream,'sha256').hexdigest()
    return result

def summarize(plan,results):
    checked=[]
    for run in plan:
        key=(run['backend'],run['workload'],run['repetition'])
        report=results.get(key,{})
        presentation=report.get('presentation',{})
        actual_backend=(report.get('renderer') or {}).get('backend')
        renderer_matches=(run['backend']=='native' or actual_backend=={'webgl':'webgl','webgpu':'webgpu'}[run['backend']])
        backlog=assess_backlog(report)
        shutdown=report.get('shutdown',{});sdk=shutdown.get('sdk',{})
        clean_shutdown=(report.get('exitCode')==0 if run['backend']=='native' else
            report.get('exitCode')==0 and all(shutdown.get(key)==[] for key in ('workers','liveApplicationTargets')) and
            all(sdk.get(key)==[] for key in ('running','pooled','pthreads')))
        clean_shutdown=clean_shutdown and not report.get('teardownFailure') and not report.get('closeFailure')
        fixed_clock=bool(report.get('functionalFixedFrameFrequency')) or any(str(value).startswith('-fixed-frame-frequency') for value in report.get('applicationArguments',[]))
        simulation=not fixed_clock and report.get('passed') is True and not report.get('errors') and not report.get('engineErrors') and abs(report.get('tickRate',0)-1)<.02 and backlog['nonGrowing'] and clean_shutdown
        displayed=presentation.get('measurementComplete') is True and report.get('presentmonExitCode')==0 and report.get('presentmonEventsLost')==0
        eligible=(run['warmupSeconds']>=120 and run['durationSeconds']>=900 and
                  report.get('warmupSeconds')==run['warmupSeconds'] and report.get('durationSeconds')==run['durationSeconds'])
        browser_gate=presentation.get('presentationGate30') is True and renderer_matches
        checked.append(dict(**run,complete=simulation and displayed and renderer_matches,
            eligibleForAcceptance=eligible,gate30=simulation and displayed and eligible and browser_gate,
            displayedFps=presentation.get('displayedFps'),p95FrameMs=presentation.get('p95FrameMs'),
            adapter=(report.get('renderer') or {}).get('adapter'),graphicsSettings=report.get('graphicsSettings'),
            backlog=backlog,
            cleanShutdown=bool(clean_shutdown),
            failure=report.get('failure')))
    gpu=[run for run in checked if run['backend']=='webgpu']
    workload_gates={workload:len({r['repetition'] for r in gpu if r['workload']==workload and r['gate30']})>=3 for workload in WORKLOADS}
    adapters={json.dumps(r['adapter'],sort_keys=True) for r in gpu}
    consistent=bool(gpu) and len(adapters)==1 and all(r['adapter'] for r in gpu)
    return dict(gamePin=PIN,phase45Accepted=False,runs=checked,
        webgpuPerformanceGate=all(workload_gates.values()) and consistent,workloadGates=workload_gates,
        consistentReportedWebGPUAdapter=bool(consistent),
        allPlannedMeasurementsComplete=bool(checked) and all(r['complete'] for r in checked),
        nativeAndWebGLIncluded=all(any(r['backend']==backend for r in checked) for backend in ('native','webgl')),
        sameActiveGPUVerified=False,
        scope='Independent presentation measurements. Active native GPU, matched graphics, functional/visual parity and stability require separate review; this summary never accepts phase 4.5.')
