"""Rebuild candidate 2 with the AI state capture after the turn frame's Present."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from phase45_shader_program_source import parallel_compile_source

os.environ.update(EMCC_CORES='2', BINARYEN_CORES='2')
includes=Path('/tmp/phase4-includes');includes.mkdir(exist_ok=True)
for name in ['boost','enet','libxml']:
    target=includes/name
    if not target.exists():target.symlink_to(Path('/spike/headless/include')/name)
shutil.copytree('/spike/headless/include/fmt',includes/'fmt',dirs_exist_ok=True)
fmt=includes/'fmt/core.h'
fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))','parse_format_string<true>(str_, checker(str_, {}))'))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--guest-profile',action='store_true',help='Also sample AI guest source locations; diagnostic only, never FPS evidence.')
parser.add_argument('--spidermonkey-library',help='Re-run the native-EH dependency audit for this separately built archive.')
parser.add_argument('--cached-time-origin',action='store_true',help='Read performance.timeOrigin once per global in emscripten_get_now; identical values.')
parser.add_argument('--async-calls',type=int,help='Recompile the WebGPU Device.cpp with this asynchronous batch bound (default 6).')
parser.add_argument('--kernel-verify',action='store_true',help='Diagnostic only: AI map kernels also run the original JS and compare.')
parser.add_argument('--variant',help='Output directory suffix; never reuse the name of an existing candidate.')
args=parser.parse_args()
base=Path('/phase45-build/application-ai-map-kernels-2')
variant=args.variant or ('ai-deferred-capture-guest-1' if args.guest_profile else 'ai-deferred-capture-2')
out=Path('/phase45-build')/('application-'+variant);out.mkdir(exist_ok=True)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((base/'compile-report.json').read_text())
assert report['status']=='COMPILE_PASSED_NOT_LINKED' and report.get('aiMapKernels') and not report.get('denseAISnapshot')
for unit in report['results']:
    assert unit['exitCode']==0 and digest(Path(unit['object']))==unit['objectSHA256']
if args.spidermonkey_library:
    from phase45_exception_audit import audit,dependencies
    library=Path(args.spidermonkey_library)
    provenance=json.loads(library.with_name('report.json').read_text())
    assert provenance['passed'] and digest(library)==provenance['archiveSHA256']
    report['dependencyAudit']=audit(dependencies(library,report['nativeCurl']['archive']))
    assert report['dependencyAudit']['passed'],'Scripting archive failed the native-EH audit'
shutil.copytree(base/'runtime-browser',out/'runtime-browser',dirs_exist_ok=True)
if args.cached_time_origin:
    time_origin=out/'runtime-browser'/'application-time-origin.js'
    time_origin.write_bytes(Path('/workspace/wasm/browser/application-time-origin.js').read_bytes().replace(b'\r\n',b'\n'))
    report['additionalJSLibraries']=report.get('additionalJSLibraries',[])+[dict(path=str(time_origin),SHA256=digest(time_origin))]
private=out/'source'
headers=[]
for name in ['components/CCmpAIManager.cpp','Simulation2.cpp','helpers/AIDeferredStart.h','helpers/AIGuestProfiler.h',
             'helpers/AIMapKernels.h','helpers/AIWorkerMailbox.h','helpers/AIWorkerScript.h','helpers/DeferredCommands.h']:
    src=Path('/workspace/source/simulation2')/name
    dst=private/'simulation2'/name;dst.parent.mkdir(parents=True,exist_ok=True)
    # The Windows checkout may use CRLF; compile the same text the frozen tree used.
    dst.write_bytes(src.read_bytes().replace(b'\r\n',b'\n'))
    if dst.suffix=='.h':headers.append(dict(path=str(dst),SHA256=digest(dst)))
# The browser frame loop exists only in the frozen, patched main.cpp copy.
units={u['source']:u for u in report['results']}
main_unit=units['main.cpp']
main_source=Path(main_unit['sourceFile']).read_text()
assert digest(Path(main_unit['sourceFile']))==main_unit['sourceSHA256']
def edit(text,old,new):
    assert text.count(old)==1,'Unexpected main.cpp for '+old
    return text.replace(old,new)
main_source=edit(main_source,'#include "application-deferred-replay.h"\n',
    '#include "application-deferred-replay.h"\n#include "simulation2/helpers/AIDeferredStart.h"\n')
# Only Frame() renders before this point; NonVisualFrame relies on the turn hook.
main_source=edit(main_source,'\tg_Profiler.Frame();\n\n\tLimitFPS();',
    '\t// This frame\'s Present is already dispatched to the render worker.\n'
    '\tAIDeferredStart::Run();\n\n\tg_Profiler.Frame();\n\n\tLimitFPS();')
(private/'main.cpp').write_text(main_source)
frozen=Path(report['frozenSourceRoot'])
# Earlier builds compiled the raw workspace file and lost the GLES adaptations.
shader_program=private/'renderer/backend/gl/ShaderProgram.cpp';shader_program.parent.mkdir(parents=True,exist_ok=True)
shader_program.write_text(parallel_compile_source((frozen/'renderer/backend/gl/ShaderProgram.cpp').read_text()))
browser_compile=shader_program.with_name('BrowserShaderCompile.h')
browser_compile.write_bytes(Path('/workspace/source/renderer/backend/gl/BrowserShaderCompile.h').read_bytes().replace(b'\r\n',b'\n'))
headers.append(dict(path=str(browser_compile),SHA256=digest(browser_compile)))
sources={'main.cpp':(private/'main.cpp',[]),
    'renderer/backend/gl/ShaderProgram.cpp':(shader_program,['-iquote',str(frozen/'renderer/backend/gl')]),
    'simulation2/Simulation2.cpp':(private/'simulation2/Simulation2.cpp',['-iquote',str(frozen/'simulation2')]),
    'simulation2/components/CCmpAIManager.cpp':(private/'simulation2/components/CCmpAIManager.cpp',[])}
if args.async_calls:
    device_unit=units['renderer/backend/webgpu/Device.cpp']
    device=private/'renderer/backend/webgpu/Device.cpp';device.parent.mkdir(parents=True,exist_ok=True)
    device.write_bytes(Path('/workspace/source/renderer/backend/webgpu/Device.cpp').read_bytes().replace(b'\r\n',b'\n'))
    # Only the bound may differ from the compiled object; headers stay the frozen copies.
    assert digest(Path(device_unit['sourceFile']))==device_unit['sourceSHA256']
    sources['renderer/backend/webgpu/Device.cpp']=(device,['-iquote',str(Path(device_unit['sourceFile']).parent),'-DWASM_WEBGPU_ASYNC_CALLS='+str(args.async_calls)])
failed=False
for relative,(source,extra) in sources.items():
    unit=units[relative]
    target=out/(relative.replace('/','_')+'.o')
    command=list(unit['command'])
    command[command.index('-c')+1]=str(source)
    command[command.index('-o')+1]=str(target)
    command[1:1]=['-DWASM_AI_DEFERRED_CAPTURE=1','-I'+str(private),*extra]
    if args.guest_profile and relative.endswith('CCmpAIManager.cpp'):command.insert(1,'-DWASM_AI_GUEST_PROFILE=1')
    if args.kernel_verify and relative.endswith('CCmpAIManager.cpp'):command.insert(1,'-DWASM_AI_KERNEL_VERIFY=1')
    log=out/(relative.replace('/','_')+'.log')
    with log.open('w') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    unit.update(command=command,sourceFile=str(source),sourceSHA256=digest(source),object=str(target),log=str(log),exitCode=result.returncode)
    if result.returncode:failed=True;print(log.read_text()[-12000:],flush=True)
    else:unit['objectSHA256']=digest(target)
report.update(aiDeferredCapture=True,cachedTimeOrigin=args.cached_time_origin,webgpuAsyncCalls=args.async_calls or 6,
    platformExperiment='ai-deferred-capture-guest-profile' if args.guest_profile else 'ai-deferred-capture',
    diagnosticOnly=args.guest_profile or args.kernel_verify,aiGuestProfiler=args.guest_profile,aiKernelVerify=args.kernel_verify,
    status='COMPILE_FAILED' if failed else 'COMPILE_PASSED_NOT_LINKED',
    additionalHeaders=report.get('additionalHeaders',[])+headers,
    buildScriptSHA256=digest(Path(__file__)),
    baseCompileReportSHA256=digest(base/'compile-report.json'),
    scope='Candidate 2 objects; threaded AI game-state capture runs after the turn frame dispatches Present. '
        'Requires original-state sync/threaded parity and independent physical validation.')
(out/'compile-report.json').write_text(json.dumps(report,indent=2))
print(report['status'],flush=True)
raise SystemExit(1 if failed else 0)
